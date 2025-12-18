#!/usr/bin/env python3
"""
백테스팅 메인 스크립트
로컬에서 직접 실행 가능

사용법:
  python main_backtest.py                    # 자동 스캔 + 1분봉/3분봉 백테스팅
  python main_backtest.py --compare          # 1분/3분/5분 비교 분석
  python main_backtest.py BTCUSDT ETHUSDT    # 특정 심볼 백테스팅
"""
import sys
from src.backtesting.backtest_engine import BacktestEngine
from config.config import Config

def main():
    print("="*80)
    print("Bybit 단타 트레이딩 봇 - 백테스팅 모드")
    print("="*80)
    print(f"테스트넷: {Config.BYBIT_TESTNET}")
    print(f"포지션 크기: ${Config.POSITION_SIZE} (레버리지 {Config.LEVERAGE}x)")
    print(f"목표 수익: ${Config.MIN_PROFIT_TARGET} 이상")
    print(f"캔들 수: {Config.BACKTEST_CANDLES}개")
    print("="*80)
    
    # 타임프레임 비교 모드
    if len(sys.argv) > 1 and sys.argv[1] == '--compare':
        print("\n🔍 타임프레임 비교 모드")
        from compare_timeframes import compare_timeframes
        compare_timeframes()
        return
    
    # 명령줄 인자로 심볼 지정 가능
    symbols = None
    if len(sys.argv) > 1:
        symbols = sys.argv[1:]
        print(f"\n지정된 심볼: {symbols}")
    
    # 1분봉 백테스팅
    print("\n" + "🔵"*40)
    print("1분봉 백테스팅")
    print("🔵"*40)
    engine_1m = BacktestEngine()
    engine_1m.run_backtest(symbols=symbols, candles=Config.BACKTEST_CANDLES, timeframe='1')
    
    # 3분봉 백테스팅
    print("\n" + "🟢"*40)
    print("3분봉 백테스팅")
    print("🟢"*40)
    engine_3m = BacktestEngine()
    engine_3m.run_backtest(symbols=symbols, candles=Config.BACKTEST_CANDLES, timeframe='3')
    
    print("\n✅ 모든 백테스팅 완료!")
    print("\n💡 Tip: 타임프레임 비교 분석을 원하면 'python main_backtest.py --compare' 실행")

if __name__ == "__main__":
    main()
