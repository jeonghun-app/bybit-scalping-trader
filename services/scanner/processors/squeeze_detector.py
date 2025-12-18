"""
Bollinger Band Squeeze Detector
볼린저 밴드 슈쿼즈 감지
"""
import logging
import numpy as np
from collections import deque
from typing import Dict, Optional

from config.settings import Config

logger = logging.getLogger(__name__)


class SqueezeDetector:
    """볼린저 밴드 슈쿼즈 감지기"""
    
    def __init__(self, window: int = Config.BB_WINDOW, std_dev: float = Config.BB_STD_DEV):
        self.window = window
        self.std_dev = std_dev
        self.prices: Dict[str, deque] = {}
        self.squeeze_scores: Dict[str, float] = {}
        self.max_widths: Dict[str, float] = {}
        self.prev_widths: Dict[str, deque] = {}
        
    def update(self, symbol: str, price: float) -> bool:
        """가격 업데이트 및 슈쿼즈 감지"""
        # 초기화
        if symbol not in self.prices:
            self.prices[symbol] = deque(maxlen=self.window * 2)
            self.squeeze_scores[symbol] = 0.0
            self.max_widths[symbol] = 0.0
            self.prev_widths[symbol] = deque(maxlen=5)
        
        self.prices[symbol].append(price)
        
        # 최소 데이터 필요
        if len(self.prices[symbol]) < self.window:
            return False
        
        # 볼린저 밴드 계산
        prices_array = np.array(list(self.prices[symbol]))
        recent_prices = prices_array[-self.window:]
        
        middle = np.mean(recent_prices)
        std = np.std(recent_prices)
        
        if middle == 0:
            return False
        
        upper = middle + self.std_dev * std
        lower = middle - self.std_dev * std
        width = (upper - lower) / middle
        
        # 최대 폭 업데이트
        if width > self.max_widths[symbol]:
            self.max_widths[symbol] = width
        
        # 폭 히스토리 저장
        self.prev_widths[symbol].append(width)
        
        # 슈쿼즈 비율 계산
        max_width = self.max_widths[symbol]
        if max_width == 0:
            return False
        
        squeeze_ratio = width / max_width
        
        # 확장 추세 감지
        is_expanding = False
        if len(self.prev_widths[symbol]) >= 3:
            recent_widths = list(self.prev_widths[symbol])
            is_expanding = recent_widths[-1] > recent_widths[-2] > recent_widths[-3]
        
        # 슈쿼즈 해제 조건
        # 1. 밴드가 매우 좁았음 (squeeze_ratio < 0.2)
        # 2. 지금 확장 중
        is_squeezed = squeeze_ratio < 0.2
        
        if is_squeezed and is_expanding:
            confidence = (1 - squeeze_ratio)
            self.squeeze_scores[symbol] = confidence
            
            logger.info(
                f"🎯 슈쿼즈 해제 감지: {symbol} "
                f"(ratio: {squeeze_ratio:.3f}, conf: {confidence:.3f})"
            )
            return True
        
        return False
    
    def get_confidence(self, symbol: str) -> float:
        """슈쿼즈 신뢰도 반환 (0~1)"""
        return self.squeeze_scores.get(symbol, 0.0)
    
    def get_current_width_ratio(self, symbol: str) -> Optional[float]:
        """현재 밴드 폭 비율"""
        if symbol not in self.prices or len(self.prices[symbol]) < self.window:
            return None
        
        prices_array = np.array(list(self.prices[symbol]))
        recent_prices = prices_array[-self.window:]
        
        middle = np.mean(recent_prices)
        std = np.std(recent_prices)
        
        if middle == 0:
            return None
        
        width = (2 * self.std_dev * std) / middle
        max_width = self.max_widths.get(symbol, width)
        
        if max_width == 0:
            return None
        
        return width / max_width
    
    def reset(self, symbol: str):
        """특정 심볼 데이터 초기화"""
        if symbol in self.prices:
            del self.prices[symbol]
        if symbol in self.squeeze_scores:
            del self.squeeze_scores[symbol]
        if symbol in self.max_widths:
            del self.max_widths[symbol]
        if symbol in self.prev_widths:
            del self.prev_widths[symbol]
