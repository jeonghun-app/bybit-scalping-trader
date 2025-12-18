"""
Discovery Service 로컬 테스트
RabbitMQ 없이 콘솔 출력
"""
import logging
import sys
import requests
from typing import List, Dict

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


class TestDiscovery:
    """테스트용 Discovery (RabbitMQ 없음)"""
    
    def __init__(self):
        self.bybit_api_url = "https://api.bybit.com/v5/market/tickers"
        self.min_volume_24h = 1_000_000
        self.min_volatility_pct = 2.0
        self.top_n = 50
    
    def fetch_all_tickers(self) -> List[Dict]:
        """전체 티커 조회"""
        try:
            params = {"category": "linear"}
            response = requests.get(
                self.bybit_api_url,
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                tickers = data.get("result", {}).get("list", [])
                logger.info(f"📊 전체 {len(tickers)}개 티커 조회 완료")
                return tickers
            else:
                logger.error(f"❌ 티커 조회 실패: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"❌ 티커 조회 오류: {e}")
            return []
    
    def filter_and_rank(self, tickers: List[Dict]) -> List[Dict]:
        """필터링 및 랭킹"""
        filtered = []
        
        for ticker in tickers:
            try:
                symbol = ticker.get("symbol", "")
                
                if not symbol.endswith("USDT"):
                    continue
                
                if any(stable in symbol for stable in ["USDC", "BUSD", "DAI", "TUSD"]):
                    continue
                
                if any(pattern in symbol for pattern in ["DOWN", "UP", "BEAR", "BULL"]):
                    continue
                
                price = float(ticker.get("lastPrice", 0))
                turnover_24h = float(ticker.get("turnover24h", 0))
                change_pct = abs(float(ticker.get("price24hPcnt", 0))) * 100
                volume_24h = float(ticker.get("volume24h", 0))
                
                if turnover_24h < self.min_volume_24h:
                    continue
                
                if change_pct < self.min_volatility_pct:
                    continue
                
                filtered.append({
                    "symbol": symbol,
                    "price": price,
                    "turnover_24h": turnover_24h,
                    "volume_24h": volume_24h,
                    "change_pct": change_pct,
                    "funding_rate": float(ticker.get("fundingRate", 0))
                })
                
            except (ValueError, TypeError) as e:
                continue
        
        filtered.sort(key=lambda x: x["change_pct"], reverse=True)
        
        logger.info(f"✅ 필터링 완료: {len(filtered)}개 → Top {self.top_n} 선정")
        
        return filtered[:self.top_n]
    
    def run(self):
        """테스트 실행"""
        logger.info("=" * 60)
        logger.info("🧪 Discovery 로컬 테스트")
        logger.info("=" * 60)
        
        # 1. 전체 티커 조회
        tickers = self.fetch_all_tickers()
        if not tickers:
            logger.error("티커 조회 실패")
            return
        
        # 2. 필터링 및 랭킹
        top_symbols = self.filter_and_rank(tickers)
        if not top_symbols:
            logger.warning("필터링 결과 없음")
            return
        
        # 3. 결과 출력
        logger.info("=" * 60)
        logger.info(f"🔝 Top {len(top_symbols)} 심볼")
        logger.info("=" * 60)
        
        for i, item in enumerate(top_symbols[:20], 1):
            logger.info(
                f"#{i:2d} {item['symbol']:12s} | "
                f"변동성: {item['change_pct']:6.2f}% | "
                f"거래량: ${item['turnover_24h']/1e6:8.2f}M | "
                f"가격: ${item['price']:10.2f}"
            )
        
        if len(top_symbols) > 20:
            logger.info(f"... 외 {len(top_symbols) - 20}개")
        
        logger.info("=" * 60)
        logger.info("✅ 테스트 완료")
        logger.info("=" * 60)


def main():
    """메인"""
    discovery = TestDiscovery()
    discovery.run()


if __name__ == "__main__":
    main()
