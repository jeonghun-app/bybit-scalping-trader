# DynamoDB 테이블 설계

## 테이블 1: BacktestResults

### 기본 정보
- **테이블명**: `crypto-backtest-results`
- **파티션 키**: `symbol` (String) - 예: "BTCUSDT"
- **정렬 키**: `scan_timestamp` (Number) - Unix timestamp
- **TTL 속성**: `ttl` (Number) - 자동 삭제용

### 속성 (Attributes)

```json
{
  "symbol": "BTCUSDT",                    // PK: 심볼
  "scan_timestamp": 1702800000,           // SK: 스캔 시간 (Unix timestamp)
  "ttl": 1702886400,                      // TTL: 24시간 후 자동 삭제
  
  // 코인 기본 정보
  "volatility_24h": 5.23,                 // 24시간 변동성
  "turnover": 6858457877.50,              // 거래량
  "price": 86623.60,                      // 현재 가격
  "price_change_24h": 0.91,               // 24시간 가격 변화율
  
  // 타임프레임별 분석 결과
  "timeframes": {
    "1m": {
      "total_trades": 234,
      "win_rate": 56.4,
      "total_pnl": 679.20,
      "avg_win": 18.40,
      "avg_loss": -11.20,
      "confidence_avg": 82.5,
      "best_strategy": "ADVANCED",
      "analysis_time": 15.3,              // 분석 소요 시간 (초)
      "status": "completed"               // completed, failed, pending
    },
    "3m": {
      "total_trades": 98,
      "win_rate": 42.1,
      "total_pnl": -123.40,
      "avg_win": 16.20,
      "avg_loss": -10.80,
      "confidence_avg": 78.2,
      "best_strategy": "BASIC",
      "analysis_time": 8.7,
      "status": "completed"
    },
    "5m": { /* ... */ },
    "15m": { /* ... */ },
    "30m": { /* ... */ }
  },
  
  // 최적 타임프레임
  "optimal_timeframe": "1m",              // 가장 수익 높은 타임프레임
  "optimal_pnl": 679.20,                  // 최적 타임프레임 수익
  "optimal_win_rate": 56.4,               // 최적 타임프레임 승률
  
  // 추세 분석
  "btc_correlation": 0.85,                // BTC 상관관계
  "trend_analysis": {
    "current_trend": "UPTREND",
    "strength": 75.3,
    "btc_trend": "SIDEWAYS"
  },
  
  // 메타데이터
  "scan_id": "scan-20251217-120000",      // 스캔 배치 ID
  "analyzer_id": "analyzer-3",            // 분석한 컨테이너 ID
  "created_at": "2025-12-17T12:00:00Z",   // ISO 8601
  "updated_at": "2025-12-17T12:15:23Z",
  "version": 1                             // 스키마 버전
}
```

### 인덱스 (GSI)

#### GSI-1: ScanIdIndex
- **파티션 키**: `scan_id` (String)
- **정렬 키**: `optimal_pnl` (Number)
- **용도**: 특정 스캔의 모든 결과 조회, 수익 순 정렬

#### GSI-2: OptimalTimeframeIndex
- **파티션 키**: `optimal_timeframe` (String)
- **정렬 키**: `optimal_pnl` (Number)
- **용도**: 타임프레임별 최고 성과 코인 조회

#### GSI-3: StatusIndex
- **파티션 키**: `status` (String) - "active", "inactive"
- **정렬 키**: `scan_timestamp` (Number)
- **용도**: 활성/비활성 코인 필터링

### TTL 설정
- **속성**: `ttl`
- **설명**: 24시간 후 자동 삭제 (scan_timestamp + 86400)
- **목적**: 오래된 분석 결과 자동 정리

---

## 테이블 2: TradingPositions (실시간 진입 신호)

### 기본 정보
- **테이블명**: `crypto-trading-positions`
- **파티션 키**: `symbol` (String) - 예: "BTCUSDT"
- **정렬 키**: `signal_timestamp` (Number) - Unix timestamp
- **TTL 속성**: `ttl` (Number) - 5분 후 자동 삭제

### 속성 (Attributes)

