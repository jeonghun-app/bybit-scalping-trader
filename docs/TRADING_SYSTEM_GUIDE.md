# 🎯 실시간 트레이딩 시스템 가이드

## 📊 전체 아키텍처

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Phase 1: 백테스팅 (분석)                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  Scanner Service (1시간마다)                                             │
│    ↓ 변동성 30개 코인 스캔                                               │
│    ↓ RabbitMQ: backtest-tasks (150개 메시지)                            │
│  Analyzer Service (Auto-scaling 1-10)                                    │
│    ↓ 1,3,5,15,30분 백테스팅                                             │
│    ↓ DynamoDB: crypto-backtest-results                                   │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                      Phase 2: 실시간 트레이딩 (실행)                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  Strategy Selector Service (1분마다)                                     │
│    ↓ DynamoDB 조회 (최적 전략)                                           │
│    ↓ 필터링 (승률 45%+, 수익 $100+, 거래 20+)                           │
│    ↓ RabbitMQ: trading-signals (N개 메시지)                             │
│  Position Finder Service (Auto-scaling 1-5)                              │
│    ↓ 실시간 캔들 데이터 조회                                             │
│    ↓ 진입 신호 탐색 (전략 적용)                                          │
│    ↓ DynamoDB: crypto-trading-positions                                  │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 데이터 흐름

### 1. 백테스팅 단계 (1시간마다)
```
Scanner → RabbitMQ(backtest-tasks) → Analyzer → DynamoDB(results)
```

**결과 예시:**
```json
{
  "symbol": "BTCUSDT",
  "optimal_timeframe": "1m",
  "optimal_pnl": 679.20,
  "optimal_win_rate": 56.4,
  "timeframes": {
    "1m": { "win_rate": 56.4, "total_pnl": 679.20, "best_strategy": "ADVANCED" },
    "3m": { "win_rate": 42.1, "total_pnl": -123.40, "best_strategy": "BASIC" }
  }
}
```

### 2. 전략 선택 단계 (1분마다)
```
Strategy Selector → DynamoDB 조회 → 필터링 → RabbitMQ(trading-signals)
```

**필터 조건:**
- 승률 ≥ 45%
- 총 수익 ≥ $100
- 거래 수 ≥ 20개

**메시지 예시:**
```json
{
  "symbol": "BTCUSDT",
  "timeframe": "1m",
  "strategy": "ADVANCED",
  "win_rate": 56.4,
  "total_pnl": 679.20,
  "confidence_avg": 85.5
}
```

### 3. 포지션 탐색 단계 (실시간)
```
Position Finder → Bybit API → 진입 신호 분석 → DynamoDB(positions)
```

**포지션 예시:**
```json
{
  "symbol": "BTCUSDT",
  "position_type": "LONG",
  "entry_price": 86623.60,
  "stop_loss": 85757.96,
  "take_profit": 88356.07,
  "confidence": 85.5,
  "risk_reward_ratio": 2.0,
  "ttl": 1702800300  // 5분 후 자동 삭제
}
```

---

## 🚀 배포 방법

### Step 1: 기존 인프라 확인
```bash
# 백테스팅 시스템이 이미 배포되어 있어야 함
aws ecs describe-clusters --clusters crypto-backtest-cluster --region ap-northeast-2
```

### Step 2: 새 Docker 이미지 빌드
```bash
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=ap-northeast-2

# Strategy Selector 이미지
docker build -f Dockerfile.selector -t crypto-backtest-selector:latest .
docker tag crypto-backtest-selector:latest \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/crypto-backtest-selector:latest
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/crypto-backtest-selector:latest

# Position Finder 이미지
docker build -f Dockerfile.finder -t crypto-backtest-finder:latest .
docker tag crypto-backtest-finder:latest \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/crypto-backtest-finder:latest
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/crypto-backtest-finder:latest
```

