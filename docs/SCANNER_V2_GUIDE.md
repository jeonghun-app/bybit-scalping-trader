# Scanner Service V2 - 실시간 스캘핑 레이더 가이드

## 📋 개요

Scanner Service가 2차 고도화되어 **실시간 스캘핑 레이더**로 전환되었습니다.

### 주요 변경사항

| 항목 | 기존 (V1) | 변경 후 (V2) |
|------|-----------|--------------|
| 실행 방식 | EventBridge → 1시간마다 | ECS Service 24/7 상시 실행 |
| 데이터 소스 | REST API (tickers 조회) | WebSocket 실시간 스트림 |
| 구독 방식 | - | tickers.*, bookticker.*, candle.3.* |
| 출력 | 단순 후보 코인 | 진입 기회 + 신뢰도 점수 + 행동 유형 |
| 결과 전달 | DynamoDB + RabbitMQ | RabbitMQ opportunity-queue 즉시 발행 |
| 필터 기준 | 거래량, 변동성 | BB 슈쿼즈, 호가 불균형, 거래량 스파이크 |

---

## 🎯 핵심 기능

### 1. 3단계 점진적 구독 전략

```
┌─────────────────────┐
│  1. Broad Scanner   │  ← tickers.* (단일 구독)
│  전체 시장 요약 수신 │     300+ 코인 동시 모니터링
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  2. Active Watchlist│  ← Top 50 종목 선정
│  bookticker +       │     실시간 호가 + 3초봉
│  candle.3 구독      │
└──────────┬──────────┘
           │ (기회 발견 시)
           ▼
┌─────────────────────┐
│  3. Opportunity     │  ← RabbitMQ 발행
│  Signal Emission    │     Finder로 전달
└─────────────────────┘
```

### 2. 기회 탐지 알고리즘

#### A. 볼린저 밴드 슈쿼즈 (BB Squeeze)
- 20봉 이동평균 ± 2σ
- 밴드 폭이 최대 대비 20% 이하로 좁아짐
- 이후 확장 시작 → 큰 움직임 예상

#### B. 호가장 불균형 (Orderbook Imbalance)
- 최우선 매수/매도 호가 잔량 비교
- 불균형 지수 = (bid_qty - ask_qty) / (bid_qty + ask_qty)
- 0.7 이상 → 매수 우위 (상승 가능성)
- -0.7 이하 → 매도 우위 (하락 가능성)

#### C. 거래량 스파이크 (Volume Spike)
- 최근 100개 거래량 평균 대비 현재 거래량
- 3배 이상 → 급격한 관심 증가

### 3. 출력 데이터 구조

```json
{
  "event_id": "opp-20251218-154521-001",
  "symbol": "TAOUSDT",
  "opportunity_type": "bb_squeeze_release",
  "volatility_rank": 3,
  "bb_squeeze_score": 0.94,
  "ob_imbalance": 0.78,
  "volume_spike_x": 3.4,
  "price": 7.52,
  "timestamp": "2025-12-18T15:45:21Z",
  "trigger_action": "activate_finder"
}
```

**필드 설명**:
- `opportunity_type`: bb_squeeze_release, ob_breakout, volume_spark, mixed_signal
- `volatility_rank`: 전체 코인 대비 변동성 순위 (1~300)
- `bb_squeeze_score`: 볼린저 밴드 좁아진 정도 (0~1, 0.9+ 주목)
- `ob_imbalance`: 호가 불균형 지수 (-1~1, ±0.7+ 주목)
- `volume_spike_x`: 평균 거래량 대비 배수
- `trigger_action`: 다음 단계 행동 명령 (activate_finder)

---

## 🚀 로컬 테스트

### 1. 환경 준비

```bash
cd services/scanner

# 의존성 설치
pip install -r requirements-scanner.txt
```

### 2. 환경 변수 설정

```bash
# .env 파일 생성
cp .env.example .env

# 필수 설정 (RabbitMQ 없이 테스트 가능)
BYBIT_WS_URL=wss://stream.bybit.com/v5/public/linear
LOG_LEVEL=INFO
```

