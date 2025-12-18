"""
실시간 데이터 처리 및 신호 감지
"""
import logging
from datetime import datetime
from typing import Dict, List

from squeeze_detector import SqueezeDetector
from orderbook_analyzer import OrderbookAnalyzer
from volatility_ranker import VolatilityRanker
from signal_emitter import SignalEmitter

logger = logging.getLogger(__name__)


class DataProcessor:
    """실시간 데이터 처리 및 신호 감지"""
    
    def __init__(self):
        self.squeeze_detector = SqueezeDetector()
        self.ob_analyzer = OrderbookAnalyzer()
        self.ranker = VolatilityRanker()
        self.signal_emitter = SignalEmitter()
        self.scanner_id = None
        self.stats = {
            "total_opportunities_sent": 0,
            "total_tickers_processed": 0,
            "total_candles_processed": 0
        }
    
    async def initialize(self):
        """데이터 프로세서 초기화"""
        await self.signal_emitter.initialize()
    
    def set_scanner_id(self, scanner_id: str):
        """Scanner ID 설정"""
        self.scanner_id = scanner_id
    
    async def process_ticker(self, topic: str, data: dict):
        """티커 데이터 처리"""
        try:
            logger.info(f"🔔 TICKER 메시지 수신: {topic}")
            ticker = data.get("data", {})
            if not ticker:
                return
            
            symbol = ticker.get("symbol", "")
            price = float(ticker.get("lastPrice", 0))
            volume_24h = float(ticker.get("volume24h", 0))
            change_pct = float(ticker.get("price24hPcnt", 0)) * 100
            
            # 가격 업데이트
            # self.hawk_detector.update_price(symbol, price)
            
            # 볼륨 업데이트  
            # self.hawk_detector.update_volume(symbol, volume_24h, change_pct)
            
            self.stats["total_tickers_processed"] += 1
            
        except Exception as e:
            logger.error(f"티커 처리 오류: {e}")
    
    async def process_bookticker(self, topic: str, data: dict):
        """호가 데이터 처리"""
        try:
            logger.info(f"🔔 BOOKTICKER 메시지 수신: {topic}")
            ticker_data = data.get("data", {})
            symbol = ticker_data.get("s", "")
            
            # 호가 데이터 업데이트
            self.ob_analyzer.update(symbol, ticker_data)
            
            # 호가 불균형 체크
            imbalance = self.ob_analyzer.get_imbalance(symbol)
            if abs(imbalance) > 0.7:  # 70% 이상 불균형
                await self._emit_opportunity(symbol, "ORDERBOOK_IMBALANCE", abs(imbalance))
            
        except Exception as e:
            logger.error(f"Bookticker 처리 오류: {e}")
    
    async def process_candle(self, topic: str, data: dict):
        """캔들 데이터 처리"""
        try:
            logger.info(f"🔔 CANDLE 메시지 수신: {topic}")
            candle_data = data.get("data", [])
            if not candle_data:
                return
            
            for candle in candle_data:
                symbol = candle.get("symbol", "")
                close_price = float(candle.get("close", 0))
                volume = float(candle.get("volume", 0))
                
                # BB 슈쿼즈 체크
                is_squeeze = self.squeeze_detector.update(symbol, close_price)
                if is_squeeze:
                    confidence = self.squeeze_detector.get_confidence(symbol)
                    await self._emit_opportunity(symbol, "BB_SQUEEZE", confidence)
                
                # Hawk 신호 체크 (주석 처리됨)
                # hawk_signal = self.hawk_detector.check_signal(symbol, price)
                
                self.stats["total_candles_processed"] += 1
            
        except Exception as e:
            logger.error(f"캔들 처리 오류: {e}")
    
    async def _emit_opportunity(self, symbol: str, signal_type: str, score: float):
        """기회 신호 발행"""
        try:
            opportunity = {
                "symbol": symbol,
                "signal_type": signal_type,
                "score": score,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "scanner_id": self.scanner_id
            }
            
            success = await self.signal_emitter.send_opportunity(opportunity)
            
            if success:
                self.stats["total_opportunities_sent"] += 1
                logger.info(f"🚀 기회 발행: {symbol} | {signal_type} | {score:.2f}")
            
        except Exception as e:
            logger.error(f"기회 발행 오류: {e}")
    
    def get_stats(self) -> Dict:
        """통계 조회"""
        return self.stats.copy()