### Step 3: Terraform 업데이트
```bash
cd infrastructure/terraform

# 변경 사항 확인
terraform plan

# 배포
terraform apply
```

**새로 생성되는 리소스:**
- ✅ DynamoDB: crypto-trading-positions
- ✅ ECS Task: crypto-backtest-selector
- ✅ ECS Service: crypto-backtest-finder
- ✅ EventBridge: selector-schedule (1분마다)
- ✅ RabbitMQ Queue: trading-signals

---

## 🔍 모니터링

### 1. Strategy Selector 로그
```bash
aws logs tail /ecs/crypto-backtest-selector --follow --region ap-northeast-2
```

**예상 출력:**
```
🔍 활성 전략 조회 중...
✅ 15개 코인 발견
✅ BTCUSDT: 1m (ADVANCED) - 승률 56.4%, 수익 $679.20
✅ ETHUSDT: 3m (BASIC) - 승률 48.2%, 수익 $234.50
❌ DOGEUSDT: 필터 조건 미달 - 승률 38.5%, 수익 $-45.20
✅ 필터링 완료: 12개 전략 선택
📤 트레이딩 신호 발행 중...
✅ 12개 신호 발행 완료
```

### 2. Position Finder 로그
```bash
aws logs tail /ecs/crypto-backtest-finder --follow --region ap-northeast-2
```

**예상 출력:**
```
📨 메시지 수신: BTCUSDT
🔍 진입 신호 탐색: BTCUSDT (1분봉, ADVANCED)
[1/4] 캔들 데이터 로딩... ✅ 200개 봉 로딩 완료
[2/4] 피보나치 계산... ✅ 5개 타임프레임 피보나치 완료
[3/4] 진입 신호 분석... ✅ 진입 신호 발견!
  - 타입: LONG
  - 진입가: $86623.60
  - 손절가: $85757.96
  - 익절가: $88356.07
  - 신뢰도: 85점
[4/4] 추가 정보 수집... ✅ 포지션 정보 생성 완료
💾 DynamoDB 저장 완료
✅ 처리 완료: BTCUSDT
```

### 3. DynamoDB 포지션 조회
```bash
# 활성 포지션 조회
aws dynamodb query \
  --table-name crypto-backtest-trading-positions \
  --index-name StatusIndex \
  --key-condition-expression "#status = :status" \
  --expression-attribute-names '{"#status":"status"}' \
  --expression-attribute-values '{":status":{"S":"active"}}' \
  --scan-index-forward false \
  --limit 10 \
  --region ap-northeast-2
```

### 4. 신뢰도 높은 포지션 조회
```bash
# 신뢰도 80점 이상
aws dynamodb query \
  --table-name crypto-backtest-trading-positions \
  --index-name ConfidenceIndex \
  --key-condition-expression "#status = :status AND confidence >= :conf" \
  --expression-attribute-names '{"#status":"status"}' \
  --expression-attribute-values '{":status":{"S":"active"},":conf":{"N":"80"}}' \
  --scan-index-forward false \
  --region ap-northeast-2
```

---

## 📊 성능 메트릭

### 예상 처리량
- **Strategy Selector**: 1분마다 실행, 평균 5초 소요
- **Position Finder**: 초당 1-2개 신호 처리
- **DynamoDB 쓰기**: 분당 10-20개 포지션

### 지연 시간
- 백테스트 결과 → 전략 선택: 최대 1분
- 전략 선택 → 포지션 생성: 5-10초
- 총 지연: 1-2분 (실시간에 가까움)

---

## 🎯 실전 활용

### 1. 포지션 조회 API (Lambda 추가 권장)
```python
import boto3

def get_active_positions():
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('crypto-backtest-trading-positions')
    
    response = table.query(
        IndexName='StatusIndex',
        KeyConditionExpression='#status = :status',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={':status': 'active'},
        ScanIndexForward=False
    )
    
    return response['Items']
```

