#!/usr/bin/env python3
"""
백테스팅 결과를 반대로 투자했을 때의 성과 분석
"""
import pandas as pd
import sys

def analyze_inverse_trades(csv_file):
    """반대 포지션 분석"""
    df = pd.read_csv(csv_file)
    
    # 반대 포지션 계산
    # gross_pnl의 부호를 반대로 (수수료는 동일)
    df['inverse_gross_pnl'] = -df['gross_pnl']
    df['inverse_net_pnl'] = df['inverse_gross_pnl'] - df['fees']
    df['inverse_result'] = df['inverse_net_pnl'].apply(lambda x: 'WIN' if x > 0 else 'LOSS')
    
    # 전체 통계
    total_trades = len(df)
    wins = len(df[df['inverse_result'] == 'WIN'])
    losses = len(df[df['inverse_result'] == 'LOSS'])
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    
    total_pnl = df['inverse_net_pnl'].sum()
    initial_capital = 1000.0
    final_capital = initial_capital + total_pnl
    roi = (total_pnl / initial_capital * 100)
    
    print(f"\n{'='*80}")
    print(f"반대 포지션 분석: {csv_file}")
    print(f"{'='*80}")
    print(f"\n📊 전체 통계")
    print(f"총 거래 수: {total_trades}")
    print(f"승리: {wins} | 패배: {losses}")
    print(f"승률: {win_rate:.2f}%")
    print(f"\n💰 수익 통계")
    print(f"총 순수익: ${total_pnl:.2f}")
    print(f"초기 자본: ${initial_capital:.2f}")
    print(f"최종 자본: ${final_capital:.2f}")
    print(f"ROI: {roi:.2f}%")
    
    # 심볼별 분석
    print(f"\n📈 심볼별 성과:")
    symbol_stats = df.groupby('symbol').agg({
        'inverse_net_pnl': ['sum', 'mean', 'count'],
        'inverse_result': lambda x: (x == 'WIN').sum()
    }).round(2)
    
    symbol_stats.columns = ['총수익', '평균수익', '거래수', '승리수']
    symbol_stats['승률%'] = (symbol_stats['승리수'] / symbol_stats['거래수'] * 100).round(2)
    symbol_stats = symbol_stats.sort_values('총수익', ascending=False)
    
    print(symbol_stats.to_string())
    
    # 원래 vs 반대 비교
    original_total = df['net_pnl'].sum()
    original_wins = len(df[df['result'] == 'WIN'])
    original_win_rate = (original_wins / total_trades * 100) if total_trades > 0 else 0
    
    print(f"\n{'='*80}")
    print(f"📊 원래 전략 vs 반대 전략 비교")
    print(f"{'='*80}")
    print(f"\n{'지표':<20} {'원래 전략':>15} {'반대 전략':>15} {'차이':>15}")
    print(f"{'-'*70}")
    print(f"{'총 수익':<20} ${original_total:>14.2f} ${total_pnl:>14.2f} ${total_pnl - original_total:>14.2f}")
    print(f"{'승률':<20} {original_win_rate:>14.2f}% {win_rate:>14.2f}% {win_rate - original_win_rate:>14.2f}%")
    print(f"{'ROI':<20} {(original_total/initial_capital*100):>14.2f}% {roi:>14.2f}% {roi - (original_total/initial_capital*100):>14.2f}%")
    print(f"{'최종 자본':<20} ${initial_capital + original_total:>14.2f} ${final_capital:>14.2f} ${final_capital - (initial_capital + original_total):>14.2f}")
    
    # 심볼별 비교
    print(f"\n📊 심볼별 원래 vs 반대 비교")
    print(f"{'='*80}")
    
    original_by_symbol = df.groupby('symbol')['net_pnl'].sum()
    inverse_by_symbol = df.groupby('symbol')['inverse_net_pnl'].sum()
    
    comparison = pd.DataFrame({
        '원래': original_by_symbol,
        '반대': inverse_by_symbol,
        '차이': inverse_by_symbol - original_by_symbol
    }).round(2).sort_values('차이', ascending=False)
    
    print(comparison.to_string())
    
    return {
        'total_pnl': total_pnl,
        'win_rate': win_rate,
        'roi': roi,
        'final_capital': final_capital,
        'original_pnl': original_total,
        'original_win_rate': original_win_rate
    }

if __name__ == "__main__":
    print("\n" + "🔄"*40)
    print("반대 포지션 분석 - 만약 모든 거래를 반대로 했다면?")
    print("🔄"*40)
    
    # 1분봉 분석
    print("\n\n" + "🔵"*40)
    print("1분봉 백테스팅 - 반대 포지션")
    print("🔵"*40)
    result_1m = analyze_inverse_trades('backtest_trades_20251217_030714.csv')
    
    # 3분봉 분석
    print("\n\n" + "🟢"*40)
    print("3분봉 백테스팅 - 반대 포지션")
    print("🟢"*40)
    result_3m = analyze_inverse_trades('backtest_trades_20251217_030743.csv')
    
    # 최종 요약
    print("\n\n" + "="*80)
    print("🎯 최종 요약")
    print("="*80)
    
    print(f"\n1분봉:")
    print(f"  원래 전략: ROI {(result_1m['original_pnl']/1000*100):.2f}% (${1000 + result_1m['original_pnl']:.2f})")
    print(f"  반대 전략: ROI {result_1m['roi']:.2f}% (${result_1m['final_capital']:.2f})")
    print(f"  차이: {result_1m['roi'] - (result_1m['original_pnl']/1000*100):.2f}%p")
    
    print(f"\n3분봉:")
    print(f"  원래 전략: ROI {(result_3m['original_pnl']/1000*100):.2f}% (${1000 + result_3m['original_pnl']:.2f})")
    print(f"  반대 전략: ROI {result_3m['roi']:.2f}% (${result_3m['final_capital']:.2f})")
    print(f"  차이: {result_3m['roi'] - (result_3m['original_pnl']/1000*100):.2f}%p")
    
    print("\n" + "="*80)
