from src.utils.bybit_client import BybitClient
from src.strategies.entry_strategy import EntryStrategy
from src.scanning.volatility_scanner import VolatilityScanner
from src.utils.indicators import Indicators
from config.config import Config
import pandas as pd
from datetime import datetime
import time

class BacktestEngine:
    def __init__(self):
        self.client = BybitClient()
        self.strategy = EntryStrategy(self.client)
        self.scanner = VolatilityScanner()
        self.trades = []
        self.total_pnl = 0.0  # 누적 손익 (자본 차감 없음)
        self.timing_stats = {}  # 시간 측정용
    
    def run_backtest(self, symbols=None, candles=None, timeframe=None):
        """백테스팅 실행"""
        if candles is None:
            candles = Config.BACKTEST_CANDLES
        if timeframe is None:
            timeframe = Config.ENTRY_TIMEFRAME
            
        print(f"\n{'='*80}")
        print(f"백테스팅 시작 - {candles}개 캔들 ({timeframe}분봉, UTC 시간)")
        print(f"거래당 포지션 크기: ${Config.POSITION_SIZE} (레버리지 {Config.LEVERAGE}x)")
        print(f"※ 매 거래마다 ${Config.POSITION_SIZE}로 진입, 손익만 누적")
        print(f"{'='*80}\n")
        
        # 심볼이 지정되지 않으면 스캔
        if symbols is None:
            scanned_coins = self.scanner.scan_coins()
            if scanned_coins.empty:
                print("코인을 찾지 못했습니다.")
                return
            
            # 변동성 필터: MIN ~ MAX 범위 내
            filtered_coins = scanned_coins[
                (scanned_coins['volatility_24h'] >= Config.MIN_VOLATILITY) &
                (scanned_coins['volatility_24h'] <= Config.MAX_VOLATILITY)
            ]
            
            if filtered_coins.empty:
                print(f"변동성 {Config.MIN_VOLATILITY}~{Config.MAX_VOLATILITY}% 범위 코인이 없습니다.")
                return
            
            # 변동성 기준으로 정렬하여 상위 선택
            symbols = filtered_coins.nlargest(Config.TOP_BACKTEST_COINS, 'volatility_24h')['symbol'].tolist()
            print(f"변동성 필터: {Config.MIN_VOLATILITY}~{Config.MAX_VOLATILITY}% (너무 높은 변동성 제외)")
        
        print(f"\n백테스팅 대상 ({len(symbols)}개): {symbols}\n")
        
        for symbol in symbols:
            print(f"\n{'='*80}")
            print(f"심볼: {symbol}")
            print(f"{'='*80}")
            self._backtest_symbol(symbol, candles, timeframe)
        
        self._print_results()
    
    def _backtest_symbol(self, symbol, candles, timeframe):
        """개별 심볼 백테스팅 (시간 측정 포함)"""
        symbol_start = time.time()
        timings = {}
        
        # 1. 멀티 타임프레임 피보나치 계산
        print(f"\n[1/5] 멀티 타임프레임 피보나치 계산...", end='', flush=True)
        step_start = time.time()
        mtf_fib = Indicators.calculate_multi_timeframe_fibonacci(
            self.client, 
            symbol, 
            Config.FIBONACCI_TIMEFRAMES
        )
        timings['fibonacci'] = time.time() - step_start
        
        if not mtf_fib:
            print(f" ❌ 데이터 부족")
            return
        
        print(f" ✅ {len(mtf_fib)}개 타임프레임 ({timings['fibonacci']:.2f}초)")
        
        # 2. 진입 타임프레임 데이터 가져오기
        print(f"[2/5] {timeframe}분봉 데이터 로딩 ({candles}개)...", end='', flush=True)
        step_start = time.time()
        entry_df = self.client.get_klines(symbol, interval=timeframe, limit=candles)
        timings['load_candles'] = time.time() - step_start
        
        if entry_df.empty or len(entry_df) < Config.BB_PERIOD + 10:
            print(f" ❌ 데이터 부족 ({len(entry_df)}개 봉)")
            return
        
        print(f" ✅ {len(entry_df)}개 봉 ({timings['load_candles']:.2f}초)")
        
        # 3. 비트코인 데이터 로딩 및 추세 사전 계산
        print(f"[3/5] 비트코인 추세 데이터 로딩 및 사전 계산...", end='', flush=True)
        step_start = time.time()
        btc_df = self.client.get_klines('BTCUSDT', interval=timeframe, limit=candles)
        
        if btc_df.empty:
            print(f" ❌ 비트코인 데이터 없음")
            return
        
        # 🔥 BTC 추세 사전 계산 (모든 시점에 대해)
        from src.utils.trend_analyzer import TrendAnalyzer
        btc_trends_cache = {}
        
        for i in range(60, len(btc_df)):  # 최소 60개 필요 (1시간)
            window_btc = btc_df.iloc[:i+1].copy()
            # 이미 계산된 데이터로 추세 분석 (API 호출 없음)
            btc_trends_cache[i] = TrendAnalyzer.get_coin_trend(window_btc, timeframe_minutes=60)
            btc_trends_cache[i]['trend_type'] = 'BTC'
        
        timings['load_btc'] = time.time() - step_start
        print(f" ✅ {len(btc_df)}개 봉, {len(btc_trends_cache)}개 추세 캐시 ({timings['load_btc']:.2f}초)")
        
        # 4. 지표 사전 계산
        print(f"[4/5] 지표 계산 (볼린저, RSI)...", end='', flush=True)
        step_start = time.time()
        entry_df = Indicators.calculate_bollinger_bands(entry_df, Config.BB_PERIOD, Config.BB_STD)
        entry_df = Indicators.calculate_rsi(entry_df, period=14)
        timings['indicators'] = time.time() - step_start
        print(f" ✅ 완료 ({timings['indicators']:.2f}초)")
        
        # 4.5. BTC 추세 미리 계산 (최적화!)
        print(f"[4.5/5] BTC 추세 사전 계산 (60분 윈도우)...", end='', flush=True)
        step_start = time.time()
        # BTC 데이터로 60분 윈도우 추세 계산 (한 번만!)
        btc_trend = self.strategy.trend_analyzer.get_btc_trend(self.client, timeframe_minutes=60)
        timings['btc_trend_calc'] = time.time() - step_start
        print(f" ✅ 완료 ({timings['btc_trend_calc']:.2f}초)")
        
        # 4.6. 펀딩비 미리 조회 (최적화!)
        print(f"[4.6/5] 펀딩비 조회...", end='', flush=True)
        step_start = time.time()
        funding_info = self.strategy.advanced_analyzer.get_funding_rate(self.client, symbol)
        timings['funding_rate'] = time.time() - step_start
        print(f" ✅ 완료 ({timings['funding_rate']:.2f}초)")
        
        # 5. 슬라이딩 윈도우로 진입 신호 찾기
        total_candles = len(entry_df) - Config.BB_PERIOD - 10
        print(f"[5/5] 진입 신호 탐색 ({total_candles}개 봉, 누적 손익: ${self.total_pnl:.2f})...")
        step_start = time.time()
        signals_found = 0
        trades_before = len(self.trades)
        
        signal_analysis_times = []
        
        # 진행률 표시를 위한 체크포인트 (10% 단위)
        checkpoints = [int(total_candles * i / 10) for i in range(1, 11)]
        checkpoint_idx = 0
        
        for idx, i in enumerate(range(Config.BB_PERIOD + 10, len(entry_df))):
            # 진행률 표시 (10% 단위)
            if checkpoint_idx < len(checkpoints) and idx >= checkpoints[checkpoint_idx]:
                progress = (checkpoint_idx + 1) * 10
                elapsed = time.time() - step_start
                estimated_total = elapsed / (idx + 1) * total_candles
                remaining = estimated_total - elapsed
                print(f"    진행: {progress}% ({idx+1}/{total_candles}) | 경과: {elapsed:.1f}초 | 예상 남은 시간: {remaining:.1f}초", flush=True)
                checkpoint_idx += 1
            
            # 현재까지의 데이터로 분석
            signal_start = time.time()
            window_df = entry_df.iloc[:i+1].copy()
            
            # 진입 신호 분석 (BTC 추세 + 펀딩비 캐시 전달)
            signal = self.strategy.analyze_entry(window_df, symbol, mtf_fib, btc_trend=btc_trend, funding_info=funding_info)
            signal_analysis_times.append(time.time() - signal_start)
            
            if signal:
                signals_found += 1
                
                # 추세 정보 출력 (첫 신호만)
                if signals_found == 1 and 'trend_reason' in signal:
                    strategy_type = signal.get('strategy', 'BASIC')
                    confidence = signal.get('confidence', 60)
                    print(f"\n    📊 전략: {strategy_type} (신뢰도 {confidence}점)")
                    print(f"       {signal['trend_reason']}")
                    print(f"       BTC: {signal['btc_trend']['trend']} ({signal['btc_trend']['price_change_pct']:.2f}%)")
                    print(f"       코인: {signal['coin_trend']['trend']} ({signal['coin_trend']['price_change_pct']:.2f}%)")
                    if 'funding_info' in signal:
                        print(f"       펀딩비: {signal['funding_info']['sentiment']} ({signal['funding_info']['funding_rate_pct']:.3f}%)")
                
                # 진입 후 결과 시뮬레이션
                trade_result = self._simulate_trade(entry_df, i, signal)
                
                if trade_result:
                    # 거래에 추가 정보 기록 (분석용)
                    trade_result['strategy'] = signal.get('strategy', 'BASIC')
                    trade_result['confidence'] = signal.get('confidence', 60)
                    trade_result['btc_trend'] = signal.get('btc_trend', {}).get('trend', 'UNKNOWN')
                    trade_result['coin_trend'] = signal.get('coin_trend', {}).get('trend', 'UNKNOWN')
                    trade_result['btc_change'] = signal.get('btc_trend', {}).get('price_change_pct', 0)
                    trade_result['coin_change'] = signal.get('coin_trend', {}).get('price_change_pct', 0)
                    trade_result['funding_sentiment'] = signal.get('funding_info', {}).get('sentiment', 'UNKNOWN')
                    trade_result['rsi'] = signal.get('rsi', 0)
                    
                    self.trades.append(trade_result)
                    
                    # 손익만 누적 (자본 차감 없음)
                    self.total_pnl += trade_result['net_pnl']
        
        timings['signal_search'] = time.time() - step_start
        trades_completed = len(self.trades) - trades_before
        
        # 신호 분석 평균 시간
        if signal_analysis_times:
            timings['avg_signal_analysis'] = sum(signal_analysis_times) / len(signal_analysis_times)
            timings['total_signal_analysis'] = sum(signal_analysis_times)
        else:
            timings['avg_signal_analysis'] = 0
            timings['total_signal_analysis'] = 0
        
        print(f" ✅ {signals_found}개 신호, {trades_completed}개 거래 완료 ({timings['signal_search']:.2f}초)")
        
        # 전체 시간
        timings['total'] = time.time() - symbol_start
        
        # 시간 통계 저장
        self.timing_stats[symbol] = timings
        
        # 시간 분석 출력
        print(f"\n⏱️  시간 분석:")
        print(f"   1. 피보나치 계산: {timings['fibonacci']:.2f}초 ({timings['fibonacci']/timings['total']*100:.1f}%)")
        print(f"   2. 캔들 데이터 로딩: {timings['load_candles']:.2f}초 ({timings['load_candles']/timings['total']*100:.1f}%)")
        print(f"   3. BTC 데이터 로딩: {timings['load_btc']:.2f}초 ({timings['load_btc']/timings['total']*100:.1f}%)")
        print(f"   4. 지표 계산: {timings['indicators']:.2f}초 ({timings['indicators']/timings['total']*100:.1f}%)")
        print(f"   4.5. BTC 추세 계산: {timings['btc_trend_calc']:.2f}초 ({timings['btc_trend_calc']/timings['total']*100:.1f}%)")
        print(f"   4.6. 펀딩비 조회: {timings['funding_rate']:.2f}초 ({timings['funding_rate']/timings['total']*100:.1f}%)")
        print(f"   5. 신호 탐색: {timings['signal_search']:.2f}초 ({timings['signal_search']/timings['total']*100:.1f}%)")
        if signal_analysis_times:
            print(f"      - 평균 신호 분석: {timings['avg_signal_analysis']*1000:.1f}ms")
            print(f"      - 총 신호 분석: {timings['total_signal_analysis']:.2f}초")
        print(f"   📊 전체 시간: {timings['total']:.2f}초")
        
        if trades_completed > 0:
            symbol_trades = [t for t in self.trades if t['symbol'] == symbol]
            wins = len([t for t in symbol_trades if t['result'] == 'WIN'])
            symbol_pnl = sum([t['net_pnl'] for t in symbol_trades])
            print(f"    승률: {wins}/{trades_completed} ({wins/trades_completed*100:.1f}%), 수익: ${symbol_pnl:.2f}, 누적 손익: ${self.total_pnl:.2f}")
    
    def _simulate_trade(self, df, entry_idx, signal):
        """거래 시뮬레이션 (수수료 포함) - 롱/숏 모두 지원"""
        entry_price = signal['entry_price']
        stop_loss = signal['stop_loss']
        take_profit = signal['take_profit']
        position_size = signal['position_size']
        leverage = signal['leverage']
        position_type = signal['type']  # 'LONG' or 'SHORT'
        
        # 진입 이후 데이터로 결과 확인
        for i in range(entry_idx + 1, len(df)):
            candle = df.iloc[i]
            
            if position_type == 'LONG':
                # 롱 포지션: 가격 하락시 손실, 상승시 이익
                # 스탑로스 체크 (아래로)
                if candle['low'] <= stop_loss:
                    exit_price = stop_loss
                    price_change_pct = ((exit_price - entry_price) / entry_price)
                    gross_pnl = position_size * price_change_pct * leverage
                    
                    # 수수료 계산
                    entry_fee = position_size * leverage * Config.TAKER_FEE
                    exit_fee = position_size * leverage * Config.TAKER_FEE
                    total_fee = entry_fee + exit_fee
                    
                    net_pnl = gross_pnl - total_fee
                    
                    return {
                        'symbol': signal['symbol'],
                        'type': position_type,
                        'entry_time': signal['timestamp'],
                        'exit_time': candle['timestamp'],
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'gross_pnl': gross_pnl,
                        'fees': total_fee,
                        'net_pnl': net_pnl,
                        'result': 'LOSS',
                        'bars_held': i - entry_idx,
                        'position_size': position_size,
                        'leverage': leverage
                    }
                
                # 익절 체크 (위로)
                if candle['high'] >= take_profit:
                    exit_price = take_profit
                    price_change_pct = ((exit_price - entry_price) / entry_price)
                    gross_pnl = position_size * price_change_pct * leverage
                    
                    # 수수료 계산
                    entry_fee = position_size * leverage * Config.TAKER_FEE
                    exit_fee = position_size * leverage * Config.TAKER_FEE
                    total_fee = entry_fee + exit_fee
                    
                    net_pnl = gross_pnl - total_fee
                    
                    return {
                        'symbol': signal['symbol'],
                        'type': position_type,
                        'entry_time': signal['timestamp'],
                        'exit_time': candle['timestamp'],
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'gross_pnl': gross_pnl,
                        'fees': total_fee,
                        'net_pnl': net_pnl,
                        'result': 'WIN',
                        'bars_held': i - entry_idx,
                        'position_size': position_size,
                        'leverage': leverage
                    }
            
            else:  # SHORT
                # 숏 포지션: 가격 상승시 손실, 하락시 이익
                # 스탑로스 체크 (위로)
                if candle['high'] >= stop_loss:
                    exit_price = stop_loss
                    price_change_pct = ((entry_price - exit_price) / entry_price)  # 숏은 반대
                    gross_pnl = position_size * price_change_pct * leverage
                    
                    # 수수료 계산
                    entry_fee = position_size * leverage * Config.TAKER_FEE
                    exit_fee = position_size * leverage * Config.TAKER_FEE
                    total_fee = entry_fee + exit_fee
                    
                    net_pnl = gross_pnl - total_fee
                    
                    return {
                        'symbol': signal['symbol'],
                        'type': position_type,
                        'entry_time': signal['timestamp'],
                        'exit_time': candle['timestamp'],
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'gross_pnl': gross_pnl,
                        'fees': total_fee,
                        'net_pnl': net_pnl,
                        'result': 'LOSS',
                        'bars_held': i - entry_idx,
                        'position_size': position_size,
                        'leverage': leverage
                    }
                
                # 익절 체크 (아래로)
                if candle['low'] <= take_profit:
                    exit_price = take_profit
                    price_change_pct = ((entry_price - exit_price) / entry_price)  # 숏은 반대
                    gross_pnl = position_size * price_change_pct * leverage
                    
                    # 수수료 계산
                    entry_fee = position_size * leverage * Config.TAKER_FEE
                    exit_fee = position_size * leverage * Config.TAKER_FEE
                    total_fee = entry_fee + exit_fee
                    
                    net_pnl = gross_pnl - total_fee
                    
                    return {
                        'symbol': signal['symbol'],
                        'type': position_type,
                        'entry_time': signal['timestamp'],
                        'exit_time': candle['timestamp'],
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'gross_pnl': gross_pnl,
                        'fees': total_fee,
                        'net_pnl': net_pnl,
                        'result': 'WIN',
                        'bars_held': i - entry_idx,
                        'position_size': position_size,
                        'leverage': leverage
                    }
        
        return None
    
    def _analyze_failure_patterns(self, df):
        """실패 패턴 분석"""
        print(f"\n{'='*80}")
        print("🔍 실패 원인 분석")
        print(f"{'='*80}\n")
        
        losses = df[df['result'] == 'LOSS']
        wins = df[df['result'] == 'WIN']
        
        if losses.empty:
            print("손실 거래가 없습니다!")
            return
        
        # 1. 전략별 성과
        print("📊 전략별 성과:")
        if 'strategy' in df.columns:
            strategy_stats = df.groupby('strategy').agg({
                'net_pnl': ['count', 'sum'],
                'result': lambda x: (x == 'WIN').sum()
            })
            strategy_stats.columns = ['거래수', '총수익', '승리수']
            strategy_stats['승률%'] = (strategy_stats['승리수'] / strategy_stats['거래수'] * 100).round(2)
            print(strategy_stats.to_string())
        
        # 2. BTC 추세별 성과
        print(f"\n📊 BTC 추세별 성과:")
        if 'btc_trend' in df.columns:
            btc_stats = df.groupby('btc_trend').agg({
                'net_pnl': ['count', 'sum'],
                'result': lambda x: (x == 'WIN').sum()
            })
            btc_stats.columns = ['거래수', '총수익', '승리수']
            btc_stats['승률%'] = (btc_stats['승리수'] / btc_stats['거래수'] * 100).round(2)
            print(btc_stats.to_string())
        
        # 3. 코인 추세별 성과
        print(f"\n📊 코인 추세별 성과:")
        if 'coin_trend' in df.columns:
            coin_stats = df.groupby('coin_trend').agg({
                'net_pnl': ['count', 'sum'],
                'result': lambda x: (x == 'WIN').sum()
            })
            coin_stats.columns = ['거래수', '총수익', '승리수']
            coin_stats['승률%'] = (coin_stats['승리수'] / coin_stats['거래수'] * 100).round(2)
            print(coin_stats.to_string())
        
        # 4. 포지션 타입 × 추세 조합
        print(f"\n📊 포지션 타입 × 코인 추세 조합:")
        if 'type' in df.columns and 'coin_trend' in df.columns:
            combo_stats = df.groupby(['type', 'coin_trend']).agg({
                'net_pnl': ['count', 'sum'],
                'result': lambda x: (x == 'WIN').sum()
            })
            combo_stats.columns = ['거래수', '총수익', '승리수']
            combo_stats['승률%'] = (combo_stats['승리수'] / combo_stats['거래수'] * 100).round(2)
            print(combo_stats.to_string())
        
        # 5. 신뢰도별 성과
        print(f"\n📊 신뢰도별 성과:")
        if 'confidence' in df.columns:
            df['confidence_range'] = pd.cut(df['confidence'], bins=[0, 70, 80, 90, 100], 
                                           labels=['60-70', '70-80', '80-90', '90-100'])
            conf_stats = df.groupby('confidence_range').agg({
                'net_pnl': ['count', 'sum'],
                'result': lambda x: (x == 'WIN').sum()
            })
            conf_stats.columns = ['거래수', '총수익', '승리수']
            conf_stats['승률%'] = (conf_stats['승리수'] / conf_stats['거래수'] * 100).round(2)
            print(conf_stats.to_string())
        
        # 6. 펀딩비 감정별 성과
        print(f"\n📊 펀딩비 감정별 성과:")
        if 'funding_sentiment' in df.columns:
            funding_stats = df.groupby('funding_sentiment').agg({
                'net_pnl': ['count', 'sum'],
                'result': lambda x: (x == 'WIN').sum()
            })
            funding_stats.columns = ['거래수', '총수익', '승리수']
            funding_stats['승률%'] = (funding_stats['승리수'] / funding_stats['거래수'] * 100).round(2)
            print(funding_stats.to_string())
        
        # 7. 보유 시간별 성과
        print(f"\n📊 보유 시간별 성과:")
        df['hold_time_range'] = pd.cut(df['bars_held'], bins=[0, 5, 10, 20, 50, 1000], 
                                       labels=['1-5분', '6-10분', '11-20분', '21-50분', '50분+'])
        hold_stats = df.groupby('hold_time_range').agg({
            'net_pnl': ['count', 'sum'],
            'result': lambda x: (x == 'WIN').sum()
        })
        hold_stats.columns = ['거래수', '총수익', '승리수']
        hold_stats['승률%'] = (hold_stats['승리수'] / hold_stats['거래수'] * 100).round(2)
        print(hold_stats.to_string())
        
        # 8. 주요 실패 패턴 요약
        print(f"\n💡 주요 인사이트:")
        
        # 가장 성과 좋은 조합
        if 'type' in df.columns and 'coin_trend' in df.columns:
            best_combo = df.groupby(['type', 'coin_trend'])['net_pnl'].sum().idxmax()
            best_pnl = df.groupby(['type', 'coin_trend'])['net_pnl'].sum().max()
            print(f"  ✅ 최고 조합: {best_combo[0]} × {best_combo[1]} (수익: ${best_pnl:.2f})")
        
        # 가장 성과 나쁜 조합
        if 'type' in df.columns and 'coin_trend' in df.columns:
            worst_combo = df.groupby(['type', 'coin_trend'])['net_pnl'].sum().idxmin()
            worst_pnl = df.groupby(['type', 'coin_trend'])['net_pnl'].sum().min()
            print(f"  ❌ 최악 조합: {worst_combo[0]} × {worst_combo[1]} (손실: ${worst_pnl:.2f})")
        
        # BTC 추세 영향
        if 'btc_trend' in df.columns:
            btc_impact = df.groupby('btc_trend')['net_pnl'].sum()
            best_btc = btc_impact.idxmax()
            print(f"  📈 BTC 추세: {best_btc} 일 때 가장 좋음 (${btc_impact[best_btc]:.2f})")
        
        # 최적 보유 시간
        optimal_hold = df.groupby('hold_time_range')['net_pnl'].sum().idxmax()
        print(f"  ⏱️  최적 보유 시간: {optimal_hold}")
        
        # 신뢰도 임계값 제안
        if 'confidence' in df.columns:
            for threshold in [70, 75, 80, 85, 90]:
                high_conf = df[df['confidence'] >= threshold]
                if len(high_conf) > 0:
                    win_rate = (high_conf['result'] == 'WIN').sum() / len(high_conf) * 100
                    total_pnl = high_conf['net_pnl'].sum()
                    print(f"  🎯 신뢰도 {threshold}+ : 승률 {win_rate:.1f}%, 수익 ${total_pnl:.2f} ({len(high_conf)}개 거래)")
    
    def _print_results(self):
        """백테스팅 결과 출력"""
        print(f"\n{'='*80}")
        print("백테스팅 결과 요약")
        print(f"{'='*80}\n")
        
        # 시간 통계 출력
        if self.timing_stats:
            print(f"⏱️  전체 시간 분석")
            print(f"{'='*80}")
            
            total_time = sum(t['total'] for t in self.timing_stats.values())
            avg_time = total_time / len(self.timing_stats)
            
            # 단계별 평균 시간
            avg_fibonacci = sum(t['fibonacci'] for t in self.timing_stats.values()) / len(self.timing_stats)
            avg_load_candles = sum(t['load_candles'] for t in self.timing_stats.values()) / len(self.timing_stats)
            avg_load_btc = sum(t['load_btc'] for t in self.timing_stats.values()) / len(self.timing_stats)
            avg_indicators = sum(t['indicators'] for t in self.timing_stats.values()) / len(self.timing_stats)
            avg_btc_trend = sum(t['btc_trend_calc'] for t in self.timing_stats.values()) / len(self.timing_stats)
            avg_funding = sum(t['funding_rate'] for t in self.timing_stats.values()) / len(self.timing_stats)
            avg_signal_search = sum(t['signal_search'] for t in self.timing_stats.values()) / len(self.timing_stats)
            
            print(f"\n코인당 평균 시간: {avg_time:.2f}초")
            print(f"  1. 피보나치 계산: {avg_fibonacci:.2f}초 ({avg_fibonacci/avg_time*100:.1f}%)")
            print(f"  2. 캔들 데이터 로딩: {avg_load_candles:.2f}초 ({avg_load_candles/avg_time*100:.1f}%)")
            print(f"  3. BTC 데이터 로딩: {avg_load_btc:.2f}초 ({avg_load_btc/avg_time*100:.1f}%)")
            print(f"  4. 지표 계산: {avg_indicators:.2f}초 ({avg_indicators/avg_time*100:.1f}%)")
            print(f"  4.5. BTC 추세 계산: {avg_btc_trend:.2f}초 ({avg_btc_trend/avg_time*100:.1f}%)")
            print(f"  4.6. 펀딩비 조회: {avg_funding:.2f}초 ({avg_funding/avg_time*100:.1f}%)")
            print(f"  5. 신호 탐색: {avg_signal_search:.2f}초 ({avg_signal_search/avg_time*100:.1f}%)")
            
            print(f"\n총 백테스팅 시간: {total_time:.2f}초 ({total_time/60:.1f}분)")
            print(f"코인 수: {len(self.timing_stats)}개")
            
            # 가장 느린 단계 찾기
            slowest_step = max([
                ('피보나치', avg_fibonacci),
                ('캔들 로딩', avg_load_candles),
                ('BTC 로딩', avg_load_btc),
                ('지표 계산', avg_indicators),
                ('BTC 추세', avg_btc_trend),
                ('펀딩비', avg_funding),
                ('신호 탐색', avg_signal_search)
            ], key=lambda x: x[1])
            
            print(f"\n🐌 가장 느린 단계: {slowest_step[0]} ({slowest_step[1]:.2f}초, {slowest_step[1]/avg_time*100:.1f}%)")
            
            print(f"{'='*80}\n")
        
        if not self.trades:
            print("거래 없음")
            return
        
        df = pd.DataFrame(self.trades)
        
        # 기본 통계
        total_trades = len(df)
        wins = len(df[df['result'] == 'WIN'])
        losses = len(df[df['result'] == 'LOSS'])
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        # 수익 통계
        total_gross_pnl = df['gross_pnl'].sum()
        total_fees = df['fees'].sum()
        total_net_pnl = df['net_pnl'].sum()
        
        avg_win = df[df['result'] == 'WIN']['net_pnl'].mean() if wins > 0 else 0
        avg_loss = df[df['result'] == 'LOSS']['net_pnl'].mean() if losses > 0 else 0
        
        # $7 이상 수익 거래
        profitable_trades = df[df['net_pnl'] >= Config.MIN_PROFIT_TARGET]
        target_achieved = len(profitable_trades)
        target_rate = (target_achieved / total_trades * 100) if total_trades > 0 else 0
        
        print(f"📊 거래 통계")
        print(f"  총 거래 수: {total_trades}")
        print(f"  승리: {wins} | 패배: {losses}")
        print(f"  승률: {win_rate:.2f}%")
        print(f"  평균 보유 시간: {df['bars_held'].mean():.1f} 봉 ({df['bars_held'].mean() * int(Config.ENTRY_TIMEFRAME):.0f}분)")
        
        print(f"\n💰 수익 통계")
        print(f"  총 수익 (수수료 전): ${total_gross_pnl:.2f}")
        print(f"  총 수수료: ${total_fees:.2f}")
        print(f"  순수익: ${total_net_pnl:.2f}")
        print(f"  평균 승리 수익: ${avg_win:.2f}")
        print(f"  평균 손실: ${avg_loss:.2f}")
        
        print(f"\n🎯 목표 달성")
        print(f"  ${Config.MIN_PROFIT_TARGET} 이상 수익 거래: {target_achieved}/{total_trades} ({target_rate:.2f}%)")
        
        print(f"\n💵 손익 결과")
        print(f"  거래당 투자금: ${Config.POSITION_SIZE}")
        print(f"  총 거래 수: {total_trades}")
        print(f"  총 투자금 (가상): ${Config.POSITION_SIZE * total_trades:.2f}")
        print(f"  누적 손익: ${total_net_pnl:.2f}")
        print(f"  손익률: {(total_net_pnl / (Config.POSITION_SIZE * total_trades) * 100):.2f}%" if total_trades > 0 else "  손익률: 0.00%")
        
        # 롱/숏 통계
        if 'type' in df.columns:
            long_trades = len(df[df['type'] == 'LONG'])
            short_trades = len(df[df['type'] == 'SHORT'])
            long_wins = len(df[(df['type'] == 'LONG') & (df['result'] == 'WIN')])
            short_wins = len(df[(df['type'] == 'SHORT') & (df['result'] == 'WIN')])
            
            print(f"\n📊 포지션 타입별 통계")
            print(f"  롱 포지션: {long_trades}개 (승률 {long_wins/long_trades*100:.1f}%)" if long_trades > 0 else "  롱 포지션: 0개")
            print(f"  숏 포지션: {short_trades}개 (승률 {short_wins/short_trades*100:.1f}%)" if short_trades > 0 else "  숏 포지션: 0개")
        
        print(f"\n📋 전체 거래 내역:")
        display_df = df[['symbol', 'type', 'entry_time', 'exit_time', 'entry_price', 'exit_price', 
                         'net_pnl', 'fees', 'result', 'bars_held']] if 'type' in df.columns else \
                    df[['symbol', 'entry_time', 'exit_time', 'entry_price', 'exit_price', 
                         'net_pnl', 'fees', 'result', 'bars_held']]
        
        # CSV 파일로 저장
        csv_filename = f"backtest_trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(csv_filename, index=False)
        print(f"거래 내역이 {csv_filename}에 저장되었습니다.")
        
        # 화면에는 요약만 출력
        print(f"\n승리 거래 (최근 10개):")
        wins = df[df['result'] == 'WIN'].tail(10)
        if not wins.empty:
            cols = ['symbol', 'type', 'entry_time', 'entry_price', 'exit_price', 'net_pnl', 'bars_held'] if 'type' in wins.columns else \
                   ['symbol', 'entry_time', 'entry_price', 'exit_price', 'net_pnl', 'bars_held']
            print(wins[cols].to_string(index=False))
        
        print(f"\n손실 거래 (최근 10개):")
        losses = df[df['result'] == 'LOSS'].tail(10)
        if not losses.empty:
            cols = ['symbol', 'type', 'entry_time', 'entry_price', 'exit_price', 'net_pnl', 'bars_held'] if 'type' in losses.columns else \
                   ['symbol', 'entry_time', 'entry_price', 'exit_price', 'net_pnl', 'bars_held']
            print(losses[cols].to_string(index=False))
        
        # 심볼별 통계
        print(f"\n📈 심볼별 성과:")
        symbol_stats = df.groupby('symbol').agg({
            'net_pnl': ['count', 'sum', 'mean'],
            'result': lambda x: (x == 'WIN').sum()
        }).round(2)
        symbol_stats.columns = ['거래수', '총수익', '평균수익', '승리수']
        symbol_stats['승률%'] = (symbol_stats['승리수'] / symbol_stats['거래수'] * 100).round(2)
        print(symbol_stats.to_string())
        
        # === 실패 원인 분석 ===
        self._analyze_failure_patterns(df)
