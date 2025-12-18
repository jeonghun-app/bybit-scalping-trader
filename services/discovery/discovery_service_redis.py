"""
Discovery Service - Redis 기반
Scanner 수에 따라 동적으로 Top N 조정
"""
import time
import logging
import sys
import json
import requests
from typing import List, Dict
from datetime import datetime

import redis

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


class DiscoveryServiceRedis:
    """Redis 기반 Discovery Service"""
    
    def __init__(self):
        self.bybit_api_url = "https://api.bybit.com/v5/market/tickers"
        
        # Redis 연결 (환경 변수)
        import os
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.redis_db = 0
        self.redis_client = None
        
        # 필터 기준 (환경 변수)
        self.min_volume_24h = float(os.getenv("MIN_VOLUME_24H", "1000000"))
        self.min_volatility_pct = float(os.getenv("MIN_VOLATILITY_PCT", "2.0"))
        self.symbols_per_scanner = int(os.getenv("SYMBOLS_PER_SCANNER", "50"))
        
    def connect_redis(self) -> bool:
        """Redis 연결"""
        try:
            self.redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            
            # 연결 테스트
            self.redis_client.ping()
            
            logger.info(f"✅ Redis 연결 성공: {self.redis_host}:{self.redis_port}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Redis 연결 실패: {e}")
            return False
    
    def get_active_scanner_count(self) -> int:
        """활성 Scanner 수 조회"""
        try:
            # scanner:active Set에서 활성 Scanner 조회
            active_scanners = self.redis_client.smembers("scanner:active")
            
            # TTL 체크: 60초 이상 업데이트 없으면 제거
            now = time.time()
            valid_scanners = []
            
            for scanner_id in active_scanners:
                last_heartbeat = self.redis_client.get(f"scanner:{scanner_id}:heartbeat")
                if last_heartbeat:
                    age = now - float(last_heartbeat)
                    if age < 60:  # 60초 이내
                        valid_scanners.append(scanner_id)
                    else:
                        # 오래된 Scanner 제거
                        self.redis_client.srem("scanner:active", scanner_id)
                        logger.warning(f"⚠️ Scanner {scanner_id} 타임아웃 제거")
            
            count = len(valid_scanners)
            logger.info(f"📊 활성 Scanner: {count}개 ({', '.join(valid_scanners) if valid_scanners else 'None'})")
            
            return max(count, 1)  # 최소 1개
            
        except Exception as e:
            logger.error(f"Scanner 수 조회 오류: {e}")
            return 1  # 기본값
    
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
    
    def filter_and_rank(self, tickers: List[Dict], target_count: int = 75) -> List[Dict]:
        """필터링 및 랭킹 - 변동성*볼륨 기준 75개"""
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
                
                # 변동성 * 볼륨 점수
                score = change_pct * (turnover_24h / 1000000)
                
                filtered.append({
                    "symbol": symbol,
                    "price": price,
                    "turnover_24h": turnover_24h,
                    "volume_24h": volume_24h,
                    "change_pct": change_pct,
                    "funding_rate": float(ticker.get("fundingRate", 0)),
                    "score": score
                })
                
            except (ValueError, TypeError):
                continue
        
        # 변동성*볼륨 점수로 정렬
        sorted_by_score = sorted(filtered, key=lambda x: x["score"], reverse=True)
        selected = sorted_by_score[:75]
        
        logger.info(f"✅ 필터링 완료: {len(filtered)}개 → 변동성*볼륨 Top 75개")
        
        return selected
    
    def publish_to_redis(self, top_symbols: List[Dict]) -> bool:
        """Redis에 발행"""
        try:
            # 현재 버전 조회
            current_version = self.redis_client.get("discovery:version")
            new_version = int(current_version) + 1 if current_version else 1
            
            # 데이터 구성
            data = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "version": new_version,
                "total_count": len(top_symbols),
                "symbols": [s["symbol"] for s in top_symbols],
                "details": top_symbols
            }
            
            # Redis에 저장
            self.redis_client.set(
                "discovery:latest",
                json.dumps(data),
                ex=300  # 5분 TTL
            )
            
            # 버전 업데이트 (Scanner들이 감지)
            self.redis_client.set("discovery:version", new_version)
            
            # Pub/Sub 알림 (선택적)
            self.redis_client.publish("discovery:update", json.dumps({
                "version": new_version,
                "count": len(top_symbols)
            }))
            
            logger.info(
                f"📤 Redis 발행: v{new_version} | {len(top_symbols)}개 심볼 | "
                f"Top 3: {', '.join([s['symbol'] for s in top_symbols[:3]])}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Redis 발행 실패: {e}")
            return False
    
    def run_once(self):
        """1회 실행"""
        logger.info("=" * 60)
        logger.info("🔍 Discovery 시작")
        logger.info("=" * 60)
        
        logger.info(f"🎯 목표: 변동성*볼륨 Top 75개 심볼")
        
        # 1. 전체 티커 조회
        tickers = self.fetch_all_tickers()
        if not tickers:
            logger.warning("⚠️ 티커 조회 실패 - 스킵")
            return
        
        # 2. 필터링 및 랭킹 (75개 고정)
        top_symbols = self.filter_and_rank(tickers)
        if not top_symbols:
            logger.warning("⚠️ 필터링 결과 없음 - 스킵")
            return
        
        # 3. Redis에 발행
        self.publish_to_redis(top_symbols)
        
        logger.info("=" * 60)
    
    def run(self, interval_seconds: int = 60):
        """주기적 실행"""
        logger.info("=" * 60)
        logger.info("🚀 Discovery Service (Redis) 시작")
        logger.info(f"   실행 주기: {interval_seconds}초")
        logger.info(f"   Scanner당 심볼: {self.symbols_per_scanner}개")
        logger.info("=" * 60)
        
        # Redis 연결
        if not self.connect_redis():
            logger.error("Redis 연결 실패 - 종료")
            return
        
        try:
            while True:
                self.run_once()
                
                logger.info(f"⏰ {interval_seconds}초 대기 중...")
                time.sleep(interval_seconds)
                
        except KeyboardInterrupt:
            logger.info("사용자 중단")
        finally:
            if self.redis_client:
                self.redis_client.close()
                logger.info("✅ Discovery Service 종료")


def main():
    """메인 실행"""
    import os
    service = DiscoveryServiceRedis()
    
    # 실행 주기 - 1일 (86400초)
    interval = int(os.getenv("DISCOVERY_INTERVAL", "86400"))
    service.run(interval_seconds=interval)


if __name__ == "__main__":
    main()