```json
{
  "symbol": "BTCUSDT",                    // PK: 심볼
  "signal_timestamp": 1702800000,         // SK: 신호 생성 시간
  "ttl": 1702800300,                      // TTL: 5분 후 삭제
  
  // 전략 정보
  "strategy": "ADVANCED",                 // 사용된 전략
  "timeframe": "1m",                      // 타임프레임
  "confidence": 85.5,                     // 신뢰도
  
  // 포지션 정보
  "position_type": "LONG",                // LONG or SHORT
  "entry_price": 86623.60,                // 진입 가격
  "stop_loss": 85757.96,                  // 손절가 (-1%)
  "take_profit": 88356.07,                // 익절가 (+2%)
  "position_size": 100.0,                 // 포지션 크기 ($)
  "leverage": 10,                         // 레버리지
  
  // 기술적 지표
  "rsi": 42.5,                            // RSI
  "bb_position": 0.25,                    // 볼린저 밴드 위치 (0-1)
  "bb_width": 2.3,                        // 볼린저 밴드 폭
  
  // 추세 정보
  "btc_trend": "UPTREND",                 // BTC 추세
  "btc_change": 0.91,                     // BTC 변화율
  "coin_trend": "UPTREND",                // 코인 추세
  "coin_change": 1.52,                    // 코인 변화율
  
  // 펀딩비
  "funding_rate": 0.0001,                 // 펀딩비
  "funding_sentiment": "NEUTRAL",         // 펀딩비 감정
  
  // 피보나치 레벨
  "fib_support": 85000.00,                // 가장 가까운 지지선
  "fib_resistance": 88000.00,             // 가장 가까운 저항선
  "fib_distance": 2.5,                    // 피보나치 레벨까지 거리 (%)
  
  // 예상 손익
  "expected_profit": 18.40,               // 예상 수익 ($)
  "expected_loss": -11.20,                // 예상 손실 ($)
  "risk_reward_ratio": 1.64,              // 손익비
  
  // 메타데이터
  "signal_id": "signal-20251217-120000-BTCUSDT",
  "scan_id": "scan-20251217-120000",      // 백테스트 스캔 ID
  "created_at": "2025-12-17T12:00:00Z",
  "updated_at": "2025-12-17T12:00:05Z",
  "status": "active",                     // active, executing, executed, expired, failed
  "version": 1,
  
  // 주문 정보 (executing 상태일 때 추가)
  "order_id": "1234567890",               // Bybit Order ID
  "executed_at": "2025-12-17T12:00:05Z",  // 주문 실행 시간
  "executed_price": 86620.50              // 실제 체결가
}
```

### 인덱스 (GSI)

#### GSI-1: StatusIndex
- **파티션 키**: `status` (String)
- **정렬 키**: `signal_timestamp` (Number)
- **용도**: 활성 신호 조회

#### GSI-2: ConfidenceIndex
- **파티션 키**: `status` (String)
- **정렬 키**: `confidence` (Number)
- **용도**: 신뢰도 높은 신호 조회

### TTL 설정
- **속성**: `ttl`
- **설명**: 5분 후 자동 삭제 (signal_timestamp + 300)
- **목적**: 오래된 신호 자동 정리

---

## 테이블 3: ScanHistory

### 기본 정보
- **테이블명**: `crypto-scan-history`
- **파티션 키**: `scan_id` (String)
- **정렬 키**: 없음

### 속성

```json
{
  "scan_id": "scan-20251217-120000",      // PK: 스캔 배치 ID
  "scan_timestamp": 1702800000,           // 스캔 시작 시간
  "ttl": 1703404800,                      // TTL: 7일 후 삭제
  
  // 스캔 결과
  "total_coins_scanned": 552,             // 전체 스캔된 코인 수
  "selected_coins": [                     // 선택된 30개 코인
    "BTCUSDT",
    "ETHUSDT",
    // ... 28개 더
  ],
  "removed_coins": [                      // 이전 스캔에서 제외된 코인
    "OLDCOINUSDT",
    "DEADCOINUSDT"
  ],
  
  // 분석 상태
  "analysis_status": {
    "total": 30,                          // 총 분석 대상
    "completed": 28,                      // 완료
    "failed": 2,                          // 실패
    "pending": 0                          // 대기 중
  },
  
  // 성능 메트릭
  "performance": {
    "scan_duration": 5.2,                 // 스캔 소요 시간 (초)
    "total_analysis_time": 450.3,         // 전체 분석 시간 (초)
    "avg_analysis_time": 15.01,           // 평균 분석 시간 (초)
    "messages_published": 150             // RabbitMQ 메시지 수 (30코인 × 5타임프레임)
  },
  
  // 메타데이터
  "scanner_id": "scanner-1",
  "created_at": "2025-12-17T12:00:00Z",
  "completed_at": "2025-12-17T12:15:23Z",
  "status": "completed"                   // running, completed, failed
}
```

---

## 테이블 3: ActiveCoins (선택적)

### 기본 정보
- **테이블명**: `crypto-active-coins`
- **파티션 키**: `symbol` (String)
- **정렬 키**: 없음

### 속성

```json
{
  "symbol": "BTCUSDT",                    // PK: 심볼
  "is_active": true,                      // 현재 활성 상태
  "last_scan_id": "scan-20251217-120000", // 마지막 스캔 ID
  "last_updated": 1702800000,             // 마지막 업데이트 시간
  "consecutive_scans": 5,                 // 연속 선택 횟수
  "ttl": 1702803600                       // TTL: 1시간 후 삭제 (자동 비활성화)
}
```

