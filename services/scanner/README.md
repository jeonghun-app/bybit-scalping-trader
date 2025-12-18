# Scanner Service - 실시간 스캘핑 레이더

24/7 실행되는 WebSocket 기반 실시간 기회 탐지 시스템

## 🎯 주요 기능

- **실시간 시장 스캔**: 300+ 코인을 tickers.* 하나로 스캔
- **스마트 필터링**: 거래량, 변동성 기준 Top 50 선정
- **정밀 분석**: 선정된 코인만 bookticker + candle.3 구독
- **기회 탐지**: 볼린저 밴드 슈쿼즈, 호가 불균형, 거래량 스파이크
- **즉시 발행**: RabbitMQ로 opportunity-queue에 신호 전송

## 📦 구조

```
services/scanner/
├── scanner_service.py          # 메인 서비스
├── volatility_ranker.py        # 변동성 랭킹
├── squeeze_detector.py         # BB 슈쿼즈 감지
├── orderbook_analyzer.py       # 호가장 분석
├── signal_emitter.py           # RabbitMQ 발행
├── config/
│   └── settings.py             # 환경 설정
├── utils/
│   └── websocket_client.py     # WebSocket 클라이언트
├── test_scanner_local.py       # 로컬 테스트
├── requirements-scanner.txt    # 의존성
└── Dockerfile
```

## 🚀 로컬 테스트

### 1. 의존성 설치

```bash
cd services/scanner
pip install -r requirements-scanner.txt
```

### 2. 환경 변수 설정

```bash
cp .env.example .env
# .env 파일 편집 (RabbitMQ 설정 등)
```

### 3. RabbitMQ 없이 테스트

```bash
python test_scanner_local.py
```

이 테스트는:
- Bybit WebSocket에 실제 연결
- 실시간 티커 수신 및 필터링
- Top 50 선정 및 구독 관리
- 기회 발견 시 콘솔에 출력 (RabbitMQ 없음)

### 4. 전체 서비스 실행 (RabbitMQ 필요)

```bash
python scanner_service.py
```

## 🔧 주요 설정

### config/settings.py

```python
# 필터 기준
MIN_VOLUME_24H = 1_000_000      # 최소 거래량 (USD)
MIN_VOLATILITY_PCT = 2.0        # 최소 변동성 (%)
ACTIVE_SYMBOLS_LIMIT = 50       # 동시 감시 코인 수

# 기회 탐지 임계값
BB_SQUEEZE_THRESHOLD = 0.9      # BB 슈쿼즈 점수
OB_IMBALANCE_THRESHOLD = 0.7    # 호가 불균형
VOLUME_SPIKE_MULTIPLIER = 3.0   # 거래량 스파이크
```

## 📊 출력 데이터 예시

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

## 🐳 Docker 빌드

```bash
docker build -t scanner-service -f services/scanner/Dockerfile .
```

## 📈 모니터링

서비스 실행 중 60초마다 통계 출력:
- 수신 티커 수
- 발행 기회 수
- 활성 심볼 수
- RabbitMQ 큐 크기

## ⚠️ 주의사항

1. **WebSocket 연결**: 하나의 ECS Task = 하나의 연결
2. **구독 제한**: 최대 48개 args per request
3. **재연결**: 연결 끊김 시 자동 재연결 (5초 대기)
4. **메모리**: Top 50 + 히스토리 데이터 관리

## 🔄 다음 단계

Scanner가 발행한 기회 신호는:
1. RabbitMQ `opportunity-queue`에 저장
2. Finder Service가 수신
3. 진입 타이밍 정밀 분석
4. Entry Signal 발행
