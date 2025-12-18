# 🚀 Crypto Trading System - 배포 완료

## 배포 일시
- **배포 완료**: 2024-12-17 06:54 UTC
- **배포 방식**: Terraform + Docker (ECR)
- **리전**: ap-northeast-2 (Seoul)

## ✅ 배포된 리소스

### 1. ECS 클러스터
- **클러스터 이름**: `crypto-backtest-cluster`
- **상태**: ACTIVE
- **Container Insights**: 활성화

### 2. ECS 서비스 (5개)

#### Scanner Service
- **실행 방식**: EventBridge (1시간마다)
- **Task Definition**: crypto-backtest-scanner
- **CPU/Memory**: 512/1024
- **역할**: 변동성 높은 코인 30개 스캔 → RabbitMQ 발행

#### Analyzer Service
- **실행 방식**: ECS Service (Auto-scaling 1-10)
- **Task Definition**: crypto-backtest-analyzer
- **CPU/Memory**: 1024/2048
- **역할**: RabbitMQ에서 코인 수신 → 1,3,5,15,30분 백테스팅 → DynamoDB 저장

#### Strategy Selector Service
- **실행 방식**: EventBridge (1분마다)
- **Task Definition**: crypto-backtest-selector
- **CPU/Memory**: 256/512
- **역할**: DynamoDB에서 최적 전략 조회 → RabbitMQ 발행

#### Position Finder Service
- **실행 방식**: ECS Service (Auto-scaling 1-5)
- **Task Definition**: crypto-backtest-finder
- **CPU/Memory**: 512/1024
- **역할**: RabbitMQ에서 전략 수신 → 진입 신호 탐색 → DynamoDB 저장

#### Order Executor Service
- **실행 방식**: ECS Service (1개 고정)
- **Task Definition**: crypto-backtest-executor
- **CPU/Memory**: 256/512
- **역할**: DynamoDB 스캔 (5초마다) → 진입 조건 확인 → 실제 주문 실행

### 3. DynamoDB 테이블 (3개)

#### crypto-backtest-results
- **용도**: 백테스팅 결과 저장
- **Primary Key**: symbol (Hash), scan_timestamp (Range)
- **GSI**: ScanIdIndex, OptimalTimeframeIndex, StatusIndex
- **TTL**: 활성화

#### crypto-backtest-scan-history
- **용도**: 스캔 이력 저장
- **Primary Key**: scan_id (Hash)
- **TTL**: 활성화

#### crypto-backtest-trading-positions
- **용도**: 진입 포지션 저장
- **Primary Key**: symbol (Hash), signal_timestamp (Range)
- **GSI**: StatusIndex, ConfidenceIndex
- **TTL**: 5분 (자동 삭제)

### 4. Amazon MQ (RabbitMQ)
- **Broker ID**: b-6ecaed19-1e36-40bc-b2e7-066c27f094f3
- **Engine**: RabbitMQ 3.13
- **Instance Type**: mq.t3.micro
- **Deployment Mode**: SINGLE_INSTANCE
- **Endpoint**: amqps://b-6ecaed19-1e36-40bc-b2e7-066c27f094f3.mq.ap-northeast-2.on.aws:5671
- **Queues**:
  - `backtest-tasks`: Scanner → Analyzer
  - `trading-signals`: Selector → Finder

### 5. ECR 리포지토리 (5개)
- crypto-backtest-scanner:latest
- crypto-backtest-analyzer:latest
- crypto-backtest-selector:latest
- crypto-backtest-finder:latest
- crypto-backtest-executor:latest

### 6. CloudWatch Log Groups (5개)
- /ecs/crypto-backtest-scanner
- /ecs/crypto-backtest-analyzer
- /ecs/crypto-backtest-selector
- /ecs/crypto-backtest-finder
- /ecs/crypto-backtest-executor
- **Retention**: 7일

### 7. EventBridge Rules (2개)
- **crypto-backtest-scanner-schedule**: rate(1 hour)
- **crypto-backtest-selector-schedule**: rate(1 minute)

### 8. IAM Roles (3개)
- crypto-backtest-ecs-task-execution
- crypto-backtest-ecs-task
- crypto-backtest-eventbridge-ecs

### 9. Security Groups (2개)
- crypto-backtest-ecs-tasks
- crypto-backtest-rabbitmq

### 10. Auto Scaling (2개)
- Analyzer: 1-10 (CPU 70%)
- Finder: 1-5 (CPU 70%)

## 🔐 Secrets Manager
- crypto-backtest/bybit-api-key
- crypto-backtest/bybit-api-secret
- crypto-backtest/bybit-testnet

## 📊 시스템 흐름

```
1. Scanner (1시간마다)
   ↓ RabbitMQ (backtest-tasks)
2. Analyzer (Auto-scaling 1-10)
   ↓ DynamoDB (results)
3. Selector (1분마다)
   ↓ RabbitMQ (trading-signals)
4. Finder (Auto-scaling 1-5)
   ↓ DynamoDB (trading-positions)
5. Executor (5초마다 스캔)
   ↓ Bybit API (실제 주문)
```

## 🔍 모니터링 및 로그 확인