### 3. RabbitMQ 없이 테스트

```bash
# 테스트 스크립트 실행
python test_scanner_local.py

# 또는 실행 스크립트 사용
chmod +x run_local_test.sh
./run_local_test.sh
```

**테스트 출력 예시**:
```
================================
🧪 Scanner 로컬 테스트 시작
================================

✅ WebSocket 연결 성공: wss://stream.bybit.com/v5/public/linear
📡 구독 요청: 1개 토픽
🎧 메시지 수신 시작...

📈 새 구독: 50개
🔝 Top 10: BTCUSDT, ETHUSDT, SOLUSDT, TAOUSDT, ...

============================================================
✨ 기회 발견!
  Symbol: TAOUSDT
  Price: $7.5200
  Rank: #3
  BB Squeeze: 0.940
  OB Imbalance: +0.780
  Volume Spike: 3.40x
============================================================

📊 테스트 통계
  • 수신 티커: 1523
  • 발견 기회: 5
  • 활성 심볼: 50
  • 전체 심볼: 287
============================================================
```

### 4. 전체 서비스 실행 (RabbitMQ 필요)

```bash
# .env에 RabbitMQ 설정 추가
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=admin
RABBITMQ_PASS=your_password
RABBITMQ_USE_SSL=false

# 서비스 실행
python scanner_service.py
```

---

## 🐳 Docker 빌드 및 배포

### 1. 로컬 Docker 빌드

```bash
# 프로젝트 루트에서
docker build -t scanner-service:latest -f services/scanner/Dockerfile .

# 실행
docker run --env-file .env scanner-service:latest
```

### 2. ECR 푸시

```bash
# ECR 로그인
aws ecr get-login-password --region ap-northeast-2 | \
  docker login --username AWS --password-stdin \
  081041735764.dkr.ecr.ap-northeast-2.amazonaws.com

# 태그
docker tag scanner-service:latest \
  081041735764.dkr.ecr.ap-northeast-2.amazonaws.com/scanner-service:latest

# 푸시
docker push 081041735764.dkr.ecr.ap-northeast-2.amazonaws.com/scanner-service:latest
```

### 3. ECS 서비스 업데이트

```bash
# 새 태스크 정의 등록
aws ecs register-task-definition --cli-input-json file://task-definition.json

# 서비스 업데이트
aws ecs update-service \
  --cluster crypto-backtest-cluster \
  --service scanner-service \
  --force-new-deployment
```

---

## ⚙️ 설정 가이드

### config/settings.py

```python
class Config:
    # WebSocket
    BYBIT_WS_URL = "wss://stream.bybit.com/v5/public/linear"
    
    # 스캔 제어
    ACTIVE_SYMBOLS_LIMIT = 50  # 동시 감시 코인 수
    TICKER_UPDATE_INTERVAL = 5  # Top N 갱신 주기 (초)
    
    # 필터 기준
    MIN_VOLUME_24H = 1_000_000  # 최소 거래량 (USD)
    MIN_VOLATILITY_PCT = 2.0    # 최소 변동성 (%)
    
    # 기회 탐지 임계값
    BB_SQUEEZE_THRESHOLD = 0.9      # BB 슈쿼즈 점수
    OB_IMBALANCE_THRESHOLD = 0.7    # 호가 불균형
    VOLUME_SPIKE_MULTIPLIER = 3.0   # 거래량 스파이크
    
    # 볼린저 밴드
    BB_WINDOW = 20      # 이동평균 기간
    BB_STD_DEV = 2.0    # 표준편차 배수
    
    # RabbitMQ
    RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
    RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
    RABBITMQ_QUEUE = "opportunity-queue"
```

### 임계값 조정 가이드

**더 많은 기회를 원할 때**:
```python
BB_SQUEEZE_THRESHOLD = 0.8      # 0.9 → 0.8
OB_IMBALANCE_THRESHOLD = 0.6    # 0.7 → 0.6
VOLUME_SPIKE_MULTIPLIER = 2.5   # 3.0 → 2.5
```

