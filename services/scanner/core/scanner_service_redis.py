"""
Scanner Service - 메인 서비스 (모듈화)
"""
import asyncio
import logging
import sys
import json
import time
from datetime import datetime
from typing import List, Set

import aiohttp
from config.settings import Config
from utils.websocket_client import BybitWebSocketClient
from redis_manager import RedisManager
from data_processor import DataProcessor

# 로깅 설정
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


class ScannerService:
    """모듈화된 Scanner Service"""
    
    def __init__(self):
        self.ws_client = BybitWebSocketClient()
        self.redis_manager = RedisManager()
        self.data_processor = DataProcessor()
        
        self.session = None
        self.active_symbols = set()
        self.current_version = "v0"
        self.rank = 1
        self.total_scanners = 1
        
        # 통계
        self.stats = {
            "start_time": datetime.utcnow(),
            "version_updates": 0,
            "symbols_assigned": 0,
            "opportunities_sent": 0
        }
    
    async def start(self):
        """Scanner 시작"""
        logger.info("🚀 Scanner Service 시작")
        
        # Redis 연결
        if not await self.redis_manager.connect():
            logger.error("Redis 연결 실패 - 종료")
            return
        
        # Scanner 등록
        if not await self.redis_manager.register_scanner():
            logger.error("Scanner 등록 실패 - 종료")
            return
        
        # Data Processor 초기화
        await self.data_processor.initialize()
        
        # Data Processor에 Scanner ID 설정
        self.data_processor.set_scanner_id(self.redis_manager.scanner_id)
        
        # HTTP 세션 생성
        self.session = aiohttp.ClientSession()
        
        # 메인 루프 시작
        await self._main_loop()
    
    async def _main_loop(self):
        """메인 실행 루프"""
        try:
            # 하트비트 태스크
            heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            
            # 통계 출력 태스크
            stats_task = asyncio.create_task(self._stats_loop())
            
            # WebSocket 연결 및 리스닝
            while True:
                try:
                    # WebSocket 연결
                    if not await self.ws_client.connect():
                        logger.error("WebSocket 연결 실패")
                        await asyncio.sleep(5)
                        continue
                    
                    # 핸들러 등록
                    self.ws_client.register_handler("tickers", self.data_processor.process_ticker)
                    self.ws_client.register_handler("orderbook", self.data_processor.process_bookticker)
                    self.ws_client.register_handler("kline", self.data_processor.process_candle)
                    
                    # 메시지 수신
                    await self.ws_client.listen()
                    
                    logger.warning("⚠️ WebSocket 연결 끊김 - 재시도 중...")
                    await asyncio.sleep(5)
                    
                except Exception as e:
                    logger.error(f"WebSocket 루프 오류: {e}")
                    await asyncio.sleep(10)
        
        except KeyboardInterrupt:
            logger.info("🛑 종료 신호 수신")
        finally:
            # 정리
            heartbeat_task.cancel()
            stats_task.cancel()
            await self._cleanup()
    
    async def _heartbeat_loop(self):
        """하트비트 루프"""
        while True:
            try:
                await self.redis_manager.update_heartbeat()
                await self._check_version_update()
                await asyncio.sleep(5)  # 5초마다
            except Exception as e:
                logger.error(f"하트비트 오류: {e}")
                await asyncio.sleep(5)
    
    async def _check_version_update(self):
        """버전 업데이트 체크"""
        try:
            symbols = await self.redis_manager.get_symbol_assignments()
            rank, total = await self.redis_manager.get_scanner_rank()
            
            # 새 버전 감지
            if symbols and len(symbols) != len(self.active_symbols):
                new_version = f"v{int(time.time()) % 1000}"
                logger.info(f"🔔 새 버전 감지: {new_version}")
                
                # 심볼 할당
                my_symbols = self._assign_symbols(symbols, rank, total)
                await self._update_subscriptions(my_symbols)
                
                self.current_version = new_version
                self.rank = rank
                self.total_scanners = total
                self.stats["version_updates"] += 1
                self.stats["symbols_assigned"] = len(my_symbols)
        
        except Exception as e:
            logger.error(f"버전 업데이트 체크 오류: {e}")
    
    def _assign_symbols(self, symbols: List[str], rank: int, total: int) -> List[str]:
        """심볼 할당 계산"""
        symbols_per_scanner = len(symbols) // total
        start_idx = (rank - 1) * symbols_per_scanner
        end_idx = start_idx + symbols_per_scanner
        
        if rank == total:  # 마지막 Scanner는 나머지 모두
            end_idx = len(symbols)
        
        return symbols[start_idx:end_idx]
    
    async def _update_subscriptions(self, new_symbols: List[str]):
        """구독 업데이트"""
        try:
            # 기존 구독 해제
            if self.active_symbols:
                old_topics = []
                for symbol in self.active_symbols:
                    old_topics.extend([
                        f"tickers.{symbol}",
                        f"orderbook.1.{symbol}",
                        f"kline.1.{symbol}"
                    ])
                await self.ws_client.unsubscribe(old_topics)
            
            # 새 구독
            if new_symbols:
                new_topics = []
                for symbol in new_symbols:
                    new_topics.extend([
                        f"tickers.{symbol}",
                        f"orderbook.1.{symbol}",
                        f"kline.1.{symbol}"
                    ])
                await self.ws_client.subscribe(new_topics)
            
            self.active_symbols = set(new_symbols)
            logger.info(f"📈 새 구독: {len(new_symbols)}개")
            logger.info(f"✅ 업데이트 완료: {self.current_version}")
        
        except Exception as e:
            logger.error(f"구독 업데이트 오류: {e}")
    
    async def _stats_loop(self):
        """통계 출력 루프"""
        while True:
            try:
                await asyncio.sleep(60)  # 1분마다
                
                processor_stats = self.data_processor.get_stats()
                
                logger.info("=" * 60)
                logger.info("📊 Scanner 통계")
                logger.info(f"   • Scanner ID: {self.redis_manager.scanner_id}")
                logger.info(f"   • Rank: {self.rank}/{self.total_scanners}")
                logger.info(f"   • 담당 심볼: {len(self.active_symbols)}")
                logger.info(f"   • 발행 기회: {processor_stats['total_opportunities_sent']}")
                logger.info(f"   • 버전: {self.current_version}")
                logger.info("=" * 60)
                
            except Exception as e:
                logger.error(f"통계 출력 오류: {e}")
    
    async def _cleanup(self):
        """정리 작업"""
        logger.info("🧹 정리 작업 시작")
        
        await self.ws_client.disconnect()
        await self.redis_manager.close()
        
        if self.session:
            await self.session.close()
        
        logger.info("✅ 정리 완료")


async def main():
    """메인 함수"""
    scanner = ScannerService()
    await scanner.start()


if __name__ == "__main__":
    asyncio.run(main())
