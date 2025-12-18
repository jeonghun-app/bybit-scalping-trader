"""
Volatility Ranker
실시간 변동성 랭킹 관리
"""
import logging
from typing import Dict, List, Tuple
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)


class VolatilityRanker:
    """변동성 기반 코인 랭킹"""
    
    def __init__(self):
        self.symbols: Dict[str, dict] = {}
        self.volume_history: Dict[str, List[float]] = defaultdict(list)
        self.last_update = datetime.now()
        
    def update(self, symbol: str, change_pct: float, volume_24h: float, price: float):
        """심볼 정보 업데이트"""
        self.symbols[symbol] = {
            "change_pct": abs(change_pct),
            "volume_24h": volume_24h,
            "price": price,
            "last_update": datetime.now()
        }
        
        # 거래량 히스토리 저장 (최근 100개)
        self.volume_history[symbol].append(volume_24h)
        if len(self.volume_history[symbol]) > 100:
            self.volume_history[symbol].pop(0)
    
    def get_top_n(self, n: int = 50) -> List[str]:
        """상위 N개 심볼 반환 (변동성 기준)"""
        if not self.symbols:
            return []
        
        # 변동성 기준 정렬
        sorted_symbols = sorted(
            self.symbols.items(),
            key=lambda x: (x[1]["change_pct"], x[1]["volume_24h"]),
            reverse=True
        )
        
        top_symbols = [symbol for symbol, _ in sorted_symbols[:n]]
        
        logger.info(f"🔝 Top {len(top_symbols)} 선정 완료")
        return top_symbols
    
    def get_rank(self, symbol: str) -> int:
        """특정 심볼의 순위 반환"""
        if symbol not in self.symbols:
            return -1
        
        sorted_symbols = sorted(
            self.symbols.items(),
            key=lambda x: x[1]["change_pct"],
            reverse=True
        )
        
        for rank, (sym, _) in enumerate(sorted_symbols, 1):
            if sym == symbol:
                return rank
        
        return -1
    
    def get_volume_spike(self, symbol: str) -> float:
        """거래량 스파이크 배수 계산"""
        if symbol not in self.symbols:
            return 0.0
        
        history = self.volume_history.get(symbol, [])
        if len(history) < 10:
            return 1.0
        
        current_volume = self.symbols[symbol]["volume_24h"]
        avg_volume = sum(history[:-1]) / len(history[:-1])
        
        if avg_volume == 0:
            return 1.0
        
        spike = current_volume / avg_volume
        return round(spike, 2)
    
    def get_symbol_info(self, symbol: str) -> dict:
        """심볼 정보 조회"""
        return self.symbols.get(symbol, {})
    
    def get_total_symbols(self) -> int:
        """전체 심볼 수"""
        return len(self.symbols)
    
    def cleanup_old_symbols(self, max_age_seconds: int = 300):
        """오래된 심볼 정리"""
        now = datetime.now()
        to_remove = []
        
        for symbol, info in self.symbols.items():
            age = (now - info["last_update"]).total_seconds()
            if age > max_age_seconds:
                to_remove.append(symbol)
        
        for symbol in to_remove:
            del self.symbols[symbol]
            if symbol in self.volume_history:
                del self.volume_history[symbol]
        
        if to_remove:
            logger.info(f"🧹 {len(to_remove)}개 오래된 심볼 정리")