**더 정밀한 기회를 원할 때**:
```python
BB_SQUEEZE_THRESHOLD = 0.95     # 0.9 → 0.95
OB_IMBALANCE_THRESHOLD = 0.8    # 0.7 → 0.8
VOLUME_SPIKE_MULTIPLIER = 4.0   # 3.0 → 4.0
```

---

## 📊 모니터링

### CloudWatch Logs

```bash
# 실시간 로그 확인
aws logs tail /ecs/crypto-trading/scanner-service --follow

# 특정 키워드 검색
aws logs filter-log-events \
  --log-group-name /ecs/crypto-trading/scanner-service \
  --filter-pattern "기회 발견"
```

### 주요 메트릭

1. **수신 티커 수**: 분당 수신하는 티커 메시지 수
2. **발행 기회 수**: 시간당 발행하는 기회 신호 수
3. **활성 심볼 수**: 현재 감시 중인 코인 수 (최대 50)
4. **WebSocket 연결 상태**: 연결/재연결 이벤트

### RabbitMQ 모니터링

```bash
# Web Console 접속
https://{broker-host}:443

# opportunity-queue 확인
- 큐 길이 (Ready)
- 메시지 처리 속도 (Publish/Deliver rate)
- 소비자 수 (Consumers)
```

---

## 🔧 트러블슈팅

### 1. WebSocket 연결 실패

**증상**: `WebSocket 연결 실패: [SSL: CERTIFICATE_VERIFY_FAILED]`

**해결**:
```python
# utils/websocket_client.py
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE
```

### 2. 구독 실패 (args too long)

**증상**: `구독 실패: args length exceeds limit`

**원인**: Bybit는 최대 48개 args 권장

**해결**: 이미 코드에 반영됨 (48개씩 분할 구독)

### 3. 메모리 부족

**증상**: 장시간 실행 시 메모리 증가

**해결**:
```python
# volatility_ranker.py
def cleanup_old_symbols(self, max_age_seconds=300):
    # 5분 이상 업데이트 없는 심볼 제거
```

### 4. RabbitMQ 연결 끊김

**증상**: `RabbitMQ 연결 실패: Connection refused`

**해결**:
- Heartbeat 설정 확인 (600초)
- 재연결 로직 확인 (자동 재연결)
- 네트워크/보안 그룹 확인

---

## 🎓 다음 단계

Scanner가 발행한 기회 신호는:

1. **RabbitMQ** `opportunity-queue`에 저장
2. **Finder Service**가 수신
3. 진입 타이밍 정밀 분석 (200봉 데이터)
4. **Entry Signal** 발행 (DynamoDB)
5. **Executor Service**가 실제 주문 실행

### Finder Service 수정 필요

Finder가 `opportunity-queue`를 소비하도록 수정:

```python
# services/finder/position_finder_service.py

# 기존: trading-signals 큐 소비
# 추가: opportunity-queue 큐 소비

def consume_opportunities(self):
    channel.basic_consume(
        queue='opportunity-queue',
        on_message_callback=self.handle_opportunity
    )

def handle_opportunity(self, ch, method, properties, body):
    opportunity = json.loads(body)
    symbol = opportunity['symbol']
    
    # 실시간 진입 신호 분석
    signal = self.analyze_entry_signal(symbol)
    
    if signal:
        self.save_to_dynamodb(signal)
```

---

## 📚 참고 자료

- [Bybit WebSocket API 문서](https://bybit-exchange.github.io/docs/v5/ws/connect)
- [볼린저 밴드 전략](https://www.investopedia.com/terms/b/bollingerbands.asp)
- [호가장 분석 기법](https://www.investopedia.com/terms/o/order-book.asp)
- [Scanner Service README](../services/scanner/README.md)

---

**문서 버전**: 2.0  
**최종 업데이트**: 2025-12-18  
**작성자**: Kiro AI Assistant
