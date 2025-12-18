"""
Trading Executor - 실시간 주문 실행
Scanner에서 감지한 기회를 즉시 주문으로 실행
"""
import asyncio
import json
import logging
import os
import ssl
from decimal import Decimal, ROUND_DOWN
from datetime import datetime
import boto3
from pybit.unified_trading import HTTP

logger = logging.getLogger(__name__)

class TradingExecutor:
    def __init__(self):
        self.bybit_session = None
        self.position_size_usd = 10.0  # $10 포지션
        self.leverage = 10
        self.enabled = os.getenv('TRADING_ENABLED', 'false').lower() == 'true'
        
    async def initialize(self):
        """Executor 초기화"""
        if not self.enabled:
            logger.info("🔒 Trading 비활성화 (TRADING_ENABLED=false)")
            return
            
        await self._setup_bybit()
        logger.info("🚀 Trading Executor 초기화 완료")
        
    async def _setup_bybit(self):
        """Bybit API 연결"""
        secrets_client = boto3.client('secretsmanager', region_name='ap-northeast-2')
        
        try:
            api_key_secret = secrets_client.get_secret_value(SecretId='crypto-backtest/bybit-api-key')
            api_secret_secret = secrets_client.get_secret_value(SecretId='crypto-backtest/bybit-api-secret')
            
            api_key = api_key_secret['SecretString']
            api_secret = api_secret_secret['SecretString']
            
            self.bybit_session = HTTP(
                testnet=False,
                api_key=api_key,
                api_secret=api_secret
            )
            
            # 연결 테스트
            account_info = self.bybit_session.get_wallet_balance(accountType="UNIFIED")
            logger.info("✅ Bybit 연결 성공")
            
        except Exception as e:
            logger.error(f"❌ Bybit 연결 실패: {e}")
            self.enabled = False
            
    async def execute_trade(self, symbol: str, signal_type: str, score: float):
        """거래 실행"""
        if not self.enabled:
            logger.info(f"📊 거래 시뮬레이션: {symbol} {signal_type} (score: {score:.2f})")
            return
            
        try:
            # 현재 가격 조회
            current_price = await self.get_current_price(symbol)
            if not current_price:
                return
                
            # 주문 수량 계산
            qty = await self.calculate_order_qty(symbol, current_price)
            if not qty:
                return
                
            # 롱 포지션 진입
            order_result = await self.place_market_order(symbol, "Buy", qty)
            
            if order_result:
                logger.info(f"🚀 주문 실행: {symbol} BUY {qty} @ ${current_price:.4f}")
                
                # 손절/익절 주문 설정
                await self.set_stop_loss_take_profit(symbol, current_price)
                
        except Exception as e:
            logger.error(f"거래 실행 오류 {symbol}: {e}")
            
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
        """주문 수량 계산"""
        try:
            response = self.bybit_session.get_instruments_info(
                category="linear",
                symbol=symbol
            )
            instrument_info = response['result']['list'][0]
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
            
    async def place_market_order(self, symbol, side, qty):
        """시장가 주문"""
        try:
            response = self.bybit_session.place_order(
                category="linear",
                symbol=symbol,
                side=side,
                orderType="Market",
                qty=str(qty),
                timeInForce="IOC"
            )
            
            if response['retCode'] == 0:
                return response['result']
            else:
                logger.error(f"주문 실패: {response['retMsg']}")
                return None
                
        except Exception as e:
            logger.error(f"주문 실행 오류: {e}")
            return None
            
    async def set_stop_loss_take_profit(self, symbol, entry_price):
        """손절/익절 설정 (2% 손절, 4% 익절)"""
        try:
            stop_loss = entry_price * 0.98  # 2% 손절
            take_profit = entry_price * 1.04  # 4% 익절
            
            # 손절 주문
            self.bybit_session.set_trading_stop(
                category="linear",
                symbol=symbol,
                stopLoss=str(stop_loss),
                takeProfit=str(take_profit),
                positionIdx=0
            )
            
            logger.info(f"📊 SL/TP 설정: {symbol} SL=${stop_loss:.4f} TP=${take_profit:.4f}")
            
        except Exception as e:
            logger.error(f"SL/TP 설정 오류: {e}")
