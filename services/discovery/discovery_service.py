"""
Discovery Service
전체 시장 스캔 및 Top N 선정 (REST API 기반)
"""
import time
import logging
import sys
import json
import requests
from typing import List, Dict
from datetime import datetime

import pika

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


class DiscoveryService:
    """시장 발견 서비스 - REST API 기반"""
    
    def __init__(self):
        self.bybit_api_url = "https://api.bybit.com/v5/market/tickers"
        self.rabbitmq_host = "localhost"  # 환경 변수로 대체 가능
        self.rabbitmq_port = 5672
        self.rabbitmq_user = "admin"
        self.rabbitmq_pass = ""
        self.queue_name = "discovery-results"
        
        # 필터 기준
        self.min_volume_24h = 1_000_000  # $1M
        self.min_volatility_pct = 2.0    # 2%
        self.top_n = 50
        
        # RabbitMQ 연결
        self.connection = None
        self.channel = None
        
    def connect_rabbitmq(self) -> bool:
        """RabbitMQ 연결"""
        try:
            credentials = pika.PlainCredentials(
                self.rabbitmq_user,
                self.rabbitmq_pass
            )
            
            parameters = pika.ConnectionParameters(
                host=self.rabbitmq_host,
                port=self.rabbitmq_port,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300
            )
            
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            
            # 큐 선언
            self.channel.queue_declare(
                queue=self.queue_name,
                durable=True
            )
            
            logger.info(f"✅ RabbitMQ 연결 성공: {self.rabbitmq_host}")
            return True
            
        except Exception as e:
            logger.error(f"❌ RabbitMQ 연결 실패: {e}")
            return False
    
    def fetch_all_tickers(self) -> List[Dict]:
        """전체 티커 조회 (REST API)"""
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
                
                # USDT 선물만
                if not symbol.endswith("USDT"):
                    continue
                
                # 스테이블코인 제외
                if any(stable in symbol for stable in ["USDC", "BUSD", "DAI", "TUSD"]):
                    continue
                
                # 제외 패턴
                if any(pattern in symbol for pattern in ["DOWN", "UP", "BEAR", "BULL"]):
                    continue
                
                # 데이터 파싱
                price = float(ticker.get("lastPrice", 0))
                turnover_24h = float(ticker.get("turnover24h", 0))
                change_pct = abs(float(ticker.get("price24hPcnt", 0))) * 100
                volume_24h = float(ticker.get("volume24h", 0))
                
                # 필터링
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
                logger.debug(f"티커 파싱 오류 ({symbol}): {e}")
                continue
        
        # 변동성 기준 정렬
        filtered.sort(key=lambda x: x["change_pct"], reverse=True)
        
        logger.info(f"✅ 필터링 완료: {len(filtered)}개 → Top {self.top_n} 선정")
        
        return filtered[:self.top_n]
    
    def publish_discovery(self, top_symbols: List[Dict]) -> bool:
        """발견 결과 발행"""
        try:
            if not self.connection or self.connection.is_closed:
                if not self.connect_rabbitmq():
                    return False
            
            message = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "total_count": len(top_symbols),
                "symbols": [s["symbol"] for s in top_symbols],
                "details": top_symbols
            }
            
            self.channel.basic_publish(
                exchange='',
                routing_key=self.queue_name,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    content_type='application/json'
                )
            )
            
            logger.info(
                f"📤 Discovery 발행: {len(top_symbols)}개 심볼 | "
                f"Top 3: {', '.join([s['symbol'] for s in top_symbols[:3]])}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 발행 실패: {e}")
            return False
    
    def run_once(self):
        """1회 실행"""
        logger.info("=" * 60)
        logger.info("🔍 Discovery 시작")
        logger.info("=" * 60)
        
        # 1. 전체 티커 조회
        tickers = self.fetch_all_tickers()
        if not tickers:
            logger.warning("⚠️ 티커 조회 실패 - 스킵")
            return
        
        # 2. 필터링 및 랭킹
        top_symbols = self.filter_and_rank(tickers)
        if not top_symbols:
            logger.warning("⚠️ 필터링 결과 없음 - 스킵")
            return
        
        # 3. 발행
        self.publish_discovery(top_symbols)
        
        logger.info("=" * 60)
    
    def run(self, interval_seconds: int = 60):
        """주기적 실행"""
        logger.info("=" * 60)
        logger.info("🚀 Discovery Service 시작")
        logger.info(f"   실행 주기: {interval_seconds}초")
        logger.info("=" * 60)
        
        # RabbitMQ 연결
        if not self.connect_rabbitmq():
            logger.error("RabbitMQ 연결 실패 - 종료")
            return
        
        try:
            while True:
                self.run_once()
                
                logger.info(f"⏰ {interval_seconds}초 대기 중...")
                time.sleep(interval_seconds)
                
        except KeyboardInterrupt:
            logger.info("사용자 중단")
        finally:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
                logger.info("✅ Discovery Service 종료")


def main():
    """메인 실행"""
    service = DiscoveryService()
    
    # 1분마다 실행
    service.run(interval_seconds=60)


if __name__ == "__main__":
    main()
