import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Bybit API 설정
    BYBIT_API_KEY = os.getenv('BYBIT_API_KEY', '')
    BYBIT_API_SECRET = os.getenv('BYBIT_API_SECRET', '')
    BYBIT_TESTNET = os.getenv('BYBIT_TESTNET', 'True') == 'True'
    
    # 백테스팅 설정
    BACKTEST_CANDLES = 1000  # 백테스팅할 캔들 수
    ENTRY_TIMEFRAME = '3'  # 진입 타임프레임 (1분 또는 3분)
    
    # 멀티 타임프레임 피보나치 설정 (interval: days)
    FIBONACCI_TIMEFRAMES = {
        '5': 1,    # 5분봉: 1일
        '15': 2,   # 15분봉: 2일
        '30': 5,   # 30분봉: 5일
        '240': 7,  # 4시간봉: 7일
        'D': 30    # 1일봉: 30일
    }
    
    # 변동성 스캐닝 설정
    MIN_VOLATILITY = 5.0  # 최소 변동성 (24h 변동폭 %)
    MAX_VOLATILITY = 50.0  # 최대 변동성 (너무 높으면 예측 불가) - 신규
    TOP_VOLATILE_COINS = 20
    TOP_BACKTEST_COINS = 10  # 백테스팅할 코인 수
    
    # 볼린저 밴드 설정
    BB_PERIOD = 20
    BB_STD = 2
    
    # 피보나치 레벨 (진입 신호용)
    FIB_ENTRY_LEVELS = [0.382, 0.5, 0.618, 0.786]  # 주요 지지선
    FIB_TOLERANCE = 0.02  # 2% 허용 오차
    
    # 자금 관리
    INITIAL_CAPITAL = 1000.0  # 초기 자본 ($)
    POSITION_SIZE = 100.0     # 포지션당 투자금 ($)
    MAX_POSITIONS = 10        # 최대 동시 포지션 수
    
    # 리스크 관리 (단타용) - 손익비 2:1 이상
    MIN_PROFIT_TARGET = 7.0   # 최소 목표 수익 ($)
    STOP_LOSS_PERCENT = 1.0   # 스탑로스 (%)
    TAKE_PROFIT_PERCENT = 2.0 # 익절 (%) - 1.5% → 2.0% (손익비 개선)
    
    # 수수료 (Bybit 선물 기준)
    MAKER_FEE = 0.0002  # 0.02%
    TAKER_FEE = 0.0006  # 0.06%
    
    # 레버리지
    LEVERAGE = 10  # 10배 레버리지
    
    # 스케줄링
    SCAN_INTERVAL_MINUTES = 5  # 스캔 주기 (분) - 단타용
