# Discovery Service

전체 시장 스캔 및 Top N 선정 서비스 (REST API 기반)

## 🎯 역할

- Bybit REST API로 전체 USDT 선물 티커 조회
- 거래량/변동성 기준 필터링
- Top 50 심볼 선정
- RabbitMQ `discovery-results` 큐에 발행

## 🚀 로컬 테스트

### 1. 의존성 설치

```bash
cd services/discovery
pip install -r requirements-discovery.txt
```

### 2. 테스트 실행 (RabbitMQ 불필요)

```bash
python test_discovery_local.py
```

### 3. 예상 출력

```
📊 전체 487개 티커 조회 완료
✅ 필터링 완료: 127개 → Top 50 선정
============================================================
🔝 Top 50 심볼
============================================================
# 1 BTCUSDT      | 변동성:   5.23% | 거래량: $15234.56M | 가격: $ 86500.00
# 2 ETHUSDT      | 변동성:   4.87% | 거래량:  $8765.43M | 가격: $  3250.00
# 3 SOLUSDT      | 변동성:   8.92% | 거래량:  $2345.67M | 가격: $   145.50
...
```

## 🔧 설정

### 필터 기준

```python
min_volume_24h = 1_000_000      # $1M 이상
min_volatility_pct = 2.0        # 2% 이상
top_n = 50                      # Top 50 선정
```

### 실행 주기

```python
interval_seconds = 60  # 1분마다
```

## 📦 출력 데이터

```json
{
  "timestamp": "2025-12-18T15:45:21Z",
  "total_count": 50,
  "symbols": ["BTCUSDT", "ETHUSDT", ...],
  "details": [
    {
      "symbol": "BTCUSDT",
      "price": 86500.0,
      "turnover_24h": 15234560000.0,
      "volume_24h": 176234.5,
      "change_pct": 5.23,
      "funding_rate": 0.0001
    },
    ...
  ]
}
```

## 🐳 Docker 실행

```bash
docker build -t discovery-service -f services/discovery/Dockerfile .
docker run --env-file .env discovery-service
```

## 📊 아키텍처

```
Discovery Service (1분마다)
    ↓ REST API
Bybit API (/v5/market/tickers)
    ↓ 필터링 & 랭킹
Top 50 선정
    ↓ RabbitMQ
discovery-results Queue
    ↓
Scanner Service (구독 업데이트)
```

## ⚙️ 환경 변수

```bash
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=admin
RABBITMQ_PASS=your_password

MIN_VOLUME_24H=1000000
MIN_VOLATILITY_PCT=2.0
TOP_N=50
```

## 📈 성능

- **API 호출**: 1분당 1회
- **응답 시간**: ~500ms
- **데이터 크기**: ~50KB
- **CPU**: 최소
- **메모리**: ~100MB

## 🔄 다음 단계

Discovery가 발행한 결과는:
1. RabbitMQ `discovery-results` 큐에 저장
2. Scanner Service가 수신
3. WebSocket 구독 대상 업데이트
4. 실시간 기회 탐지 시작
