"""
Orderbook Analyzer
호가장 불균형 분석
"""
import logging
from typing import Dict
from datetime import datetime

logger = logging.getLogger(__name__)


class OrderbookAnalyzer:
    """호가장 불균형 분석기"""
    
    def __init__(self):
        self.orderbooks: Dict[str, dict] = {}
        
    def update(self, symbol: str, bookticker_data: dict):
        """Bookticker 데이터 업데이트"""
        try:
            bid_price = float(bookticker_data.get("bp", 0))
            bid_qty = float(bookticker_data.get("bq", 0))
            ask_price = float(bookticker_data.get("ap", 0))
            ask_qty = float(bookticker_data.get("aq", 0))
            
            self.orderbooks[symbol] = {
                "bid_price": bid_price,
                "bid_qty": bid_qty,
                "ask_price": ask_price,
                "ask_qty": ask_qty,
                "timestamp": datetime.now()
            }
            
        except Exception as e:
            logger.error(f"Bookticker 업데이트 오류 ({symbol}): {e}")
    
    def get_imbalance(self, symbol: str) -> float:
        """
        호가 불균형 지수 계산
        
        Returns:
            -1.0 ~ 1.0
            양수: 매수 우위
            음수: 매도 우위
        """
        if symbol not in self.orderbooks:
            return 0.0
        
        ob = self.orderbooks[symbol]
        bid_qty = ob["bid_qty"]
        ask_qty = ob["ask_qty"]
        
        total = bid_qty + ask_qty
        if total == 0:
            return 0.0
        
        # 매수 비율 - 매도 비율
        imbalance = (bid_qty - ask_qty) / total
        
        return round(imbalance, 3)
    
    def get_spread_pct(self, symbol: str) -> float:
        """스프레드 비율 계산"""
        if symbol not in self.orderbooks:
            return 0.0
        
        ob = self.orderbooks[symbol]
        bid_price = ob["bid_price"]
        ask_price = ob["ask_price"]
        
        if bid_price == 0:
            return 0.0
        
        spread_pct = ((ask_price - bid_price) / bid_price) * 100
        return round(spread_pct, 4)
    
    def get_mid_price(self, symbol: str) -> float:
        """중간 가격 계산"""
        if symbol not in self.orderbooks:
            return 0.0
        
        ob = self.orderbooks[symbol]
        return (ob["bid_price"] + ob["ask_price"]) / 2
    
    def is_liquid(self, symbol: str, min_qty: float = 1000) -> bool:
        """유동성 체크"""
        if symbol not in self.orderbooks:
            return False
        
        ob = self.orderbooks[symbol]
        return ob["bid_qty"] >= min_qty and ob["ask_qty"] >= min_qty
    
    def get_orderbook_info(self, symbol: str) -> dict:
        """호가장 정보 조회"""
        return self.orderbooks.get(symbol, {})