### ECS 서비스 상태 확인
```bash
aws ecs describe-services \
  --cluster crypto-backtest-cluster \
  --services crypto-backtest-analyzer crypto-backtest-finder crypto-backtest-executor \
  --region ap-northeast-2
```

### CloudWatch 로그 확인
```bash
# Scanner 로그
aws logs tail /ecs/crypto-backtest-scanner --follow --region ap-northeast-2

# Analyzer 로그
aws logs tail /ecs/crypto-backtest-analyzer --follow --region ap-northeast-2

# Selector 로그
aws logs tail /ecs/crypto-backtest-selector --follow --region ap-northeast-2

# Finder 로그
aws logs tail /ecs/crypto-backtest-finder --follow --region ap-northeast-2

# Executor 로그
aws logs tail /ecs/crypto-backtest-executor --follow --region ap-northeast-2
```

### DynamoDB 데이터 확인
```bash
# 백테스팅 결과 확인
aws dynamodb scan \
  --table-name crypto-backtest-results \
  --max-items 5 \
  --region ap-northeast-2

# 진입 포지션 확인
aws dynamodb scan \
  --table-name crypto-backtest-trading-positions \
  --max-items 5 \
  --region ap-northeast-2
```

### RabbitMQ 관리 콘솔
- URL: https://b-6ecaed19-1e36-40bc-b2e7-066c27f094f3.mq.ap-northeast-2.on.aws
- Username: admin
- Password: (Terraform output에서 확인)

```bash
# RabbitMQ 비밀번호 확인
cd infrastructure/terraform
terraform output rabbitmq_password
```

## 🧪 테스트

### Scanner 수동 실행
```bash
aws ecs run-task \
  --cluster crypto-backtest-cluster \
  --task-definition crypto-backtest-scanner \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-0a96d24968cc72110,subnet-0fe37d8893503c639],securityGroups=[sg-06038f745d8c8734c],assignPublicIp=ENABLED}" \
  --region ap-northeast-2
```

### Selector 수동 실행
```bash
aws ecs run-task \
  --cluster crypto-backtest-cluster \
  --task-definition crypto-backtest-selector \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-0a96d24968cc72110,subnet-0fe37d8893503c639],securityGroups=[sg-06038f745d8c8734c],assignPublicIp=ENABLED}" \
  --region ap-northeast-2
```

## ⚙️ 설정 파라미터

### Scanner
- TOP_N_COINS: 30
- VOLATILITY_PERIOD: 24h

### Analyzer
- TIMEFRAMES: 1, 3, 5, 15, 30분
- PREFETCH_COUNT: 1

### Selector
- MIN_WIN_RATE: 45%
- MIN_PNL: $100
- MIN_TRADES: 20

### Finder
- PREFETCH_COUNT: 1

### Executor
- POSITION_SIZE: $100
- LEVERAGE: 10x
- SCAN_INTERVAL: 5초
- PRICE_TOLERANCE: ±0.2%
- MIN_CONFIDENCE: 75점

## 📝 다음 단계

1. **Scanner 실행 확인**
   - 1시간 후 자동 실행 확인
   - 또는 수동 실행으로 테스트

2. **로그 모니터링**
   - CloudWatch Logs에서 각 서비스 로그 확인
   - 에러 발생 시 즉시 대응

3. **DynamoDB 데이터 확인**
   - 백테스팅 결과가 정상적으로 저장되는지 확인
   - 진입 포지션이 생성되는지 확인

4. **주문 실행 모니터링**
   - Executor 로그에서 주문 실행 확인
   - Bybit 계정에서 실제 포지션 확인

5. **성능 최적화**
   - Auto-scaling 동작 확인
   - 필요시 CPU/Memory 조정

## 🚨 주의사항

1. **실제 거래 중**: BYBIT_TESTNET=False로 설정되어 있습니다.
2. **레버리지 10x**: 높은 레버리지로 인한 리스크 주의
3. **포지션 크기**: 매 진입마다 $100 고정
4. **TTL 설정**: trading-positions는 5분 후 자동 삭제됩니다.

## 📚 관련 문서
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - 배포 가이드
- [TRADING_SYSTEM_GUIDE.md](TRADING_SYSTEM_GUIDE.md) - 트레이딩 시스템 가이드
- [ORDER_EXECUTION_GUIDE.md](ORDER_EXECUTION_GUIDE.md) - 주문 실행 가이드
- [BACKTEST_IMPROVEMENTS.md](BACKTEST_IMPROVEMENTS.md) - 백테스팅 개선 사항

## 🎉 배포 완료!

전체 시스템이 성공적으로 배포되었습니다. 이제 자동으로 다음과 같이 동작합니다:

1. **1시간마다**: Scanner가 변동성 높은 코인 30개를 스캔
2. **자동**: Analyzer가 백테스팅 수행 및 결과 저장
3. **1분마다**: Selector가 최적 전략 선택 및 발행
4. **자동**: Finder가 진입 신호 탐색 및 저장
5. **5초마다**: Executor가 진입 조건 확인 및 주문 실행

모든 서비스가 정상적으로 실행 중입니다! 🚀
