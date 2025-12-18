"""
Scanner Service - 변동성 높은 코인 30개 스캔 및 RabbitMQ 발행
1시간마다 실행 (ECS Scheduled Task)
"""
import os
import json
import time
import boto3
import pika
from decimal import Decimal
from datetime import datetime, timezone
from src.scanning.volatility_scanner import VolatilityScanner
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

class ScannerService:
    def __init__(self):
        self.scanner = VolatilityScanner()
        self.dynamodb = boto3.resource('dynamodb', region_name=os.getenv('AWS_REGION', 'ap-northeast-2'))
        self.results_table = self.dynamodb.Table(os.getenv('DYNAMODB_TABLE', 'crypto-backtest-results'))
        self.history_table = self.dynamodb.Table(os.getenv('DYNAMODB_HISTORY_TABLE', 'crypto-scan-history'))
        
        # RabbitMQ 연결
        self.rabbitmq_host = os.getenv('RABBITMQ_HOST', 'localhost')
        self.rabbitmq_port = int(os.getenv('RABBITMQ_PORT', '5672'))
        self.rabbitmq_user = os.getenv('RABBITMQ_USER', 'guest')
        self.rabbitmq_pass = os.getenv('RABBITMQ_PASS', 'guest')
        self.queue_name = os.getenv('RABBITMQ_QUEUE', 'backtest-tasks')
        
        self.scan_id = f"scan-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        self.scanner_id = os.getenv('HOSTNAME', 'scanner-1')
    
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
        
        # Queue 선언 (durable=True: 재시작 후에도 유지)
        channel.queue_declare(queue=self.queue_name, durable=True)
        
        return connection, channel
    
    def scan_coins(self):
        """변동성 높은 코인 30개 스캔"""
        print(f"\n{'='*80}")
        print(f"🔍 코인 스캔 시작 - {self.scan_id}")
        print(f"{'='*80}\n")
        
        start_time = time.time()
        
        # 변동성 스캔
        scanned_coins = self.scanner.scan_coins()
        
        if scanned_coins.empty:
            print("❌ 스캔된 코인이 없습니다.")
            return []
        
        # 변동성 필터: MIN ~ MAX 범위
        filtered_coins = scanned_coins[
            (scanned_coins['volatility_24h'] >= Config.MIN_VOLATILITY) &
            (scanned_coins['volatility_24h'] <= Config.MAX_VOLATILITY)
        ]
        
        # 상위 30개 선택
        top_30 = filtered_coins.nlargest(30, 'volatility_24h')
        
        scan_duration = time.time() - start_time
        
        print(f"\n✅ 스캔 완료:")
        print(f"  - 전체 코인: {len(scanned_coins)}개")
        print(f"  - 필터링 후: {len(filtered_coins)}개")
        print(f"  - 선택된 코인: {len(top_30)}개")
        print(f"  - 소요 시간: {scan_duration:.2f}초\n")
        
        return top_30, scan_duration
    
    def get_previous_active_coins(self):
        """이전 스캔의 활성 코인 목록 조회"""
        try:
            # 최근 스캔 히스토리 조회 (scan은 ScanIndexForward를 지원하지 않음)
            response = self.history_table.scan(
                Limit=100  # 최근 100개 조회
            )
            
            if response['Items']:
                # scan_timestamp로 정렬하여 최신 항목 선택
                items = sorted(response['Items'], 
                             key=lambda x: x.get('scan_timestamp', 0), 
                             reverse=True)
                if items:
                    latest_scan = items[0]
                    return set(latest_scan.get('selected_coins', []))
            
            return set()
        except Exception as e:
            print(f"⚠️  이전 활성 코인 조회 실패: {e}")
            return set()
    
    def remove_inactive_coins(self, current_coins, previous_coins):
        """이전 스캔에서 제외된 코인 삭제"""
        removed_coins = previous_coins - current_coins
        
        if not removed_coins:
            print("✅ 제외된 코인 없음")
            return []
        
        print(f"\n🗑️  제외된 코인 삭제 중 ({len(removed_coins)}개)...")
        
        deleted_count = 0
        for symbol in removed_coins:
            try:
                # 해당 심볼의 모든 레코드 조회
                response = self.results_table.query(
                    KeyConditionExpression='symbol = :symbol',
                    ExpressionAttributeValues={':symbol': symbol}
                )
                
                # 모든 레코드 삭제
                for item in response['Items']:
                    self.results_table.delete_item(
                        Key={
                            'symbol': symbol,
                            'scan_timestamp': item['scan_timestamp']
                        }
                    )
                    deleted_count += 1
                
                print(f"  ✅ {symbol}: {len(response['Items'])}개 레코드 삭제")
                
            except Exception as e:
                print(f"  ❌ {symbol} 삭제 실패: {e}")
        
        print(f"\n✅ 총 {deleted_count}개 레코드 삭제 완료\n")
        return list(removed_coins)
    
    def publish_tasks(self, coins_df):
        """RabbitMQ에 분석 태스크 발행"""
        print(f"\n📤 RabbitMQ 태스크 발행 중...")
        
        connection, channel = self.connect_rabbitmq()
        
        timeframes = ['1', '3', '5', '15', '30']
        published_count = 0
        
        try:
            for _, coin in coins_df.iterrows():
                for timeframe in timeframes:
                    message = {
                        'scan_id': self.scan_id,
                        'symbol': coin['symbol'],
                        'timeframe': timeframe,
                        'volatility_24h': float(coin['volatility_24h']),
                        'turnover': float(coin['turnover']),
                        'price': float(coin['price']),
                        'price_change_24h': float(coin['price_change_24h']),
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }
                    
                    channel.basic_publish(
                        exchange='',
                        routing_key=self.queue_name,
                        body=json.dumps(message),
                        properties=pika.BasicProperties(
                            delivery_mode=2,  # persistent
                            content_type='application/json'
                        )
                    )
                    
                    published_count += 1
            
            print(f"✅ {published_count}개 태스크 발행 완료")
            print(f"  - 코인: {len(coins_df)}개")
            print(f"  - 타임프레임: {len(timeframes)}개")
            print(f"  - 총 태스크: {published_count}개\n")
            
        finally:
            connection.close()
        
        return published_count
    
    def save_scan_history(self, coins_df, scan_duration, messages_published, removed_coins):
        """스캔 히스토리 저장"""
        print(f"💾 스캔 히스토리 저장 중...")
        
        now = datetime.now(timezone.utc)
        scan_timestamp = int(now.timestamp())
        
        history_item = {
            'scan_id': self.scan_id,
            'scan_timestamp': scan_timestamp,
            'ttl': scan_timestamp + (7 * 24 * 60 * 60),  # 7일 후 삭제
            
            'total_coins_scanned': len(coins_df),
            'selected_coins': coins_df['symbol'].tolist(),
            'removed_coins': removed_coins,
            
            'analysis_status': {
                'total': len(coins_df) * 5,  # 30코인 × 5타임프레임
                'completed': 0,
                'failed': 0,
                'pending': len(coins_df) * 5
            },
            
            'performance': {
                'scan_duration': round(scan_duration, 2),
                'total_analysis_time': 0,
                'avg_analysis_time': 0,
                'messages_published': messages_published
            },
            
            'scanner_id': self.scanner_id,
            'created_at': now.isoformat(),
            'completed_at': None,
            'status': 'running'
        }
        
        try:
            # Float를 Decimal로 변환
            history_item = convert_floats_to_decimal(history_item)
            self.history_table.put_item(Item=history_item)
            print(f"✅ 스캔 히스토리 저장 완료: {self.scan_id}\n")
        except Exception as e:
            print(f"❌ 스캔 히스토리 저장 실패: {e}\n")
    
    def run(self):
        """메인 실행 로직"""
        print(f"\n{'='*80}")
        print(f"🚀 Scanner Service 시작")
        print(f"{'='*80}")
        print(f"Scanner ID: {self.scanner_id}")
        print(f"Scan ID: {self.scan_id}")
        print(f"RabbitMQ: {self.rabbitmq_host}:{self.rabbitmq_port}")
        print(f"DynamoDB: {self.results_table.table_name}")
        print(f"{'='*80}\n")
        
        try:
            # 1. 코인 스캔
            coins_df, scan_duration = self.scan_coins()
            
            if coins_df.empty:
                print("❌ 스캔된 코인이 없어 종료합니다.")
                return
            
            current_coins = set(coins_df['symbol'].tolist())
            
            # 2. 이전 활성 코인 조회
            previous_coins = self.get_previous_active_coins()
            
            # 3. 제외된 코인 삭제
            removed_coins = self.remove_inactive_coins(current_coins, previous_coins)
            
            # 4. RabbitMQ에 태스크 발행
            messages_published = self.publish_tasks(coins_df)
            
            # 5. 스캔 히스토리 저장
            self.save_scan_history(coins_df, scan_duration, messages_published, removed_coins)
            
            print(f"\n{'='*80}")
            print(f"✅ Scanner Service 완료")
            print(f"{'='*80}\n")
            
        except Exception as e:
            print(f"\n{'='*80}")
            print(f"❌ Scanner Service 실패: {e}")
            print(f"{'='*80}\n")
            raise

if __name__ == "__main__":
    service = ScannerService()
    service.run()
