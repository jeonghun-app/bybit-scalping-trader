from src.utils.indicators import Indicators
from src.utils.trend_analyzer import TrendAnalyzer
from src.utils.advanced_signal_analyzer import AdvancedSignalAnalyzer
from config.config import Config
import pandas as pd

class EntryStrategy:
    def __init__(self, client):
        self.client = client
        self.config = Config()
        self.trend_analyzer = TrendAnalyzer()
        self.advanced_analyzer = AdvancedSignalAnalyzer()
    
    def _round_price(self, price, symbol):
        """가격을 심볼의 tickSize에 맞게 반올림"""
        try:
            instrument_info = self.client.get_instrument_info(symbol)
            if instrument_info:
                tick_size = instrument_info['tick_size']
                decimals = instrument_info['price_decimals']
                rounded = round(price / tick_size) * tick_size
                return round(rounded, decimals)
            return round(price, 2)  # 기본값
        except:
            return round(price, 2)  # 오류 시 기본값
    
    def analyze_entry(self, df, symbol, mtf_fib, btc_trend=None, funding_info=None, instrument_info=None):
        """진입 신호 분석 (1분 또는 3분봉 기준) - 롱/숏 모두 지원 + 추세 필터
        
        Args:
            df: 캔들 데이터
            symbol: 심볼
            mtf_fib: 멀티 타임프레임 피보나치
            btc_trend: 미리 계산된 BTC 추세 (None이면 새로 계산)
            funding_info: 미리 조회된 펀딩비 (None이면 새로 조회)
            instrument_info: 심볼 거래 규칙 (tickSize, qtyStep 등)
        """
        if len(df) < Config.BB_PERIOD + 5:
            return None
        
        # 심볼 정보 조회 (가격 소수점 처리용)
        if instrument_info is None:
            instrument_info = self.client.get_instrument_info(symbol)
        
        if not instrument_info:
            print(f"⚠️  {symbol} 심볼 정보 조회 실패")
            return None
        
        # 지표 계산
        df = Indicators.calculate_bollinger_bands(df, Config.BB_PERIOD, Config.BB_STD)
        df = Indicators.calculate_rsi(df, period=14)
        
        # 최근 데이터
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        # 🔥 추세 분석 (비트코인 + 개별 코인)
        # BTC 추세가 제공되지 않으면 새로 계산 (실시간 모드)
        if btc_trend is None:
            btc_trend = self.trend_analyzer.get_btc_trend(self.client, timeframe_minutes=60)
        coin_trend = self.trend_analyzer.get_coin_trend(df, timeframe_minutes=30)
        
        # 🔥 펀딩비 조회 (제공되지 않으면 새로 조회)
        if funding_info is None:
            funding_info = self.advanced_analyzer.get_funding_rate(self.client, symbol)
        
        # 🔥 피보나치 레벨 통합 (모든 타임프레임)
        all_fib_levels = {}
        for timeframe, fib_data in mtf_fib.items():
            all_fib_levels.update(fib_data['levels'])
        
        # === 고급 분석 1: 하락 추세 중 숏 진입 ===
        if coin_trend['trend'] == 'DOWNTREND':
            can_enter, reason, confidence = self.advanced_analyzer.should_enter_short_on_downtrend(
                latest['close'], all_fib_levels, btc_trend, coin_trend, 
                funding_info, latest['rsi']
            )
            if can_enter and confidence >= 80:  # 70 → 80 (더 엄격)
                return self._create_short_signal(
                    latest, prev, mtf_fib, btc_trend, coin_trend, 
                    funding_info, reason, confidence, symbol, instrument_info
                )
        
        # === 고급 분석 2: 상승 추세 중 롱 진입 ===
        if coin_trend['trend'] == 'UPTREND':
            can_enter, reason, confidence = self.advanced_analyzer.should_enter_long_on_uptrend(
                latest['close'], all_fib_levels, btc_trend, coin_trend, 
                funding_info, latest['rsi']
            )
            if can_enter and confidence >= 80:  # 70 → 80 (더 엄격)
                return self._create_long_signal(
                    latest, prev, mtf_fib, btc_trend, coin_trend, 
                    funding_info, reason, confidence, symbol, instrument_info
                )
        
        # === 고급 분석 3: 지지선 근처 반등 노리기 ===
        bb_position = (latest['close'] - latest['bb_lower']) / (latest['bb_upper'] - latest['bb_lower'])
        can_enter, reason, confidence = self.advanced_analyzer.should_enter_long_at_support(
            latest['close'], all_fib_levels, btc_trend, coin_trend, 
            funding_info, latest['rsi'], bb_position
        )
        if can_enter and confidence >= 85:  # 75 → 85 (더 엄격)
            return self._create_long_signal(
                latest, prev, mtf_fib, btc_trend, coin_trend, 
                funding_info, reason, confidence, symbol, instrument_info
            )
        
        # === 기본 전략 (기존 로직) ===
        # 롱 신호 체크
        long_signal = self._check_long_signal(df, latest, prev, mtf_fib, instrument_info)
        if long_signal:
            # 추세 필터 적용
            can_enter, reason = self.trend_analyzer.should_enter_long(btc_trend, coin_trend)
            if can_enter:
                long_signal['symbol'] = symbol
                long_signal['btc_trend'] = btc_trend
                long_signal['coin_trend'] = coin_trend
                long_signal['funding_info'] = funding_info
                long_signal['trend_reason'] = reason
                long_signal['confidence'] = 60  # 기본 신뢰도
                return long_signal
        
        # 숏 신호 체크
        short_signal = self._check_short_signal(df, latest, prev, mtf_fib, instrument_info)
        if short_signal:
            # 추세 필터 적용
            can_enter, reason = self.trend_analyzer.should_enter_short(btc_trend, coin_trend)
            if can_enter:
                short_signal['symbol'] = symbol
                short_signal['btc_trend'] = btc_trend
                short_signal['coin_trend'] = coin_trend
                short_signal['funding_info'] = funding_info
                short_signal['trend_reason'] = reason
                short_signal['confidence'] = 60  # 기본 신뢰도
                return short_signal
            
        return None
    
    def _check_long_signal(self, df, latest, prev, mtf_fib, instrument_info):
        """롱 진입 신호 확인 (개선된 전략 - 추세 확인 + 반등 확인)"""
        current_price = latest['close']
        tick_size = instrument_info['tick_size']
        price_decimals = instrument_info['price_decimals']
        
        # 조건 1: 볼린저 밴드 - 하단 근처
        bb_lower_break = current_price <= latest['bb_lower'] * 1.015  # 1.5% 이내
        bb_width_ok = latest['bb_width'] > 1.5  # 변동성 최소 기준
        
        # 조건 2: RSI - 과매도 구간에서 반등 확인 (개선!)
        rsi_oversold = latest['rsi'] < 35  # 35 미만 (더 엄격)
        rsi_bouncing = latest['rsi'] > prev['rsi']  # RSI 상승 중 (반등 확인!)
        rsi_signal = rsi_oversold and rsi_bouncing
        
        # 조건 3: 추세 필터 - 이동평균선 확인 (신규!)
        if len(df) >= 20:
            ma_5 = df['close'].rolling(5).mean().iloc[-1]
            ma_20 = df['close'].rolling(20).mean().iloc[-1]
            uptrend = ma_5 > ma_20  # 상승 추세
        else:
            uptrend = True  # 데이터 부족시 통과
        
        # 조건 4: 멀티 타임프레임 피보나치 - 최소 1개 이상의 타임프레임에서 지지
        fib_supports = []
        
        for timeframe, fib_data in mtf_fib.items():
            is_near, level_name, level_price = Indicators.is_near_fibonacci_level(
                current_price, 
                fib_data['levels'], 
                Config.FIB_TOLERANCE
            )
            if is_near:
                fib_supports.append({
                    'timeframe': timeframe,
                    'level': level_name,
                    'price': level_price
                })
        
        # 최소 1개 타임프레임에서 지지 필요
        fib_signal = len(fib_supports) >= 1
        
        # 조건 5: 강한 반등 신호 (개선!)
        strong_bounce = (
            latest['close'] > prev['low'] and  # 이전 저점보다 높음
            latest['close'] > latest['open'] and  # 양봉
            (latest['close'] - latest['open']) / latest['open'] > 0.002  # 최소 0.2% 상승
        )
        
        # 조건 6: 캔들 패턴 - 해머 패턴 확인 (신규!)
        body = abs(latest['close'] - latest['open'])
        lower_shadow = min(latest['open'], latest['close']) - latest['low']
        upper_shadow = latest['high'] - max(latest['open'], latest['close'])
        
        is_hammer = (
            lower_shadow > body * 2 and  # 아래 꼬리가 몸통의 2배 이상
            upper_shadow < body * 0.5  # 위 꼬리가 작음
        )
        
        # 진입 조건 (개선!):
        # (볼린저 밴드 AND 변동성) AND 
        # (RSI 반등 OR 피보나치) AND 
        # 상승 추세 AND 
        # (강한 반등 OR 해머 패턴)
        if bb_lower_break and bb_width_ok and (rsi_signal or fib_signal) and uptrend and (strong_bounce or is_hammer):
            entry_price = current_price
            
            # 레버리지 적용된 손익 계산
            stop_loss_pct = Config.STOP_LOSS_PERCENT / 100
            take_profit_pct = Config.TAKE_PROFIT_PERCENT / 100
            
            # tickSize에 맞게 가격 반올림
            rounded_entry = round(entry_price / tick_size) * tick_size
            rounded_stop = round((entry_price * (1 - stop_loss_pct)) / tick_size) * tick_size
            rounded_take = round((entry_price * (1 + take_profit_pct)) / tick_size) * tick_size
            
            stop_loss = round(rounded_stop, price_decimals)
            take_profit = round(rounded_take, price_decimals)
            entry_price = round(rounded_entry, price_decimals)
            
            # 예상 손익 (레버리지 적용)
            expected_profit = Config.POSITION_SIZE * take_profit_pct * Config.LEVERAGE
            expected_loss = Config.POSITION_SIZE * stop_loss_pct * Config.LEVERAGE
            
            # 수수료 계산 (진입 + 청산)
            entry_fee = Config.POSITION_SIZE * Config.LEVERAGE * Config.TAKER_FEE
            exit_fee = Config.POSITION_SIZE * Config.LEVERAGE * Config.TAKER_FEE
            total_fee = entry_fee + exit_fee
            
            # 순수익 (수수료 제외)
            net_profit = expected_profit - total_fee
            
            # 최소 수익 조건 확인
            if net_profit >= Config.MIN_PROFIT_TARGET:
                return {
                    'type': 'LONG',
                    'entry_price': entry_price,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
                    'timestamp': latest['timestamp'],
                    'rsi': latest['rsi'],
                    'bb_position': (current_price - latest['bb_lower']) / (latest['bb_upper'] - latest['bb_lower']),
                    'bb_width': latest['bb_width'],
                    'fib_supports': fib_supports,
                    'expected_profit': expected_profit,
                    'expected_loss': expected_loss,
                    'total_fee': total_fee,
                    'net_profit': net_profit,
                    'position_size': Config.POSITION_SIZE,
                    'leverage': Config.LEVERAGE
                }
        
        return None

    
    def _check_short_signal(self, df, latest, prev, mtf_fib, instrument_info):
        """숏 진입 신호 확인 (롱의 반대 전략)"""
        current_price = latest['close']
        tick_size = instrument_info['tick_size']
        price_decimals = instrument_info['price_decimals']
        
        # 조건 1: 볼린저 밴드 - 상단 근처
        bb_upper_break = current_price >= latest['bb_upper'] * 0.985  # 1.5% 이내
        bb_width_ok = latest['bb_width'] > 1.5  # 변동성 최소 기준
        
        # 조건 2: RSI - 과매수 구간에서 하락 확인
        rsi_overbought = latest['rsi'] > 65  # 65 초과
        rsi_falling = latest['rsi'] < prev['rsi']  # RSI 하락 중
        rsi_signal = rsi_overbought and rsi_falling
        
        # 조건 3: 추세 필터 - 이동평균선 확인
        if len(df) >= 20:
            ma_5 = df['close'].rolling(5).mean().iloc[-1]
            ma_20 = df['close'].rolling(20).mean().iloc[-1]
            downtrend = ma_5 < ma_20  # 하락 추세
        else:
            downtrend = True  # 데이터 부족시 통과
        
        # 조건 4: 멀티 타임프레임 피보나치 - 최소 1개 이상의 타임프레임에서 저항
        fib_resistances = []
        
        for timeframe, fib_data in mtf_fib.items():
            is_near, level_name, level_price = Indicators.is_near_fibonacci_level(
                current_price, 
                fib_data['levels'], 
                Config.FIB_TOLERANCE
            )
            if is_near:
                fib_resistances.append({
                    'timeframe': timeframe,
                    'level': level_name,
                    'price': level_price
                })
        
        # 최소 1개 타임프레임에서 저항 필요
        fib_signal = len(fib_resistances) >= 1
        
        # 조건 5: 강한 하락 신호
        strong_drop = (
            latest['close'] < prev['high'] and  # 이전 고점보다 낮음
            latest['close'] < latest['open'] and  # 음봉
            (latest['open'] - latest['close']) / latest['open'] > 0.002  # 최소 0.2% 하락
        )
        
        # 조건 6: 캔들 패턴 - 역해머/슈팅스타 패턴 확인
        body = abs(latest['close'] - latest['open'])
        lower_shadow = min(latest['open'], latest['close']) - latest['low']
        upper_shadow = latest['high'] - max(latest['open'], latest['close'])
        
        is_shooting_star = (
            upper_shadow > body * 2 and  # 위 꼬리가 몸통의 2배 이상
            lower_shadow < body * 0.5  # 아래 꼬리가 작음
        )
        
        # 진입 조건:
        # (볼린저 밴드 AND 변동성) AND 
        # (RSI 하락 OR 피보나치) AND 
        # 하락 추세 AND 
        # (강한 하락 OR 슈팅스타 패턴)
        if bb_upper_break and bb_width_ok and (rsi_signal or fib_signal) and downtrend and (strong_drop or is_shooting_star):
            entry_price = current_price
            
            # 레버리지 적용된 손익 계산 (숏은 반대)
            stop_loss_pct = Config.STOP_LOSS_PERCENT / 100
            take_profit_pct = Config.TAKE_PROFIT_PERCENT / 100
            
            # tickSize에 맞게 가격 반올림
            rounded_entry = round(entry_price / tick_size) * tick_size
            rounded_stop = round((entry_price * (1 + stop_loss_pct)) / tick_size) * tick_size  # 숏은 위로
            rounded_take = round((entry_price * (1 - take_profit_pct)) / tick_size) * tick_size  # 숏은 아래로
            
            stop_loss = round(rounded_stop, price_decimals)
            take_profit = round(rounded_take, price_decimals)
            entry_price = round(rounded_entry, price_decimals)
            
            # 예상 손익 (레버리지 적용)
            expected_profit = Config.POSITION_SIZE * take_profit_pct * Config.LEVERAGE
            expected_loss = Config.POSITION_SIZE * stop_loss_pct * Config.LEVERAGE
            
            # 수수료 계산 (진입 + 청산)
            entry_fee = Config.POSITION_SIZE * Config.LEVERAGE * Config.TAKER_FEE
            exit_fee = Config.POSITION_SIZE * Config.LEVERAGE * Config.TAKER_FEE
            total_fee = entry_fee + exit_fee
            
            # 순수익 (수수료 제외)
            net_profit = expected_profit - total_fee
            
            # 최소 수익 조건 확인
            if net_profit >= Config.MIN_PROFIT_TARGET:
                return {
                    'type': 'SHORT',
                    'entry_price': entry_price,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
                    'timestamp': latest['timestamp'],
                    'rsi': latest['rsi'],
                    'bb_position': (current_price - latest['bb_lower']) / (latest['bb_upper'] - latest['bb_lower']),
                    'bb_width': latest['bb_width'],
                    'fib_resistances': fib_resistances,
                    'expected_profit': expected_profit,
                    'expected_loss': expected_loss,
                    'total_fee': total_fee,
                    'net_profit': net_profit,
                    'position_size': Config.POSITION_SIZE,
                    'leverage': Config.LEVERAGE
                }
        
        return None

    
    def _create_long_signal(self, latest, prev, mtf_fib, btc_trend, coin_trend, 
                           funding_info, reason, confidence, symbol, instrument_info):
        """롱 신호 생성 (고급 분석용)"""
        raw_entry_price = latest['close']
        
        # 가격이 0이면 에러
        if raw_entry_price == 0:
            print(f"⚠️  {symbol} 진입가가 0입니다 (latest['close'] = 0)")
            return None
        
        # 레버리지 적용된 손익 계산
        stop_loss_pct = Config.STOP_LOSS_PERCENT / 100
        take_profit_pct = Config.TAKE_PROFIT_PERCENT / 100
        
        # tickSize에 맞게 가격 반올림
        tick_size = instrument_info['tick_size']
        price_decimals = instrument_info['price_decimals']
        
        entry_price = round(raw_entry_price / tick_size) * tick_size
        entry_price = round(entry_price, price_decimals)
        
        # 반올림 후에도 0이면 에러
        if entry_price == 0:
            print(f"⚠️  {symbol} 반올림 후 진입가가 0입니다 (raw: {raw_entry_price}, tick: {tick_size})")
            return None
        
        stop_loss = round((entry_price * (1 - stop_loss_pct)) / tick_size) * tick_size
        stop_loss = round(stop_loss, price_decimals)
        
        take_profit = round((entry_price * (1 + take_profit_pct)) / tick_size) * tick_size
        take_profit = round(take_profit, price_decimals)
        
        # 예상 손익 (레버리지 적용)
        expected_profit = Config.POSITION_SIZE * take_profit_pct * Config.LEVERAGE
        expected_loss = Config.POSITION_SIZE * stop_loss_pct * Config.LEVERAGE
        
        # 수수료 계산 (진입 + 청산)
        entry_fee = Config.POSITION_SIZE * Config.LEVERAGE * Config.TAKER_FEE
        exit_fee = Config.POSITION_SIZE * Config.LEVERAGE * Config.TAKER_FEE
        total_fee = entry_fee + exit_fee
        
        # 순수익 (수수료 제외)
        net_profit = expected_profit - total_fee
        
        if net_profit >= Config.MIN_PROFIT_TARGET:
            return {
                'type': 'LONG',
                'symbol': symbol,
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'timestamp': latest['timestamp'],
                'rsi': latest['rsi'],
                'bb_position': (entry_price - latest['bb_lower']) / (latest['bb_upper'] - latest['bb_lower']),
                'bb_width': latest['bb_width'],
                'expected_profit': expected_profit,
                'expected_loss': expected_loss,
                'total_fee': total_fee,
                'net_profit': net_profit,
                'position_size': Config.POSITION_SIZE,
                'leverage': Config.LEVERAGE,
                'btc_trend': btc_trend,
                'coin_trend': coin_trend,
                'funding_info': funding_info,
                'trend_reason': reason,
                'confidence': confidence,
                'strategy': 'ADVANCED'
            }
        return None
    
    def _create_short_signal(self, latest, prev, mtf_fib, btc_trend, coin_trend, 
                            funding_info, reason, confidence, symbol, instrument_info):
        """숏 신호 생성 (고급 분석용)"""
        raw_entry_price = latest['close']
        
        # 가격이 0이면 에러
        if raw_entry_price == 0:
            print(f"⚠️  {symbol} 진입가가 0입니다 (latest['close'] = 0)")
            return None
        
        # 레버리지 적용된 손익 계산 (숏은 반대)
        stop_loss_pct = Config.STOP_LOSS_PERCENT / 100
        take_profit_pct = Config.TAKE_PROFIT_PERCENT / 100
        
        # tickSize에 맞게 가격 반올림
        tick_size = instrument_info['tick_size']
        price_decimals = instrument_info['price_decimals']
        
        entry_price = round(raw_entry_price / tick_size) * tick_size
        entry_price = round(entry_price, price_decimals)
        
        # 반올림 후에도 0이면 에러
        if entry_price == 0:
            print(f"⚠️  {symbol} 반올림 후 진입가가 0입니다 (raw: {raw_entry_price}, tick: {tick_size})")
            return None
        
        stop_loss = round((entry_price * (1 + stop_loss_pct)) / tick_size) * tick_size  # 숏은 위로
        stop_loss = round(stop_loss, price_decimals)
        
        take_profit = round((entry_price * (1 - take_profit_pct)) / tick_size) * tick_size  # 숏은 아래로
        take_profit = round(take_profit, price_decimals)
        
        # 예상 손익 (레버리지 적용)
        expected_profit = Config.POSITION_SIZE * take_profit_pct * Config.LEVERAGE
        expected_loss = Config.POSITION_SIZE * stop_loss_pct * Config.LEVERAGE
        
        # 수수료 계산 (진입 + 청산)
        entry_fee = Config.POSITION_SIZE * Config.LEVERAGE * Config.TAKER_FEE
        exit_fee = Config.POSITION_SIZE * Config.LEVERAGE * Config.TAKER_FEE
        total_fee = entry_fee + exit_fee
        
        # 순수익 (수수료 제외)
        net_profit = expected_profit - total_fee
        
        if net_profit >= Config.MIN_PROFIT_TARGET:
            return {
                'type': 'SHORT',
                'symbol': symbol,
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'timestamp': latest['timestamp'],
                'rsi': latest['rsi'],
                'bb_position': (entry_price - latest['bb_lower']) / (latest['bb_upper'] - latest['bb_lower']),
                'bb_width': latest['bb_width'],
                'expected_profit': expected_profit,
                'expected_loss': expected_loss,
                'total_fee': total_fee,
                'net_profit': net_profit,
                'position_size': Config.POSITION_SIZE,
                'leverage': Config.LEVERAGE,
                'btc_trend': btc_trend,
                'coin_trend': coin_trend,
                'funding_info': funding_info,
                'trend_reason': reason,
                'confidence': confidence,
                'strategy': 'ADVANCED'
            }
        return None
