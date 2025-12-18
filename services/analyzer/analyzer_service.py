"""
Analyzer Service - RabbitMQ에서 태스크를 가져와 백테스팅 수행
Auto-scaling으로 1-10개 컨테이너 실행
"""
import os
import json
import time
import boto3
import pika
from decimal import Decimal
from datetime import datetime, timezone
from src.backtesting.backtest_engine import BacktestEngine
from config.config import Config
import pandas as pd

def convert_floats_to_decimal(obj):
    """재귀적으로 float를 Decimal로 변환"""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimal(item) for item in obj]
    return obj

class AnalyzerService:
    def __init__(self):
        self.engine = BacktestEngine()
        self.dynamodb = boto3.resource('dynamodb', region_name=os.getenv('AWS_REGION', 'ap-northeast-2'))
        self.results_table = self.dynamodb.Table(os.getenv('DYNAMODB_TABLE', 'crypto-backtest-results'))
        self.history_table = self.dynamodb.Table(os.getenv('DYNAMODB_HISTORY_TABLE', 'crypto-scan-history'))
        
        # RabbitMQ 연결
        self.rabbitmq_host = os.getenv('RABBITMQ_HOST', 'localhost')
        self.rabbitmq_port = int(os.getenv('RABBITMQ_PORT', '5672'))
        self.rabbitmq_user = os.getenv('RABBITMQ_USER', 'guest')
        self.rabbitmq_pass = os.getenv('RABBITMQ_PASS', 'guest')
        self.queue_name = os.getenv('RABBITMQ_QUEUE', 'backtest-tasks')
        
        self.analyzer_id = os.getenv('HOSTNAME', 'analyzer-1')
        self.prefetch_count = int(os.getenv('PREFETCH_COUNT', '1'))  # 동시 처리 수
    
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
        
        # Prefetch 설정 (한 번에 가져올 메시지 수)
        channel.basic_qos(prefetch_count=self.prefetch_count)
        
        return connection, channel
    
    def analyze_coin(self, message):
        """코인 백테스팅 수행"""
        scan_id = message['scan_id']
        symbol = message['symbol']
        timeframe = message['timeframe']
        
        print(f"\n{'='*80}")
        print(f"📊 분석 시작: {symbol} ({timeframe}분봉)")
        print(f"{'='*80}\n")
        
        start_time = time.time()
        
        try:
            # 백테스팅 실행
            self.engine.trades = []  # 초기화
            self.engine.total_pnl = 0.0
            self.engine.run_backtest(
                symbols=[symbol],
                candles=Config.BACKTEST_CANDLES,
                timeframe=timeframe
            )
            
            analysis_time = time.time() - start_time
            
            # 결과 집계
            if self.engine.trades:
                df = pd.DataFrame(self.engine.trades)
                
                total_trades = len(df)
                wins = len(df[df['result'] == 'WIN'])
                win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
                total_pnl = df['net_pnl'].sum()
                avg_win = df[df['result'] == 'WIN']['net_pnl'].mean() if wins > 0 else 0
                avg_loss = df[df['result'] == 'LOSS']['net_pnl'].mean() if total_trades > wins else 0
                
                # 신뢰도 평균
                confidence_avg = df['confidence'].mean() if 'confidence' in df.columns else 0
                
                # 가장 많이 사용된 전략
                if 'strategy' in df.columns:
                    best_strategy = df['strategy'].mode()[0] if not df['strategy'].mode().empty else 'UNKNOWN'
                else:
                    best_strategy = 'UNKNOWN'
                
                result = {
                    'total_trades': total_trades,
                    'win_rate': round(win_rate, 2),
                    'total_pnl': round(total_pnl, 2),
                    'avg_win': round(avg_win, 2),
                    'avg_loss': round(avg_loss, 2),
                    'confidence_avg': round(confidence_avg, 2),
                    'best_strategy': best_strategy,
                    'analysis_time': round(analysis_time, 2),
                    'status': 'completed'
                }
            else:
                result = {
                    'total_trades': 0,
                    'win_rate': 0,
                    'total_pnl': 0,
                    'avg_win': 0,
                    'avg_loss': 0,
                    'confidence_avg': 0,
                    'best_strategy': 'NONE',
                    'analysis_time': round(analysis_time, 2),
                    'status': 'no_trades'
                }
            
            print(f"\n✅ 분석 완료: {symbol} ({timeframe}분봉)")
            print(f"  - 거래 수: {result['total_trades']}")
            print(f"  - 승률: {result['win_rate']}%")
            print(f"  - 수익: ${result['total_pnl']}")
            print(f"  - 소요 시간: {result['analysis_time']}초\n")
            
            return result
            
        except Exception as e:
            print(f"\n❌ 분석 실패: {symbol} ({timeframe}분봉) - {e}\n")
            return {
                'total_trades': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'confidence_avg': 0,
                'best_strategy': 'ERROR',
                'analysis_time': round(time.time() - start_time, 2),
                'status': 'failed',
                'error': str(e)
            }
    
    def save_result(self, message, timeframe_result):
        """DynamoDB에 결과 저장"""
        scan_id = message['scan_id']
        symbol = message['symbol']
        timeframe = message['timeframe']
        scan_timestamp = int(datetime.now(timezone.utc).timestamp())
        
        try:
            # 기존 레코드 조회 (같은 scan_id의 다른 타임프레임 결과가 있을 수 있음)
            response = self.results_table.query(
                KeyConditionExpression='symbol = :symbol AND scan_timestamp >= :ts',
                ExpressionAttributeValues={
                    ':symbol': symbol,
                    ':ts': scan_timestamp - 3600  # 1시간 이내
                },
                ScanIndexForward=False,
                Limit=1
            )
            
            if response['Items']:
                # 기존 레코드 업데이트
                existing_item = response['Items'][0]
                timeframes = existing_item.get('timeframes', {})
                timeframes[f"{timeframe}m"] = timeframe_result
                
                # 최적 타임프레임 계산
                best_tf = max(timeframes.items(), key=lambda x: x[1]['total_pnl'])
                
                # Float를 Decimal로 변환
                update_values = {
                    ':tf': convert_floats_to_decimal(timeframes),
                    ':opt_tf': best_tf[0],
                    ':opt_pnl': convert_floats_to_decimal(best_tf[1]['total_pnl']),
                    ':opt_wr': convert_floats_to_decimal(best_tf[1]['win_rate']),
                    ':updated': datetime.now(timezone.utc).isoformat()
                }
                
                self.results_table.update_item(
                    Key={
                        'symbol': symbol,
                        'scan_timestamp': existing_item['scan_timestamp']
                    },
                    UpdateExpression='SET timeframes = :tf, optimal_timeframe = :opt_tf, '
                                   'optimal_pnl = :opt_pnl, optimal_win_rate = :opt_wr, '
                                   'updated_at = :updated',
                    ExpressionAttributeValues=update_values
                )
                
                print(f"✅ DynamoDB 업데이트: {symbol} ({timeframe}분봉)")
                
            else:
                # 새 레코드 생성
                item = {
                    'symbol': symbol,
                    'scan_timestamp': scan_timestamp,
                    'ttl': scan_timestamp + (24 * 60 * 60),  # 24시간 후 삭제
                    
                    'volatility_24h': message['volatility_24h'],
                    'turnover': message['turnover'],
                    'price': message['price'],
                    'price_change_24h': message['price_change_24h'],
                    
                    'timeframes': {
                        f"{timeframe}m": timeframe_result
                    },
                    
                    'optimal_timeframe': f"{timeframe}m",
                    'optimal_pnl': timeframe_result['total_pnl'],
                    'optimal_win_rate': timeframe_result['win_rate'],
                    
                    'scan_id': scan_id,
                    'analyzer_id': self.analyzer_id,
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'updated_at': datetime.now(timezone.utc).isoformat(),
                    'version': 1,
                    'status': 'active'
                }
                
                # Float를 Decimal로 변환
                item = convert_floats_to_decimal(item)
                
                self.results_table.put_item(Item=item)
                print(f"✅ DynamoDB 저장: {symbol} ({timeframe}분봉)")
                
        except Exception as e:
            print(f"❌ DynamoDB 저장 실패: {symbol} ({timeframe}분봉) - {e}")
    
    def process_message(self, ch, method, properties, body):
        """메시지 처리 콜백"""
        try:
            message = json.loads(body)
            
            # 백테스팅 수행
            result = self.analyze_coin(message)
            
            # DynamoDB에 저장
            self.save_result(message, result)
            
            # ACK (성공)
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
        except Exception as e:
            print(f"❌ 메시지 처리 실패: {e}")
            # NACK (실패 - 재시도)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    
    def run(self):
        """메인 실행 로직"""
        print(f"\n{'='*80}")
        print(f"🚀 Analyzer Service 시작")
        print(f"{'='*80}")
        print(f"Analyzer ID: {self.analyzer_id}")
        print(f"RabbitMQ: {self.rabbitmq_host}:{self.rabbitmq_port}")
        print(f"Queue: {self.queue_name}")
        print(f"Prefetch: {self.prefetch_count}")
        print(f"DynamoDB: {self.results_table.table_name}")
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
            print(f"⏹️  Analyzer Service 종료")
            print(f"{'='*80}\n")
            channel.stop_consuming()
            
        finally:
            connection.close()

if __name__ == "__main__":
    service = AnalyzerService()
    service.run()
