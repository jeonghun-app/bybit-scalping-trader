#!/usr/bin/env python3
"""
Executor Service - 실시간 주문 실행
Scanner → Hawk → Executor 파이프라인의 마지막 단계
"""

import asyncio
import json
import logging
import os
import ssl
import time
from datetime import datetime
from decimal import Decimal, ROUND_DOWN
import boto3
import redis
import pika
from pybit.unified_trading import HTTP

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ExecutorService:
    def __init__(self):
        self.redis_client = None
        self.bybit_session = None
        self.rabbitmq_connection = None
        self.rabbitmq_channel = None
        self.position_size_usd = 10.0  # $10 포지션
        self.leverage = 10
        
    async def initialize(self):
        """서비스 초기화"""
        await self._setup_redis()
        await self._setup_bybit()
        await self._setup_rabbitmq()
        logger.info("🚀 Executor Service 초기화 완료")
        
    async def _setup_redis(self):
        """Redis 연결"""
        redis_host = os.getenv('REDIS_HOST', 'crypto-backtest-redis.h0oz8i.0001.apn2.cache.amazonaws.com')
        self.redis_client = redis.Redis(host=redis_host, port=6379, decode_responses=True)
        self.redis_client.ping()
        logger.info("✅ Redis 연결 성공")
        
    async def _setup_bybit(self):
        """Bybit API 연결"""
        # AWS Secrets Manager에서 API 키 가져오기
        secrets_client = boto3.client('secretsmanager', region_name='ap-northeast-2')
        
        try:
            api_key_secret = secrets_client.get_secret_value(SecretId='crypto-backtest/bybit-api-key')
            api_secret_secret = secrets_client.get_secret_value(SecretId='crypto-backtest/bybit-api-secret')
            
            api_key = api_key_secret['SecretString']
            api_secret = api_secret_secret['SecretString']
            
            self.bybit_session = HTTP(
                testnet=False,  # 프로덕션 모드
                api_key=api_key,
                api_secret=api_secret
            )
            
            # 연결 테스트
            account_info = self.bybit_session.get_wallet_balance(accountType="UNIFIED")
            logger.info("✅ Bybit 프로덕션 연결 성공")
            
        except Exception as e:
            logger.error(f"❌ Bybit 연결 실패: {e}")
            raise
            
    async def _setup_rabbitmq(self):
        """RabbitMQ 연결"""
        rabbitmq_url = os.getenv('RABBITMQ_URL', 'amqps://b-3e6a53bb-ec2b-4380-aaa8-64f147af0cd5.mq.ap-northeast-2.on.aws:5671')
        
        try:
            # RabbitMQ 자격 증명 가져오기
            secrets_client = boto3.client('secretsmanager', region_name='ap-northeast-2')
            rabbitmq_secret = secrets_client.get_secret_value(SecretId='crypto-backtest/rabbitmq-creds')
            rabbitmq_creds = json.loads(rabbitmq_secret['SecretString'])
            
            # RabbitMQ 연결 파라미터 파싱
            import urllib.parse
            parsed = urllib.parse.urlparse(rabbitmq_url)
            
            credentials = pika.PlainCredentials(rabbitmq_creds['username'], rabbitmq_creds['password'])
            parameters = pika.ConnectionParameters(
                host=parsed.hostname,
                port=parsed.port,
                virtual_host='/',
                credentials=credentials,
                ssl_options=pika.SSLOptions(ssl.create_default_context()) if parsed.scheme == 'amqps' else None
            )
            
            self.rabbitmq_connection = pika.BlockingConnection(parameters)
            self.rabbitmq_channel = self.rabbitmq_connection.channel()
            
            # entry-signal 큐 선언
            self.rabbitmq_channel.queue_declare(queue='entry-signal', durable=True)
            logger.info("✅ RabbitMQ 연결 성공")
            
        except Exception as e:
            logger.error(f"❌ RabbitMQ 연결 실패: {e}")
            raise
            
    async def get_instrument_info(self, symbol):
        """심볼 정보 조회"""
        try:
            response = self.bybit_session.get_instruments_info(
                category="linear",
                symbol=symbol
            )
            return response['result']['list'][0]
        except Exception as e:
            logger.error(f"심볼 정보 조회 실패 {symbol}: {e}")
            return None
            
    async def get_current_price(self, symbol):
        """현재 가격 조회"""
        try:
            response = self.bybit_session.get_tickers(
                category="linear",
                symbol=symbol
            )
            return float(response['result']['list'][0]['lastPrice'])
        except Exception as e:
            logger.error(f"가격 조회 실패 {symbol}: {e}")
            return None
            
    async def calculate_order_qty(self, symbol, entry_price):
        """주문 수량 계산 (qtyStep 반영)"""
        try:
            instrument_info = await self.get_instrument_info(symbol)
            if not instrument_info:
                return None
                
            qty_step = float(instrument_info['lotSizeFilter']['qtyStep'])
            
            # $10 포지션, 10x 레버리지
            raw_qty = (self.position_size_usd * self.leverage) / entry_price
            
            # qtyStep에 맞춰 반올림
            rounded_qty = Decimal(str(raw_qty)).quantize(
                Decimal(str(qty_step)), 
                rounding=ROUND_DOWN
            )
            
            return float(rounded_qty)
            
        except Exception as e:
            logger.error(f"수량 계산 실패 {symbol}: {e}")
            return None
            
    async def is_already_positioned(self, symbol, side):
        """중복 포지션 확인"""
        try:
            response = self.bybit_session.get_positions(
                category="linear",
                symbol=symbol
            )
            
            positions = response['result']['list']
            if not positions:
                return False
                
            position = positions[0]
            size = float(position['size'])
            position_side = position['side']
            
            # 이미 같은 방향 포지션이 있으면 중복
            if side == "buy" and position_side == "Buy" and size > 0:
                return True
            if side == "sell" and position_side == "Sell" and size > 0:
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"포지션 확인 실패 {symbol}: {e}")
            return False
            
    async def set_leverage(self, symbol):
        """레버리지 설정"""
        try:
            self.bybit_session.set_leverage(
                category="linear",
                symbol=symbol,
                buyLeverage=str(self.leverage),
                sellLeverage=str(self.leverage)
            )
            logger.info(f"레버리지 {self.leverage}x 설정: {symbol}")
        except Exception as e:
            # 이미 설정된 경우 무시
            if "110043" not in str(e):
                logger.warning(f"레버리지 설정 실패 {symbol}: {e}")
                
    async def execute_order(self, signal_data):
        """주문 실행"""
        symbol = signal_data['symbol']
        direction = signal_data.get('direction', 'LONG')  # LONG/SHORT
        confidence = float(signal_data.get('confidence', 0))
        
        # direction을 side로 변환
        side = "buy" if direction == "LONG" else "sell"
        
        logger.info(f"🎯 주문 실행 시작: {symbol} {direction} (신뢰도: {confidence}%)")
        
        try:
            # 1. 신뢰도 검증
            if confidence < 75:
                logger.warning(f"신뢰도 부족 ({confidence}%). 주문 취소: {symbol}")
                return False
                
            # 2. 현재 가격 조회 (진입가로 사용)
            current_price = await self.get_current_price(symbol)
            if not current_price:
                logger.error(f"현재 가격 조회 실패: {symbol}")
                return False
            
            entry_price = current_price
            
            # 3. TP/SL 가격 계산 (1% TP, 0.5% SL)
            if direction == "LONG":
                tp_price = entry_price * 1.01   # +1% 익절
                sl_price = entry_price * 0.995  # -0.5% 손절
            else:  # SHORT
                tp_price = entry_price * 0.99   # -1% 익절
                sl_price = entry_price * 1.005  # +0.5% 손절
                
            # 4. 중복 포지션 확인
            if await self.is_already_positioned(symbol, side):
                logger.info(f"이미 포지션 존재. 주문 취소: {symbol}")
                return False
                
            # 5. 주문 수량 계산
            qty = await self.calculate_order_qty(symbol, entry_price)
            if not qty or qty <= 0:
                logger.error(f"주문 수량 계산 실패: {symbol}")
                return False
                
            # 6. 레버리지 설정
            await self.set_leverage(symbol)
            
            # 7. 주문 실행 (Market Order로 즉시 진입)
            bybit_side = "Buy" if side == "buy" else "Sell"
            
            order_response = self.bybit_session.place_order(
                category="linear",
                symbol=symbol,
                side=bybit_side,
                orderType="Market",  # 시장가로 즉시 진입
                qty=str(qty),
                takeProfit=str(tp_price),
                stopLoss=str(sl_price),
                tpTriggerBy="LastPrice",
                slTriggerBy="LastPrice",
                positionIdx=0
            )
            
            if order_response['retCode'] == 0:
                order_id = order_response['result']['orderId']
                logger.info(f"✅ 주문 성공: {symbol} {direction} @ {entry_price} (ID: {order_id})")
                
                # 실행 로그 저장
                await self.save_execution_log(symbol, order_response['result'], signal_data)
                return True
            else:
                logger.error(f"❌ 주문 실패: {order_response['retMsg']}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 주문 실행 중 오류 {symbol}: {e}")
            return False
            
    async def save_execution_log(self, symbol, order_result, signal_data):
        """실행 로그 저장"""
        try:
            log_entry = {
                "symbol": symbol,
                "orderId": order_result['orderId'],
                "side": order_result['side'],
                "qty": order_result['qty'],
                "price": order_result['price'],
                "takeProfit": signal_data.get('take_profit'),
                "stopLoss": signal_data.get('stop_loss'),
                "confidence": signal_data.get('confidence'),
                "timestamp": datetime.utcnow().isoformat(),
                "status": "executed"
            }
            
            # Redis에 저장
            self.redis_client.setex(
                f"execution:{order_result['orderId']}", 
                86400,  # 24시간
                json.dumps(log_entry)
            )
            
            logger.info(f"📝 실행 로그 저장: {order_result['orderId']}")
            
        except Exception as e:
            logger.error(f"로그 저장 실패: {e}")
            
    def on_entry_signal(self, ch, method, properties, body):
        """entry-signal 메시지 처리"""
        try:
            signal_data = json.loads(body)
            logger.info(f"📨 Entry Signal 수신: {signal_data}")
            
            # 비동기 실행
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            success = loop.run_until_complete(self.execute_order(signal_data))
            loop.close()
            
            if success:
                ch.basic_ack(delivery_tag=method.delivery_tag)
            else:
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                
        except Exception as e:
            logger.error(f"메시지 처리 실패: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            
    async def start_consuming(self):
        """메시지 소비 시작"""
        try:
            self.rabbitmq_channel.basic_qos(prefetch_count=1)
            self.rabbitmq_channel.basic_consume(
                queue='entry-signal',
                on_message_callback=self.on_entry_signal
            )
            
            logger.info("🎧 Entry Signal 대기 중...")
            self.rabbitmq_channel.start_consuming()
            
        except KeyboardInterrupt:
            logger.info("서비스 종료 중...")
            self.rabbitmq_channel.stop_consuming()
            self.rabbitmq_connection.close()

async def main():
    """메인 실행"""
    executor = ExecutorService()
    
    try:
        await executor.initialize()
        await executor.start_consuming()
    except Exception as e:
        logger.error(f"서비스 실행 실패: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