### 2. 자동 주문 실행 (별도 서비스 필요)
```python
# 예시: Bybit 자동 주문
def execute_position(position):
    from pybit.unified_trading import HTTP
    
    session = HTTP(
        testnet=False,
        api_key="YOUR_KEY",
        api_secret="YOUR_SECRET"
    )
    
    # 주문 실행
    order = session.place_order(
        category="linear",
        symbol=position['symbol'],
        side="Buy" if position['position_type'] == 'LONG' else "Sell",
        orderType="Market",
        qty=calculate_qty(position['position_size'], position['entry_price']),
        stopLoss=str(position['stop_loss']),
        takeProfit=str(position['take_profit'])
    )
    
    return order
```

### 3. 알림 시스템 (SNS 연동)
```python
# DynamoDB Stream → Lambda → SNS
def send_alert(position):
    import boto3
    
    sns = boto3.client('sns')
    
    message = f"""
    🚨 새로운 진입 신호!
    
    심볼: {position['symbol']}
    타입: {position['position_type']}
    진입가: ${position['entry_price']:.2f}
    손절가: ${position['stop_loss']:.2f}
    익절가: ${position['take_profit']:.2f}
    신뢰도: {position['confidence']}점
    손익비: {position['risk_reward_ratio']:.2f}:1
    """
    
    sns.publish(
        TopicArn='arn:aws:sns:ap-northeast-2:ACCOUNT_ID:trading-alerts',
        Subject='진입 신호 알림',
        Message=message
    )
```

---

## ⚠️ 주의사항

### 1. 백테스트 vs 실전
- 백테스트 결과가 실전 성과를 보장하지 않음
- 슬리피지, 체결 지연 고려 필요
- 시장 상황 변화에 따라 전략 효과 감소 가능

### 2. 리스크 관리
- 포지션 크기 제한 (총 자본의 1-2%)
- 동시 포지션 수 제한 (최대 5-10개)
- 일일 손실 한도 설정

### 3. 모니터링
- CloudWatch 알람 설정 (오류율, 지연 시간)
- DynamoDB 용량 모니터링
- RabbitMQ 큐 길이 모니터링

---

## 💰 추가 비용

기존 백테스팅 시스템 ($135/월)에 추가:
- **Strategy Selector**: $5/월 (1분마다 5초 실행)
- **Position Finder**: $30/월 (평균 2개 컨테이너)
- **DynamoDB (Positions)**: $3/월
- **추가 데이터 전송**: $2/월

**총 추가 비용: ~$40/월**
**전체 비용: ~$175/월**

---

## 🔧 트러블슈팅

### 문제 1: 포지션이 생성되지 않음
```bash
# Strategy Selector 로그 확인
aws logs tail /ecs/crypto-backtest-selector --follow --region ap-northeast-2

# 필터 조건 완화 (환경 변수)
MIN_WIN_RATE=40.0
MIN_PNL=50.0
MIN_TRADES=10
```

### 문제 2: 지연 시간이 너무 김
```bash
# Position Finder 스케일 아웃
aws ecs update-service \
  --cluster crypto-backtest-cluster \
  --service crypto-backtest-finder \
  --desired-count 5 \
  --region ap-northeast-2
```

### 문제 3: DynamoDB 쓰기 제한
```bash
# On-Demand 모드 확인
aws dynamodb describe-table \
  --table-name crypto-backtest-trading-positions \
  --region ap-northeast-2
```

---

## 📚 다음 단계

1. **자동 주문 실행 시스템** 구축
2. **포지션 관리 시스템** (진입 후 모니터링)
3. **알림 시스템** (SNS, Telegram, Discord)
4. **대시보드** (실시간 포지션 현황)
5. **백테스트 자동 재실행** (시장 변화 감지)

---

## 🆘 지원

- **백테스팅 가이드**: `DEPLOYMENT_GUIDE.md`
- **DynamoDB 스키마**: `infrastructure/dynamodb_schema.md`
- **빠른 시작**: `QUICK_START.md`
