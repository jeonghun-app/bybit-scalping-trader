"""
Scanner Service 설정
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Scanner 설정"""
    
    # Bybit WebSocket
    BYBIT_WS_URL = os.getenv("BYBIT_WS_URL", "wss://stream.bybit.com/v5/public/linear")
    
    # WebSocket 설정
    WS_TIMEOUT = 60  # 타임아웃 (초)
    WS_PING_INTERVAL = 20  # Ping 간격 (초)
    WS_RECONNECT_DELAY = 5  # 재연결 대기 (초)
    
    # Redis 설정
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    
    # RabbitMQ 설정
    RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
    RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
    RABBITMQ_USER = os.getenv("RABBITMQ_USER", "admin")
    RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "password")
    RABBITMQ_USE_SSL = os.getenv("RABBITMQ_USE_SSL", "false").lower() == "true"
    RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "opportunity-queue")
    
    # Scanner 설정
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    SCAN_INTERVAL_SEC = int(os.getenv("SCAN_INTERVAL_SEC", "1"))
    ACTIVE_SYMBOLS_LIMIT = int(os.getenv("ACTIVE_SYMBOLS_LIMIT", "50"))
    TICKER_UPDATE_INTERVAL = 30  # 티커 업데이트 간격 (초)
    
    # 필터 기준
    MIN_VOLUME_24H = float(os.getenv("MIN_VOLUME_24H", "1000000"))
    MIN_VOLATILITY_PCT = float(os.getenv("MIN_VOLATILITY_PCT", "2.0"))
    BB_SQUEEZE_THRESHOLD = float(os.getenv("BB_SQUEEZE_THRESHOLD", "0.9"))
    OB_IMBALANCE_THRESHOLD = float(os.getenv("OB_IMBALANCE_THRESHOLD", "0.7"))
    VOLUME_SPIKE_MULTIPLIER = float(os.getenv("VOLUME_SPIKE_MULTIPLIER", "3.0"))
    
    # Bollinger Bands 설정
    BB_WINDOW = int(os.getenv("BB_WINDOW", "20"))
    BB_STD_DEV = float(os.getenv("BB_STD_DEV", "2.0"))
    
    # 제외 패턴
    STABLECOINS = ["USDC", "USDT", "BUSD", "DAI", "TUSD"]
    EXCLUDED_PATTERNS = ["UP", "DOWN", "BEAR", "BULL"]
    
    # 메트릭스
    ENABLE_METRICS = os.getenv("ENABLE_METRICS", "true").lower() == "true"
    METRICS_INTERVAL = int(os.getenv("METRICS_INTERVAL", "60"))
