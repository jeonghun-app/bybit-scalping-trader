"""
신호 발행기 - 실시간 거래 실행
"""
import json
import logging
from datetime import datetime
from core.trading_executor import TradingExecutor

logger = logging.getLogger(__name__)

class SignalEmitter:
    """기회 신호를 감지하면 즉시 거래 실행"""
    
    def __init__(self):
        self.executor = TradingExecutor()
        self.initialized = False
        
    async def initialize(self):
        """거래 실행기 초기화"""
        try:
            await self.executor.initialize()
            self.initialized = True
            logger.info("✅ SignalEmitter 초기화 완료")
        except Exception as e:
            logger.error(f"❌ SignalEmitter 초기화 실패: {e}")
            self.initialized = False
    
    async def send_opportunity(self, opportunity: dict) -> bool:
        """기회 감지 시 즉시 거래 실행"""
        if not self.initialized:
            logger.warning("거래 실행기 초기화되지 않음")
            return False
            
        try:
            symbol = opportunity.get('symbol')
            signal_type = opportunity.get('signal_type')
            score = opportunity.get('score', 0.0)
            
            # 즉시 거래 실행
            await self.executor.execute_trade(symbol, signal_type, score)
            
            return True
            
        except Exception as e:
            logger.error(f"거래 실행 오류: {e}")
            return False
    
    def close(self):
        """정리"""
        pass