**용도**: 
- 빠른 활성 코인 조회
- TTL로 자동 비활성화 (1시간 동안 스캔 안 되면 자동 삭제)

---

## 쿼리 패턴

### 1. 특정 코인의 최신 분석 결과 조회
```python
response = table.query(
    KeyConditionExpression=Key('symbol').eq('BTCUSDT'),
    ScanIndexForward=False,  # 최신순
    Limit=1
)
```

### 2. 특정 스캔의 모든 결과 조회 (수익 순)
```python
response = table.query(
    IndexName='ScanIdIndex',
    KeyConditionExpression=Key('scan_id').eq('scan-20251217-120000'),
    ScanIndexForward=False  # 수익 높은 순
)
```

### 3. 특정 타임프레임에서 최고 성과 코인 조회
```python
response = table.query(
    IndexName='OptimalTimeframeIndex',
    KeyConditionExpression=Key('optimal_timeframe').eq('1m'),
    ScanIndexForward=False,  # 수익 높은 순
    Limit=10
)
```

### 4. 활성 코인 목록 조회
```python
response = table.query(
    IndexName='StatusIndex',
    KeyConditionExpression=Key('status').eq('active')
)
```

### 5. 이전 스캔에서 제외된 코인 삭제
```python
# 1. 현재 스캔의 코인 목록 가져오기
current_coins = set(['BTCUSDT', 'ETHUSDT', ...])

# 2. 이전 활성 코인 조회
previous_active = table.query(
    IndexName='StatusIndex',
    KeyConditionExpression=Key('status').eq('active')
)

# 3. 제외된 코인 찾기
removed_coins = set(previous_active) - current_coins

# 4. 제외된 코인 삭제 (또는 status='inactive'로 변경)
for coin in removed_coins:
    table.delete_item(Key={'symbol': coin, 'scan_timestamp': ...})
```

---

## CloudFormation / Terraform 예시

### DynamoDB 테이블 생성 (CloudFormation)

```yaml
Resources:
  BacktestResultsTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: crypto-backtest-results
      BillingMode: PAY_PER_REQUEST  # On-demand
      AttributeDefinitions:
        - AttributeName: symbol
          AttributeType: S
        - AttributeName: scan_timestamp
          AttributeType: N
        - AttributeName: scan_id
          AttributeType: S
        - AttributeName: optimal_pnl
          AttributeType: N
        - AttributeName: optimal_timeframe
          AttributeType: S
        - AttributeName: status
          AttributeType: S
      KeySchema:
        - AttributeName: symbol
          KeyType: HASH
        - AttributeName: scan_timestamp
          KeyType: RANGE
      GlobalSecondaryIndexes:
        - IndexName: ScanIdIndex
          KeySchema:
            - AttributeName: scan_id
              KeyType: HASH
            - AttributeName: optimal_pnl
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
        - IndexName: OptimalTimeframeIndex
          KeySchema:
            - AttributeName: optimal_timeframe
              KeyType: HASH
            - AttributeName: optimal_pnl
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
        - IndexName: StatusIndex
          KeySchema:
            - AttributeName: status
              KeyType: HASH
            - AttributeName: scan_timestamp
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
      TimeToLiveSpecification:
        AttributeName: ttl
        Enabled: true
      Tags:
        - Key: Environment
          Value: production
        - Key: Service
          Value: crypto-backtest
```

---

## 비용 최적화

### 1. TTL 활용
- 24시간 후 자동 삭제 → 스토리지 비용 절감
- 오래된 데이터 자동 정리

### 2. On-Demand vs Provisioned
- **개발/테스트**: On-Demand (예측 불가능한 트래픽)
- **프로덕션**: Provisioned (1시간마다 예측 가능)
  - Read: 10 RCU (30개 코인 × 5 타임프레임 조회)
  - Write: 20 WCU (30개 코인 × 5 타임프레임 저장)

### 3. 인덱스 최적화
- 필요한 인덱스만 생성
- Projection Type: KEYS_ONLY 또는 INCLUDE (ALL 대신)

---

## 데이터 보존 정책

| 데이터 타입 | 보존 기간 | 방법 |
|------------|----------|------|
| 백테스트 결과 | 24시간 | TTL |
| 스캔 히스토리 | 7일 | TTL |
| 활성 코인 | 1시간 | TTL |
| 통계/집계 | 영구 | S3 Export |

---

## 모니터링

### CloudWatch 메트릭
- `ConsumedReadCapacityUnits`
- `ConsumedWriteCapacityUnits`
- `UserErrors` (조건 실패)
- `SystemErrors` (서비스 오류)
- `ThrottledRequests` (제한)

### 알람 설정
- Write 실패율 > 1%
- Read 지연 > 100ms
- TTL 삭제 지연
