"""
Redis 연결 및 상태 관리
"""
import json
import logging
import socket
from datetime import datetime
from typing import List, Set

import redis.asyncio as aioredis
from config.settings import Config

logger = logging.getLogger(__name__)


class RedisManager:
    """Redis 연결 및 상태 관리"""
    
    def __init__(self):
        self.redis_client = None
        self.scanner_id = socket.gethostname()
        
    async def connect(self) -> bool:
        """Redis 연결"""
        try:
            self.redis_client = aioredis.from_url(
                f"redis://{Config.REDIS_HOST}:{Config.REDIS_PORT}",
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info(f"✅ Redis 연결 성공: {Config.REDIS_HOST}:{Config.REDIS_PORT}")
            return True
        except Exception as e:
            logger.error(f"❌ Redis 연결 실패: {e}")
            return False
    
    async def register_scanner(self) -> bool:
        """Scanner 등록"""
        try:
            scanner_data = {
                "scanner_id": self.scanner_id,
                "status": "active",
                "last_heartbeat": datetime.utcnow().isoformat(),
                "assigned_symbols": [],
                "rank": 0,
                "version": "v0"
            }
            
            await self.redis_client.hset(
                "scanners", 
                self.scanner_id, 
                json.dumps(scanner_data)
            )
            
            logger.info(f"📝 Scanner 등록: {self.scanner_id}")
            return True
        except Exception as e:
            logger.error(f"Scanner 등록 실패: {e}")
            return False
    
    async def update_heartbeat(self):
        """하트비트 업데이트"""
        try:
            await self.redis_client.hset(
                f"scanner:{self.scanner_id}",
                "last_heartbeat",
                datetime.utcnow().isoformat()
            )
        except Exception as e:
            logger.error(f"하트비트 업데이트 실패: {e}")
    
    async def get_symbol_assignments(self) -> List[str]:
        """심볼 할당 조회"""
        try:
            symbols_data = await self.redis_client.get("discovery:latest")
            if not symbols_data:
                return []
            
            data = json.loads(symbols_data)
            return data.get("symbols", [])
        except Exception as e:
            logger.error(f"심볼 할당 조회 실패: {e}")
            return []
    
    async def get_scanner_rank(self) -> tuple:
        """Scanner 순위 조회"""
        try:
            scanners_data = await self.redis_client.hgetall("scanners")
            active_scanners = []
            
            for scanner_id, data_str in scanners_data.items():
                data = json.loads(data_str)
                if data.get("status") == "active":
                    active_scanners.append(scanner_id)
            
            active_scanners.sort()
            
            if self.scanner_id in active_scanners:
                rank = active_scanners.index(self.scanner_id) + 1
                total = len(active_scanners)
                return rank, total
            
            return 1, 1
        except Exception as e:
            logger.error(f"Scanner 순위 조회 실패: {e}")
            return 1, 1
    
    async def close(self):
        """Redis 연결 종료"""
        if self.redis_client:
            await self.redis_client.close()
