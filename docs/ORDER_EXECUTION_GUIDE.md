# 🎯 주문 실행 시스템 가이드

## 📊 전체 흐름

```
1. Position Finder → DynamoDB (status: active)
   ↓
2. Order Executor (5초마다 스캔)
   ↓ 진입 조건 확인
   ↓ - 가격 범위: 진입가 ±0.2%
   ↓ - 신뢰도: 75점 이상
   ↓ - 스프레드: 0.1% 이내
   ↓ - 잔고: $100 이상
   ↓
3. Bybit 주문 실행
   ↓ - 포지션 크기: $100 고정
   ↓ - 레버리지: 10x
   ↓ - TP/SL 자동 설정
   ↓
4. DynamoDB 업데이트 (status: executing)
```

---

## 🔍 진입 조건 (제안)

### 1. 가격 조건
**롱 포지션:**
- 현재가 ≤ 진입가 × 1.002 (0.2% 이내)
- 예: 진입가 $86,623 → 현재가 $86,796 이하

**숏 포지션:**
- 현재가 ≥ 진입가 × 0.998 (0.2% 이내)
- 예: 진입가 $86,623 → 현재가 $86,450 이상

### 2. 신뢰도 조건
- 최소 신뢰도: 75점 이상
- 백테스트에서 검증된 고신뢰도 신호만 실행

### 3. 스프레드 조건
- 매수/매도 스프레드: 0.1% 이내
- 예: Bid $86,600, Ask $86,700 → 스프레드 0.12% (거부)

### 4. 거래량 조건
- 24시간 거래량: 최소 1,000 이상
- 유동성 확보

### 5. 잔고 조건
- 사용 가능 잔고: $100 이상
- 부족 시 대기

---

## 💰 주문 수량 계산

### 공식
```
수량 = (포지션 크기 × 레버리지) / 진입가
```

### 예시 1: BTCUSDT
```
포지션 크기: $100
레버리지: 10x
진입가: $86,623

수량 = ($100 × 10) / $86,623 = 0.0115 BTC

qty_step = 0.001 (Bybit 규칙)
최종 수량 = 0.011 BTC (반올림)
```

### 예시 2: ETHUSDT
```
포지션 크기: $100
레버리지: 10x
진입가: $2,932

수량 = ($100 × 10) / $2,932 = 0.341 ETH

qty_step = 0.01 (Bybit 규칙)
최종 수량 = 0.34 ETH (반올림)
```

### 주의사항
- Bybit의 `lotSizeFilter` 확인 필수
- `minOrderQty`, `maxOrderQty`, `qtyStep` 준수
- 소수점 자릿수 정확히 맞춰야 함

---

## 🔄 포지션 상태 관리

### 상태 전환
```
active → executing → executed
   ↓         ↓          ↓
expired   failed    closed
```

### 상태 설명
- **active**: 진입 대기 중 (Position Finder가 생성)
- **executing**: 주문 실행 중 (Order Executor가 주문 실행)
- **executed**: 주문 완료 (체결 확인)
- **expired**: 만료됨 (TTL 5분)
- **failed**: 실패 (주문 오류)
- **closed**: 청산 완료 (TP/SL 도달)

### Position Finder 로직
```python
# 기존 포지션 확인
existing_status, existing_position = check_existing_position(symbol)

if existing_status == 'executing':
    # 이미 진입 중 → 스킵
    return False

if existing_status == 'active':
    # 기존 포지션과 비교
    if positions_are_similar(new, existing):
        # 유사함 → 업데이트 스킵
        return False
    else:
        # 다름 → 업데이트 진행
        update_position(new)
```

### 유사성 판단 기준
- 진입가 차이: 0.5% 이내
- 포지션 타입: 동일
- 신뢰도 차이: 5점 이내

---

## 🚀 배포

### Step 1: ECR 리포지토리 생성
```bash
aws ecr create-repository \
  --repository-name crypto-backtest-executor \
  --region ap-northeast-2
```

### Step 2: Docker 이미지 빌드 및 푸시
```bash
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=ap-northeast-2

# 이미지 빌드
docker build -f Dockerfile.executor -t crypto-backtest-executor:latest .

# 태그 및 푸시
docker tag crypto-backtest-executor:latest \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/crypto-backtest-executor:latest

docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/crypto-backtest-executor:latest
```

### Step 3: ECS Service 생성
```bash
# Task Definition 등록
aws ecs register-task-definition \
  --cli-input-json file://infrastructure/ecs-executor-task.json

# Service 생성
aws ecs create-service \
  --cluster crypto-backtest-cluster \
  --service-name crypto-backtest-executor \
  --task-definition crypto-backtest-executor \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"
```

---

## 🔍 모니터링

### 1. 로그 확인
```bash
aws logs tail /ecs/crypto-backtest-executor --follow --region ap-northeast-2
```

**예상 출력:**
```
🔄 Order Executor 스캔 시작
✅ 3개 활성 포지션 발견

🔍 포지션 확인: BTCUSDT
  - 진입가: $86623.60
  - 타입: LONG
  - 신뢰도: 85점
  - 상태: active
  - 현재가: $86620.50
✅ 진입 조건 충족: 진입 조건 충족
  - 계정 잔고: $1,234.56

📤 주문 실행: BTCUSDT (LONG)
[1/3] 레버리지 설정 (10x)... ✅ 레버리지 설정 완료
[2/3] 주문 수량 계산...
📊 수량 계산:
  - 포지션 크기: $100.0
  - 레버리지: 10x
  - 진입가: $86623.60
  - 계산된 수량: 0.011
  - 최소/최대: 0.001 / 100.0
  - 수량 단위: 0.001
[3/3] 주문 실행...

✅ 주문 실행 성공!
  - Order ID: 1234567890
  - 심볼: BTCUSDT
  - 타입: LONG
  - 수량: 0.011
  - 진입가: $86620.50 (예상)
  - 손절가: $85757.96
  - 익절가: $88356.07
  - 포지션 크기: $100.0
  - 레버리지: 10x

✅ DynamoDB 상태 업데이트: BTCUSDT → executing
✅ 처리 완료: BTCUSDT
```

