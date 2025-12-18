"""
타임프레임 비교 백테스트
1분, 3분, 5분봉을 각각 테스트하여 최적의 타임프레임 찾기
"""
from src.backtesting.backtest_engine import BacktestEngine
from config.config import Config
import pandas as pd

def compare_timeframes():
    """1분, 3분, 5분봉 비교 백테스트"""
    
    timeframes = ['1', '3', '5']
    results = {}
    
    print(f"\n{'='*80}")
    print("타임프레임 비교 백테스트 (1분 vs 3분 vs 5분)")
    print(f"{'='*80}\n")
    
    for tf in timeframes:
        print(f"\n{'🔵'*40}")
        print(f"{tf}분봉 백테스팅")
        print(f"{'🔵'*40}\n")
        
        # 백테스트 실행
        engine = BacktestEngine()
        engine.run_backtest(candles=Config.BACKTEST_CANDLES, timeframe=tf)
        
        # 결과 저장
        if engine.trades:
            df = pd.DataFrame(engine.trades)
            
            total_trades = len(df)
            wins = len(df[df['result'] == 'WIN'])
            win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
            total_pnl = df['net_pnl'].sum()
            avg_win = df[df['result'] == 'WIN']['net_pnl'].mean() if wins > 0 else 0
            avg_loss = df[df['result'] == 'LOSS']['net_pnl'].mean() if total_trades > wins else 0
            
            # 심볼별 성과
            symbol_pnl = df.groupby('symbol')['net_pnl'].sum().to_dict()
            
            results[tf] = {
                'total_trades': total_trades,
                'wins': wins,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'symbol_pnl': symbol_pnl,
                'trades_df': df
            }
        else:
            results[tf] = {
                'total_trades': 0,
                'wins': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'symbol_pnl': {},
                'trades_df': pd.DataFrame()
            }
    
    # 비교 결과 출력
    print(f"\n{'='*80}")
    print("📊 타임프레임 비교 결과")
    print(f"{'='*80}\n")
    
    # 전체 비교표
    print("전체 성과 비교:")
    print(f"{'타임프레임':<10} {'거래수':<10} {'승률':<10} {'총수익':<15} {'평균승리':<12} {'평균손실':<12}")
    print("-" * 80)
    
    for tf in timeframes:
        r = results[tf]
        print(f"{tf}분봉{'':<6} {r['total_trades']:<10} {r['win_rate']:<9.2f}% ${r['total_pnl']:<14.2f} ${r['avg_win']:<11.2f} ${r['avg_loss']:<11.2f}")
    
    # 최고 성과 타임프레임
    best_tf = max(results.keys(), key=lambda x: results[x]['total_pnl'])
    print(f"\n🏆 최고 성과: {best_tf}분봉 (${results[best_tf]['total_pnl']:.2f})")
    
    # 심볼별 최적 타임프레임
    print(f"\n{'='*80}")
    print("📈 심볼별 최적 타임프레임")
    print(f"{'='*80}\n")
    
    # 모든 심볼 수집
    all_symbols = set()
    for tf in timeframes:
        all_symbols.update(results[tf]['symbol_pnl'].keys())
    
    symbol_best = {}
    
    print(f"{'심볼':<15} {'1분봉':<15} {'3분봉':<15} {'5분봉':<15} {'최적':<10}")
    print("-" * 80)
    
    for symbol in sorted(all_symbols):
        pnl_1 = results['1']['symbol_pnl'].get(symbol, 0)
        pnl_3 = results['3']['symbol_pnl'].get(symbol, 0)
        pnl_5 = results['5']['symbol_pnl'].get(symbol, 0)
        
        best = max([('1', pnl_1), ('3', pnl_3), ('5', pnl_5)], key=lambda x: x[1])
        symbol_best[symbol] = best[0]
        
        print(f"{symbol:<15} ${pnl_1:<14.2f} ${pnl_3:<14.2f} ${pnl_5:<14.2f} {best[0]}분봉")
    
    # 인사이트
    print(f"\n{'='*80}")
    print("💡 주요 인사이트")
    print(f"{'='*80}\n")
    
    # 1분봉이 좋은 코인
    best_1min = [s for s, tf in symbol_best.items() if tf == '1']
    if best_1min:
        print(f"✅ 1분봉 최적 코인 ({len(best_1min)}개): {', '.join(best_1min)}")
        print(f"   특징: 빠른 변동성, 단기 스캘핑에 적합")
    
    # 3분봉이 좋은 코인
    best_3min = [s for s, tf in symbol_best.items() if tf == '3']
    if best_3min:
        print(f"✅ 3분봉 최적 코인 ({len(best_3min)}개): {', '.join(best_3min)}")
        print(f"   특징: 중간 변동성, 노이즈 필터링")
    
    # 5분봉이 좋은 코인
    best_5min = [s for s, tf in symbol_best.items() if tf == '5']
    if best_5min:
        print(f"✅ 5분봉 최적 코인 ({len(best_5min)}개): {', '.join(best_5min)}")
        print(f"   특징: 안정적 추세, 장기 포지션")
    
    # 타임프레임별 특성 분석
    print(f"\n타임프레임별 특성:")
    for tf in timeframes:
        r = results[tf]
        if r['total_trades'] > 0:
            avg_bars = r['trades_df']['bars_held'].mean() if not r['trades_df'].empty else 0
            avg_time_minutes = avg_bars * int(tf)
            print(f"  {tf}분봉: 평균 보유 {avg_bars:.1f}봉 ({avg_time_minutes:.0f}분), "
                  f"승률 {r['win_rate']:.1f}%, 수익 ${r['total_pnl']:.2f}")
    
    # 권장 사항
    print(f"\n🎯 권장 사항:")
    if results[best_tf]['win_rate'] > 45:
        print(f"  ✅ {best_tf}분봉 사용 권장 (승률 {results[best_tf]['win_rate']:.1f}%, 수익 ${results[best_tf]['total_pnl']:.2f})")
    else:
        print(f"  ⚠️  모든 타임프레임에서 승률 낮음 → 전략 재검토 필요")
    
    # 혼합 전략 제안
    print(f"\n💡 혼합 전략 (코인별 최적 타임프레임 사용):")
    mixed_pnl = sum(max(results['1']['symbol_pnl'].get(s, 0),
                        results['3']['symbol_pnl'].get(s, 0),
                        results['5']['symbol_pnl'].get(s, 0))
                    for s in all_symbols)
    print(f"  예상 수익: ${mixed_pnl:.2f}")
    print(f"  개선율: {(mixed_pnl / results[best_tf]['total_pnl'] - 1) * 100:.1f}%")
    
    # CSV 저장
    comparison_data = []
    for tf in timeframes:
        r = results[tf]
        comparison_data.append({
            'timeframe': f"{tf}분",
            'total_trades': r['total_trades'],
            'win_rate': r['win_rate'],
            'total_pnl': r['total_pnl'],
            'avg_win': r['avg_win'],
            'avg_loss': r['avg_loss']
        })
    
    comparison_df = pd.DataFrame(comparison_data)
    comparison_df.to_csv('timeframe_comparison.csv', index=False)
    print(f"\n비교 결과가 timeframe_comparison.csv에 저장되었습니다.")
    
    return results

if __name__ == "__main__":
    compare_timeframes()
