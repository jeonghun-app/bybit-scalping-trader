"""
Position Finder Service - 실시간 진입 신호 탐색
RabbitMQ에서 전략을 받아 현재 시점의 진입 신호 생성
"""
import os
import json
import time
import boto3
import pika
import pandas as pd
from decimal import Decimal
from datetime import datetime, timezone
from src.utils.bybit_client import BybitClient
from src.strategies.entry_strategy import EntryStrategy
from src.utils.indicators import Indicators
from config.config import Config

def convert_floats_to_decimal(obj):
    """재귀적으로 float를 Decimal로 변환"""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimal(item) for item in obj]
    return obj

class PositionFinderService:
    def __init__(self):
        self.client = BybitClient()
        self.strategy = EntryStrategy(self.client)
        
        self.dynamodb = boto3.resource('dynamodb', region_name=os.getenv('AWS_REGION', 'ap-northeast-2'))
        self.positions_table = self.dynamodb.Table(os.getenv('DYNAMODB_POSITIONS_TABLE', 'crypto-trading-positions'))
        
        # Bybit API 세션 (포지션 조회용)
        from pybit.unified_trading import HTTP
        self.session = HTTP(
            testnet=os.getenv('BYBIT_TESTNET', 'False') == 'True',
            api_key=os.getenv('BYBIT_API_KEY'),
            api_secret=os.getenv('BYBIT_API_SECRET')
        )
        
        # RabbitMQ 연결
        self.rabbitmq_host = os.getenv('RABBITMQ_HOST', 'localhost')
        self.rabbitmq_port = int(os.getenv('RABBITMQ_PORT', '5672'))
        self.rabbitmq_user = os.getenv('RABBITMQ_USER', 'guest')
        self.rabbitmq_pass = os.getenv('RABBITMQ_PASS', 'guest')
        self.queue_name = os.getenv('RABBITMQ_TRADING_QUEUE', 'trading-signals')
        
        self.finder_id = os.getenv('HOSTNAME', 'finder-1')
        self.prefetch_count = int(os.getenv('PREFETCH_COUNT', '1'))
    
    def connect_rabbitmq(self):
        """RabbitMQ 연결"""
        import ssl
        credentials = pika.PlainCredentials(self.rabbitmq_user, self.rabbitmq_pass)
        
        # Amazon MQ는 SSL 필요
        ssl_context = ssl.create_default_context()
        ssl_options = pika.SSLOptions(ssl_context)
        
        parameters = pika.ConnectionParameters(
            host=self.rabbitmq_host,
            port=self.rabbitmq_port,  # 환경 변수에서 포트 사용
            credentials=credentials,
            ssl_options=ssl_options,
            heartbeat=600,
            blocked_connection_timeout=300
        )
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        
        # Queue 선언
        channel.queue_declare(queue=self.queue_name, durable=True)
        
        # Prefetch 설정
        channel.basic_qos(prefetch_count=self.prefetch_count)
        
        return connection, channel
    
    def find_entry_signal(self, message):
        """진입 신호 탐색"""
        symbol = message['symbol']
        timeframe = message['timeframe'].replace('m', '')  # '1m' -> '1'
        strategy_type = message['strategy']
        
        print(f"\n{'='*80}")
        print(f"🔍 진입 신호 탐색: {symbol} ({timeframe}분봉, {strategy_type})")
        print(f"{'='*80}\n")
        
        try:
            # 1. 최신 캔들 데이터 가져오기 (백테스팅과 동일하게 1000개)
            print(f"[1/4] 캔들 데이터 로딩...")
            
            # 타임프레임에 따라 필요한 일수 계산
            timeframe_int = int(timeframe)
            if timeframe_int <= 5:
                days = 4  # 1~5분봉: 4일
            elif timeframe_int <= 15:
                days = 11  # 15분봉: 11일
            elif timeframe_int <= 60:
                days = 21  # 30~60분봉: 21일
            else:
                days = 42  # 그 이상: 42일
            
            candles = self.client.get_klines_for_days(symbol, timeframe, days)
            
            if candles.empty or len(candles) < Config.BB_PERIOD + 10:
                print(f"❌ 데이터 부족: {len(candles)}개 봉")
                return None
            
            # 최신 1000개만 사용 (백테스팅과 동일)
            if len(candles) > 1000:
                candles = candles.tail(1000).reset_index(drop=True)
            
            print(f"✅ {len(candles)}개 봉 로딩 완료")
            
            # 2. 심볼 정보 조회 (tickSize, qtyStep)
            print(f"[2/5] 심볼 정보 조회...")
            instrument_info = self.client.get_instrument_info(symbol)
            
            if not instrument_info:
                print(f"❌ 심볼 정보 조회 실패")
                return None
            
            print(f"✅ tickSize: {instrument_info['tick_size']}, qtyStep: {instrument_info['qty_step']}")
            
            # 3. 멀티 타임프레임 피보나치 계산
            print(f"[3/5] 피보나치 계산...")
            mtf_fib = Indicators.calculate_multi_timeframe_fibonacci(
                self.client,
                symbol,
                Config.FIBONACCI_TIMEFRAMES
            )
            
            if not mtf_fib:
                print(f"❌ 피보나치 계산 실패")
                return None
            
            print(f"✅ {len(mtf_fib)}개 타임프레임 피보나치 완료")
            
            # 4. 진입 신호 분석
            print(f"[4/5] 진입 신호 분석...")
            signal = self.strategy.analyze_entry(candles, symbol, mtf_fib, instrument_info=instrument_info)
            
            if not signal:
                print(f"⚠️  진입 신호 없음")
                return None
            
            # 소수점 자릿수
            price_decimals = instrument_info['price_decimals']
            
            print(f"✅ 진입 신호 발견!")
            print(f"  - 타입: {signal['type']}")
            print(f"  - 진입가: ${signal['entry_price']:.{price_decimals}f}")
            print(f"  - 손절가: ${signal['stop_loss']:.{price_decimals}f}")
            print(f"  - 익절가: ${signal['take_profit']:.{price_decimals}f}")
            print(f"  - 신뢰도: {signal.get('confidence', 60)}점")
            
            # 4. 추가 정보 수집
            print(f"[5/5] 추가 정보 수집...")
            
            # 피보나치 레벨 찾기
            all_fib_levels = {}
            for tf, fib_data in mtf_fib.items():
                all_fib_levels.update(fib_data['levels'])
            
            # 가장 가까운 지지/저항 찾기
            current_price = signal['entry_price']
            
            support_levels = [price for price in all_fib_levels.values() if price < current_price]
            resistance_levels = [price for price in all_fib_levels.values() if price > current_price]
            
            fib_support = max(support_levels) if support_levels else current_price * 0.95
            fib_resistance = min(resistance_levels) if resistance_levels else current_price * 1.05
            fib_distance = abs(current_price - fib_support) / current_price * 100
            
            # 손익비 계산
            profit_potential = abs(signal['take_profit'] - signal['entry_price'])
            loss_potential = abs(signal['entry_price'] - signal['stop_loss'])
            risk_reward_ratio = profit_potential / loss_potential if loss_potential > 0 else 0
            
            # 완전한 포지션 정보 생성
            position = {
                'symbol': symbol,
                'signal_timestamp': int(datetime.now(timezone.utc).timestamp()),
                'ttl': int(datetime.now(timezone.utc).timestamp()) + 300,  # 5분 후 삭제
                
                # 전략 정보
                'strategy': signal.get('strategy', strategy_type),
                'timeframe': f"{timeframe}m",
                'confidence': signal.get('confidence', 60),
                
                # 포지션 정보
                'position_type': signal['type'],
                'entry_price': signal['entry_price'],
                'stop_loss': signal['stop_loss'],
                'take_profit': signal['take_profit'],
                'position_size': signal['position_size'],
                'leverage': signal['leverage'],
                
                # 기술적 지표
                'rsi': signal.get('rsi', 0),
                'bb_position': signal.get('bb_position', 0),
                'bb_width': signal.get('bb_width', 0),
                
                # 추세 정보
                'btc_trend': signal.get('btc_trend', {}).get('trend', 'UNKNOWN'),
                'btc_change': signal.get('btc_trend', {}).get('price_change_pct', 0),
                'coin_trend': signal.get('coin_trend', {}).get('trend', 'UNKNOWN'),
                'coin_change': signal.get('coin_trend', {}).get('price_change_pct', 0),
                
                # 펀딩비
                'funding_rate': signal.get('funding_info', {}).get('funding_rate', 0),
                'funding_sentiment': signal.get('funding_info', {}).get('sentiment', 'UNKNOWN'),
                
                # 피보나치 레벨
                'fib_support': fib_support,
                'fib_resistance': fib_resistance,
                'fib_distance': round(fib_distance, 2),
                
                # 예상 손익
                'expected_profit': signal.get('expected_profit', 0),
                'expected_loss': signal.get('expected_loss', 0),
                'risk_reward_ratio': round(risk_reward_ratio, 2),
                
                # 메타데이터
                'signal_id': f"signal-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{symbol}",
                'scan_id': message.get('scan_id', ''),
                'created_at': datetime.now(timezone.utc).isoformat(),
                'status': 'active',
                'version': 1
            }
            
            print(f"✅ 포지션 정보 생성 완료")
            return position
            
        except Exception as e:
            print(f"❌ 진입 신호 탐색 실패: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def check_bybit_position_or_order(self, symbol):
        """Bybit에서 해당 심볼의 오픈 포지션 또는 활성 주문 확인"""
        try:
            # 1. 오픈 포지션 확인
            position_result = self.session.get_positions(
                category="linear",
                symbol=symbol
            )
            
            if position_result['retCode'] == 0:
                positions = position_result['result']['list']
                for pos in positions:
                    if float(pos['size']) > 0:
                        print(f"⚠️  {symbol}에 이미 오픈된 포지션이 있습니다:")
                        print(f"  - 사이드: {pos['side']}")
                        print(f"  - 수량: {pos['size']}")
                        print(f"  - 진입가: ${float(pos['avgPrice']):.2f}")
                        return True
            
            # 2. 활성 주문 확인
            order_result = self.session.get_open_orders(
                category="linear",
                symbol=symbol
            )
            
            if order_result['retCode'] == 0:
                orders = order_result['result']['list']
                if orders:
                    print(f"⚠️  {symbol}에 활성 주문이 있습니다:")
                    for order in orders[:3]:  # 최대 3개만 출력
                        print(f"  - Order ID: {order['orderId']}")
                        print(f"  - 타입: {order['side']} {order['orderType']}")
                    return True
            
            return False
            
        except Exception as e:
            print(f"⚠️  Bybit 포지션/주문 확인 실패: {e}")
            # 에러 발생 시 안전하게 False 반환 (포지션 생성 허용)
            return False
    
    def check_existing_position(self, symbol):
        """기존 포지션 확인 (DynamoDB에서 진입 중이거나 실행 중인지)"""
        try:
            # 최근 5분 이내의 포지션 조회
            current_time = int(datetime.now(timezone.utc).timestamp())
            five_minutes_ago = current_time - 300
            
            response = self.positions_table.query(
                KeyConditionExpression='symbol = :symbol AND signal_timestamp >= :ts',
                ExpressionAttributeValues={
                    ':symbol': symbol,
                    ':ts': five_minutes_ago
                },
                ScanIndexForward=False,
                Limit=1
            )
            
            if response['Items']:
                existing = response['Items'][0]
                status = existing.get('status', 'active')
                
                # executing 상태면 진입 중
                if status == 'executing':
                    return 'executing', existing
                
                # active 상태면 기존 포지션과 비교 필요
                if status == 'active':
                    return 'active', existing
            
            return None, None
            
        except Exception as e:
            print(f"⚠️  기존 포지션 확인 실패: {e}")
            return None, None
    
    def positions_are_similar(self, pos1, pos2):
        """두 포지션이 유사한지 확인 (업데이트 필요 여부)"""
        # 진입가 차이가 0.5% 이내면 유사
        price_diff = abs(pos1['entry_price'] - pos2['entry_price']) / pos1['entry_price']
        if price_diff > 0.005:  # 0.5%
            return False
        
        # 포지션 타입이 다르면 다름
        if pos1['position_type'] != pos2['position_type']:
            return False
        
        # 신뢰도 차이가 5점 이내면 유사
        conf_diff = abs(pos1['confidence'] - pos2['confidence'])
        if conf_diff > 5:
            return False
        
        return True
    
    def save_position(self, position):
        """DynamoDB에 포지션 저장 (중복 확인 포함)"""
        symbol = position['symbol']
        
        # 1. Bybit에서 오픈 포지션 또는 활성 주문 확인 (최우선)
        print(f"\n[1/3] Bybit 포지션/주문 확인...")
        if self.check_bybit_position_or_order(symbol):
            print(f"❌ {symbol}은(는) 이미 Bybit에 포지션/주문이 있습니다. 포지션 생성 스킵.\n")
            return False
        
        print(f"✅ Bybit에 {symbol} 포지션/주문 없음")
        
        # 2. DynamoDB에서 기존 포지션 확인
        print(f"[2/3] DynamoDB 포지션 확인...")
        existing_status, existing_position = self.check_existing_position(symbol)
        
        if existing_status == 'executing':
            print(f"⚠️  {symbol}은(는) DynamoDB에서 진입 중입니다. 스킵.")
            print(f"  - 기존 진입가: ${existing_position['entry_price']:.2f}")
            print(f"  - 기존 타입: {existing_position['position_type']}\n")
            return False
        
        if existing_status == 'active':
            # 기존 포지션과 비교
            if self.positions_are_similar(position, existing_position):
                print(f"⚠️  {symbol}의 포지션이 기존과 유사합니다. 업데이트 스킵.")
                print(f"  - 기존 진입가: ${existing_position['entry_price']:.2f}")
                print(f"  - 새 진입가: ${position['entry_price']:.2f}\n")
                return False
            else:
                print(f"🔄 {symbol}의 포지션이 변경되었습니다. 업데이트 진행.")
                print(f"  - 기존: ${existing_position['entry_price']:.2f} ({existing_position['position_type']})")
                print(f"  - 새로: ${position['entry_price']:.2f} ({position['position_type']})")
        
        print(f"✅ DynamoDB에 {symbol} 활성 포지션 없음")
        
        # 3. 포지션 저장
        print(f"[3/3] 포지션 저장...")
        try:
            # Float를 Decimal로 변환
            position = convert_floats_to_decimal(position)
            
            self.positions_table.put_item(Item=position)
            
            print(f"\n💾 DynamoDB 저장 완료:")
            print(f"  - 심볼: {position['symbol']}")
            print(f"  - 타입: {position['position_type']}")
            print(f"  - 진입가: ${float(position['entry_price']):.2f}")
            print(f"  - 신뢰도: {position['confidence']}점")
            print(f"  - 손익비: {float(position['risk_reward_ratio']):.2f}:1\n")
            
            return True
            
        except Exception as e:
            print(f"❌ DynamoDB 저장 실패: {e}")
            return False
    
    def process_message(self, ch, method, properties, body):
        """메시지 처리 콜백"""
        try:
            message = json.loads(body)
            
            print(f"\n{'='*80}")
            print(f"📨 메시지 수신: {message['symbol']}")
            print(f"{'='*80}")
            
            # 진입 신호 탐색
            position = self.find_entry_signal(message)
            
            if position:
                # DynamoDB에 저장
                if self.save_position(position):
                    # ACK (성공)
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    print(f"✅ 처리 완료: {message['symbol']}\n")
                else:
                    # NACK (저장 실패 - 재시도)
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                    print(f"❌ 저장 실패 - 재시도: {message['symbol']}\n")
            else:
                # 신호 없음 - ACK (재시도 불필요)
                ch.basic_ack(delivery_tag=method.delivery_tag)
                print(f"⚠️  신호 없음: {message['symbol']}\n")
            
        except Exception as e:
            print(f"❌ 메시지 처리 실패: {e}")
            # NACK (실패 - 재시도)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    
    def run(self):
        """메인 실행 로직"""
        print(f"\n{'='*80}")
        print(f"🚀 Position Finder Service 시작")
        print(f"{'='*80}")
        print(f"Finder ID: {self.finder_id}")
        print(f"RabbitMQ: {self.rabbitmq_host}:{self.rabbitmq_port}")
        print(f"Queue: {self.queue_name}")
        print(f"Prefetch: {self.prefetch_count}")
        print(f"DynamoDB: {self.positions_table.table_name}")
        print(f"{'='*80}\n")
        
        connection, channel = self.connect_rabbitmq()
        
        try:
            # 메시지 소비 시작
            channel.basic_consume(
                queue=self.queue_name,
                on_message_callback=self.process_message,
                auto_ack=False  # 수동 ACK
            )
            
            print(f"✅ 메시지 대기 중... (Ctrl+C로 종료)\n")
            channel.start_consuming()
            
        except KeyboardInterrupt:
            print(f"\n\n{'='*80}")
            print(f"⏹️  Position Finder Service 종료")
            print(f"{'='*80}\n")
            channel.stop_consuming()
            
        finally:
            connection.close()

if __name__ == "__main__":
    service = PositionFinderService()
    service.run()
