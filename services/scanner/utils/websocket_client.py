"""
Bybit WebSocket Client
실시간 데이터 스트림 관리
"""
import asyncio
import json
import ssl
import logging
from typing import Callable, List, Optional
from datetime import datetime
import websockets
from websockets.exceptions import ConnectionClosed

from config.settings import Config

logger = logging.getLogger(__name__)


class BybitWebSocketClient:
    """Bybit WebSocket 연결 관리"""
    
    def __init__(self, url: str = Config.BYBIT_WS_URL):
        self.url = url
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.handlers = {}
        self.is_connected = False
        self.ping_task: Optional[asyncio.Task] = None
        self.last_message_time = datetime.now()
        
    async def connect(self) -> bool:
        """WebSocket 연결"""
        try:
            ssl_context = ssl.create_default_context()
            self.ws = await websockets.connect(
                self.url,
                ssl=ssl_context,
                ping_interval=None,  # 수동 ping 관리
                close_timeout=10
            )
            self.is_connected = True
            self.last_message_time = datetime.now()
            logger.info(f"✅ WebSocket 연결 성공: {self.url}")
            
            # Ping 태스크 시작
            self.ping_task = asyncio.create_task(self._send_ping())
            
            return True
            
        except Exception as e:
            logger.error(f"❌ WebSocket 연결 실패: {e}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """WebSocket 연결 종료"""
        self.is_connected = False
        
        if self.ping_task:
            self.ping_task.cancel()
            
        if self.ws:
            await self.ws.close()
            logger.info("WebSocket 연결 종료")
    
    async def subscribe(self, topics: List[str]):
        """토픽 구독"""
        if not self.ws or not self.is_connected:
            logger.error("WebSocket이 연결되지 않음")
            return False
        
        try:
            # Bybit는 최대 48개 args 권장
            for i in range(0, len(topics), 48):
                chunk = topics[i:i+48]
                message = {
                    "op": "subscribe",
                    "args": chunk
                }
                await self.ws.send(json.dumps(message))
                logger.info(f"📡 구독 요청: {len(chunk)}개 토픽")
                await asyncio.sleep(0.1)  # Rate limit 방지
            
            return True
            
        except Exception as e:
            logger.error(f"구독 실패: {e}")
            return False
    
    async def unsubscribe(self, topics: List[str]):
        """토픽 구독 해제"""
        if not self.ws or not self.is_connected:
            return False
        
        try:
            message = {
                "op": "unsubscribe",
                "args": topics
            }
            await self.ws.send(json.dumps(message))
            logger.info(f"구독 해제: {len(topics)}개 토픽")
            return True
            
        except Exception as e:
            logger.error(f"구독 해제 실패: {e}")
            return False
    
    def register_handler(self, topic_pattern: str, handler: Callable):
        """메시지 핸들러 등록"""
        self.handlers[topic_pattern] = handler
        logger.debug(f"핸들러 등록: {topic_pattern}")
    
    async def listen(self):
        """메시지 수신 루프"""
        if not self.ws or not self.is_connected:
            logger.error("WebSocket이 연결되지 않음")
            return
        
        logger.info("🎧 메시지 수신 시작...")
        
        try:
            while self.is_connected:
                try:
                    message = await asyncio.wait_for(
                        self.ws.recv(),
                        timeout=Config.WS_TIMEOUT
                    )
                    self.last_message_time = datetime.now()
                    
                    data = json.loads(message)
                    
                    # Pong 응답 처리
                    if data.get("op") == "pong":
                        logger.debug("📡 Pong 수신")
                        continue
                    
                    # 구독 확인 메시지
                    if data.get("op") == "subscribe":
                        if data.get("success"):
                            logger.info(f"✅ 구독 성공: {data.get('ret_msg', '')}")
                        else:
                            logger.warning(f"⚠️ 구독 실패: {data}")
                        continue
                    
                    # 데이터 메시지 처리
                    topic = data.get("topic", "")
                    if topic:
                        logger.debug(f"📨 메시지 수신: {topic}")
                        await self._dispatch_message(topic, data)
                    else:
                        logger.debug(f"🔍 토픽 없는 메시지: {data}")
                    
                except asyncio.TimeoutError:
                    # 타임아웃 체크
                    elapsed = (datetime.now() - self.last_message_time).total_seconds()
                    if elapsed > Config.WS_TIMEOUT:
                        logger.warning(f"⚠️ 메시지 수신 타임아웃 ({elapsed}초)")
                        break
                    continue
                    
                except ConnectionClosed:
                    logger.warning("⚠️ WebSocket 연결 끊김")
                    break
                    
        except Exception as e:
            logger.error(f"❌ 메시지 수신 오류: {e}")
        finally:
            self.is_connected = False
    
    async def _dispatch_message(self, topic: str, data: dict):
        """메시지를 적절한 핸들러로 전달"""
        handled = False
        for pattern, handler in self.handlers.items():
            if pattern == "*":
                # 와일드카드는 마지막에 처리
                continue
            if pattern in topic:
                try:
                    await handler(topic, data)
                    handled = True
                except Exception as e:
                    logger.error(f"핸들러 실행 오류 ({pattern}): {e}")
        
        # 와일드카드 핸들러 실행 (처리되지 않은 메시지만)
        if not handled and "*" in self.handlers:
            try:
                await self.handlers["*"](topic, data)
            except Exception as e:
                logger.error(f"와일드카드 핸들러 오류: {e}")
    
    async def _send_ping(self):
        """주기적으로 ping 전송"""
        while self.is_connected:
            try:
                await asyncio.sleep(Config.WS_PING_INTERVAL)
                if self.ws and self.is_connected:
                    await self.ws.send(json.dumps({"op": "ping"}))
                    logger.debug("📡 Ping 전송")
            except Exception as e:
                logger.error(f"Ping 전송 실패: {e}")
                break
