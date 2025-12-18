"""
Strategy Selector Service - DynamoDB에서 최적 전략 조회 및 RabbitMQ 발행
1분마다 실행 (ECS Scheduled Task)
"""
import os
import json
import time
import boto3
import pika
from datetime import datetime, timezone
from decimal import Decimal

class DecimalEncoder(json.JSONEncoder):
    """DynamoDB Decimal을 JSON으로 변환"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

class StrategySelectorService:
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb', region_name=os.getenv('AWS_REGION', 'ap-northeast-2'))
        self.results_table = self.dynamodb.Table(os.getenv('DYNAMODB_TABLE', 'crypto-backtest-results'))
        
        # RabbitMQ 연결
        self.rabbitmq_host = os.getenv('RABBITMQ_HOST', 'localhost')
        self.rabbitmq_port = int(os.getenv('RABBITMQ_PORT', '5672'))
        self.rabbitmq_user = os.getenv('RABBITMQ_USER', 'guest')
        self.rabbitmq_pass = os.getenv('RABBITMQ_PASS', 'guest')
        self.queue_name = os.getenv('RABBITMQ_TRADING_QUEUE', 'trading-signals')
        
        self.selector_id = os.getenv('HOSTNAME', 'selector-1')
        
        # 필터 기준
        self.min_win_rate = float(os.getenv('MIN_WIN_RATE', '45.0'))  # 최소 승률 45%
        self.min_pnl = float(os.getenv('MIN_PNL', '100.0'))  # 최소 수익 $100
        self.min_trades = int(os.getenv('MIN_TRADES', '20'))  # 최소 거래 수 20개
    
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
        
        return connection, channel
    
    def get_active_strategies(self):
        """DynamoDB에서 활성 전략 조회"""
        print(f"\n{'='*80}")
        print(f"🔍 활성 전략 조회 중...")
        print(f"{'='*80}\n")
        
        try:
            # StatusIndex를 사용하여 활성 코인 조회
            response = self.results_table.query(
                IndexName='StatusIndex',
                KeyConditionExpression='#status = :status',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={':status': 'active'},
                ScanIndexForward=False  # 최신순
            )
            
            items = response.get('Items', [])
            
            if not items:
                print("⚠️  활성 전략이 없습니다.")
                return []
            
            print(f"✅ {len(items)}개 코인 발견\n")
            
            # 각 코인의 최적 전략 필터링
            strategies = []
            
            for item in items:
                symbol = item['symbol']
                optimal_timeframe = item.get('optimal_timeframe', '1m')
                optimal_pnl = float(item.get('optimal_pnl', 0))
                optimal_win_rate = float(item.get('optimal_win_rate', 0))
                
                # 타임프레임 데이터 가져오기
                timeframes = item.get('timeframes', {})
                tf_data = timeframes.get(optimal_timeframe, {})
                
                total_trades = int(tf_data.get('total_trades', 0))
                best_strategy = tf_data.get('best_strategy', 'BASIC')
                confidence_avg = float(tf_data.get('confidence_avg', 0))
                
                # 필터 조건 확인
                if (optimal_win_rate >= self.min_win_rate and 
                    optimal_pnl >= self.min_pnl and 
                    total_trades >= self.min_trades):
                    
                    strategies.append({
                        'symbol': symbol,
                        'timeframe': optimal_timeframe,
                        'strategy': best_strategy,
                        'win_rate': optimal_win_rate,
                        'total_pnl': optimal_pnl,
                        'total_trades': total_trades,
                        'confidence_avg': confidence_avg,
                        'scan_id': item.get('scan_id', ''),
                        'volatility_24h': float(item.get('volatility_24h', 0)),
                        'price': float(item.get('price', 0))
                    })
                    
                    print(f"✅ {symbol}: {optimal_timeframe} ({best_strategy}) - "
                          f"승률 {optimal_win_rate:.1f}%, 수익 ${optimal_pnl:.2f}")
                else:
                    print(f"❌ {symbol}: 필터 조건 미달 - "
                          f"승률 {optimal_win_rate:.1f}%, 수익 ${optimal_pnl:.2f}, 거래 {total_trades}개")
            
            print(f"\n✅ 필터링 완료: {len(strategies)}개 전략 선택\n")
            return strategies
            
        except Exception as e:
            print(f"❌ 전략 조회 실패: {e}")
            return []
    
    def publish_trading_signals(self, strategies):
        """RabbitMQ에 트레이딩 신호 발행"""
        if not strategies:
            print("⚠️  발행할 전략이 없습니다.")
            return 0
        
        print(f"\n📤 트레이딩 신호 발행 중...")
        
        connection, channel = self.connect_rabbitmq()
        published_count = 0
        
        try:
            for strategy in strategies:
                message = {
                    'selector_id': self.selector_id,
                    'symbol': strategy['symbol'],
                    'timeframe': strategy['timeframe'],
                    'strategy': strategy['strategy'],
                    'win_rate': strategy['win_rate'],
                    'total_pnl': strategy['total_pnl'],
                    'confidence_avg': strategy['confidence_avg'],
                    'scan_id': strategy['scan_id'],
                    'volatility_24h': strategy['volatility_24h'],
                    'price': strategy['price'],
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                
                channel.basic_publish(
                    exchange='',
                    routing_key=self.queue_name,
                    body=json.dumps(message, cls=DecimalEncoder),
                    properties=pika.BasicProperties(
                        delivery_mode=2,  # persistent
                        content_type='application/json'
                    )
                )
                
                published_count += 1
                print(f"  ✅ {strategy['symbol']}: {strategy['timeframe']} ({strategy['strategy']})")
            
            print(f"\n✅ {published_count}개 신호 발행 완료\n")
            
        finally:
            connection.close()
        
        return published_count
    
    def run(self):
        """메인 실행 로직"""
        print(f"\n{'='*80}")
        print(f"🚀 Strategy Selector Service 시작")
        print(f"{'='*80}")
        print(f"Selector ID: {self.selector_id}")
        print(f"RabbitMQ: {self.rabbitmq_host}:{self.rabbitmq_port}")
        print(f"Queue: {self.queue_name}")
        print(f"필터 조건:")
        print(f"  - 최소 승률: {self.min_win_rate}%")
        print(f"  - 최소 수익: ${self.min_pnl}")
        print(f"  - 최소 거래: {self.min_trades}개")
        print(f"{'='*80}\n")
        
        try:
            # 1. 활성 전략 조회
            strategies = self.get_active_strategies()
            
            # 2. RabbitMQ에 신호 발행
            published = self.publish_trading_signals(strategies)
            
            print(f"\n{'='*80}")
            print(f"✅ Strategy Selector Service 완료")
            print(f"  - 조회된 전략: {len(strategies)}개")
            print(f"  - 발행된 신호: {published}개")
            print(f"{'='*80}\n")
            
        except Exception as e:
            print(f"\n{'='*80}")
            print(f"❌ Strategy Selector Service 실패: {e}")
            print(f"{'='*80}\n")
            raise

if __name__ == "__main__":
    service = StrategySelectorService()
    service.run()