### 2. DynamoDB 확인
```bash
# executing 상태 포지션 조회
aws dynamodb query \
  --table-name crypto-backtest-trading-positions \
  --index-name StatusIndex \
  --key-condition-expression "#status = :status" \
  --expression-attribute-names '{"#status":"status"}' \
  --expression-attribute-values '{":status":{"S":"executing"}}' \
  --region ap-northeast-2
```

### 3. Bybit 포지션 확인
```bash
# API로 확인
curl -X GET "https://api.bybit.com/v5/position/list?category=linear" \
  -H "X-BAPI-API-KEY: YOUR_KEY" \
  -H "X-BAPI-TIMESTAMP: $(date +%s)000" \
  -H "X-BAPI-SIGN: YOUR_SIGNATURE"
```

---

## ⚙️ 설정 조정

### 환경 변수
```bash
# 포지션 크기 (기본: $100)
POSITION_SIZE=100.0

# 레버리지 (기본: 10x)
LEVERAGE=10

# 스캔 주기 (기본: 5초)
SCAN_INTERVAL=5

# 최소 신뢰도 (기본: 75점)
MIN_CONFIDENCE=75

# 가격 허용 범위 (기본: 0.2%)
PRICE_TOLERANCE=0.002
```

### 진입 조건 완화
```python
# order_executor_service.py
self.entry_conditions = {
    'price_tolerance': 0.005,  # 0.2% → 0.5%
    'min_confidence': 70,      # 75점 → 70점
    'check_volume': False,     # 거래량 확인 비활성화
    'check_spread': False      # 스프레드 확인 비활성화
}
```

---

## 🔧 트러블슈팅

### 문제 1: 주문이 실행되지 않음
```bash
# 로그 확인
aws logs tail /ecs/crypto-backtest-executor --follow --region ap-northeast-2

# 가능한 원인:
# 1. 잔고 부족 → 입금 필요
# 2. 가격 범위 초과 → PRICE_TOLERANCE 조정
# 3. 신뢰도 부족 → MIN_CONFIDENCE 낮추기
# 4. 스프레드 과다 → check_spread=False
```

### 문제 2: 수량 계산 오류
```bash
# 심볼 정보 확인
curl "https://api.bybit.com/v5/market/instruments-info?category=linear&symbol=BTCUSDT"

# lotSizeFilter 확인:
# - minOrderQty: 최소 주문 수량
# - maxOrderQty: 최대 주문 수량
# - qtyStep: 수량 단위
```

### 문제 3: 레버리지 설정 실패
```bash
# 이미 설정되어 있을 수 있음 (정상)
# 또는 Bybit 계정 설정 확인:
# - 격리 마진 vs 교차 마진
# - 최대 레버리지 제한
```

### 문제 4: 중복 주문
```bash
# Position Finder 로직 확인
# - executing 상태 체크
# - 유사성 판단 기준 조정
```

---

## 💡 최적화 팁

### 1. 진입 타이밍 개선
```python
# 롱: 현재가가 진입가보다 약간 낮을 때
if position_type == 'LONG':
    if current_price <= entry_price * 0.999:  # 0.1% 낮을 때
        # 더 좋은 가격에 진입
```

### 2. 동적 포지션 크기
```python
# 신뢰도에 따라 포지션 크기 조정
if confidence >= 90:
    position_size = 150.0  # $150
elif confidence >= 80:
    position_size = 100.0  # $100
else:
    position_size = 50.0   # $50
```

### 3. 리스크 관리
```python
# 일일 최대 손실 한도
daily_loss_limit = 500.0  # $500

# 동시 포지션 수 제한
max_positions = 5

# 코인당 최대 포지션
max_per_symbol = 1
```

---

## 📊 성능 메트릭

### 예상 처리량
- **스캔 주기**: 5초
- **포지션 처리**: 초당 2-3개
- **주문 실행**: 평균 1-2초

### 지연 시간
- 신호 생성 → 주문 실행: 5-15초
- 총 지연: 1-2분 (실시간에 가까움)

---

## ⚠️ 주의사항

### 1. 실전 거래 리스크
- 백테스트 ≠ 실전 성과
- 슬리피지, 체결 지연 발생 가능
- 시장 급변 시 손실 확대 가능

### 2. 자금 관리
- 총 자본의 1-2%만 사용
- 레버리지 신중히 사용
- 손절 반드시 설정

### 3. 모니터링 필수
- 실시간 로그 확인
- 포지션 현황 모니터링
- 알람 설정 (SNS, Telegram)

---

## 📚 다음 단계

1. **포지션 모니터링 시스템** (TP/SL 도달 확인)
2. **알림 시스템** (진입/청산 알림)
3. **대시보드** (실시간 현황)
4. **자동 재조정** (손절/익절 동적 조정)
5. **성과 분석** (실전 vs 백테스트 비교)
