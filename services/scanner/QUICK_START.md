# Scanner V2 - 빠른 시작 가이드

## 🚀 5분 안에 로컬 테스트하기

### 1단계: 의존성 설치 (1분)

```bash
cd services/scanner
pip install -r requirements-scanner.txt
```

**필요한 패키지**:
- websockets (WebSocket 클라이언트)
- numpy (수치 계산)
- pandas (데이터 처리)
- pika (RabbitMQ, 테스트 시 불필요)

### 2단계: 테스트 실행 (3분)

```bash
# 방법 1: Python 직접 실행
python test_scanner_local.py

# 방법 2: 실행 스크립트 사용
chmod +x run_local_test.sh
./run_local_test.sh
```

### 3단계: 결과 확인 (1분)

**정상 실행 시 출력**:
```
✅ WebSocket 연결 성공
📡 구독 요청: 1개 토픽
🎧 메시지 수신 시작...

📈 새 구독: 50개
🔝 Top 10: BTCUSDT, ETHUSDT, SOLUSDT, ...

============================================================
✨ 기회 발견!
  Symbol: TAOUSDT
  Price: $7.5200
  Rank: #3
  BB Squeeze: 0.940
  OB Imbalance: +0.780
  Volume Spike: 3.40x
============================================================
```

**Ctrl+C로 종료**

---

## 🎯 무엇을 테스트하는가?

### ✅ 실시간 WebSocket 연결
- Bybit Public WebSocket에 실제 연결
- 300+ 코인의 실시간 티커 수신

### ✅ 스마트 필터링
- 거래량 $1M+ 필터링
- 변동성 2%+ 필터링
- Top 50 자동 선정

### ✅ 기회 탐지
- 볼린저 밴드 슈쿼즈 감지
- 호가장 불균형 분석
- 거래량 스파이크 감지

### ✅ 콘솔 출력
- RabbitMQ 없이 콘솔에 결과 출력
- 실제 운영 시에는 RabbitMQ로 발행

---

## 🔧 설정 변경

### 더 많은 기회를 보고 싶다면

`config/settings.py` 수정:

```python
# 기본값
MIN_VOLUME_24H = 1_000_000
MIN_VOLATILITY_PCT = 2.0
BB_SQUEEZE_THRESHOLD = 0.9

# 더 많은 기회
MIN_VOLUME_24H = 500_000      # 거래량 기준 완화
MIN_VOLATILITY_PCT = 1.5      # 변동성 기준 완화
BB_SQUEEZE_THRESHOLD = 0.8    # 슈쿼즈 기준 완화
```

### 감시 코인 수 변경

```python
ACTIVE_SYMBOLS_LIMIT = 50  # 기본값

# 더 많이 감시 (메모리 증가)
ACTIVE_SYMBOLS_LIMIT = 100

# 적게 감시 (리소스 절약)
ACTIVE_SYMBOLS_LIMIT = 30
```

---

## ❓ 문제 해결

### Q: WebSocket 연결 실패
```
❌ WebSocket 연결 실패: [SSL: CERTIFICATE_VERIFY_FAILED]
```

**해결**: Python SSL 인증서 설치
```bash
# macOS
/Applications/Python\ 3.11/Install\ Certificates.command

# Linux
pip install --upgrade certifi
```

### Q: 기회가 발견되지 않음
```
📊 테스트 통계
  • 발견 기회: 0
```

**원인**: 시장이 조용하거나 기준이 너무 엄격

**해결**: 
1. 더 오래 실행 (5~10분)
2. 임계값 완화 (위 "설정 변경" 참고)

### Q: 메모리 사용량 증가
```
메모리 사용량이 계속 증가합니다
```

**해결**: 이미 코드에 반영됨
- 5분마다 오래된 심볼 자동 정리
- 히스토리 최대 100개로 제한

---

## 📊 예상 결과

### 정상 작동 시

**30초 후**:
- 수신 티커: ~500개
- 활성 심볼: 50개
- Top 10 출력

**5분 후**:
- 수신 티커: ~15,000개
- 발견 기회: 3~10개
- 기회 타입: bb_squeeze_release, ob_breakout, volume_spark

### 시장 상황별 기회 발생 빈도

| 시장 상황 | 기회 발생 빈도 |
|-----------|----------------|
| 조용한 시장 | 시간당 5~10개 |
| 보통 시장 | 시간당 20~30개 |
| 변동성 큰 시장 | 시간당 50~100개 |

---

## 🎓 다음 단계

### 로컬 테스트 성공 후

1. **RabbitMQ 연동 테스트**
   ```bash
   # .env 설정 후
   python scanner_service.py
   ```

2. **Docker 빌드**
   ```bash
   docker build -t scanner-service .
   docker run --env-file .env scanner-service
   ```

3. **AWS 배포**
   ```bash
   ./scripts/build-and-push.sh
   ./scripts/update-services.sh
   ```

---

## 📚 더 알아보기

- [상세 가이드](../../docs/SCANNER_V2_GUIDE.md)
- [시스템 아키텍처](../../docs/SYSTEM_ARCHITECTURE.md)
- [Scanner README](README.md)

---

**테스트 시간**: 5분  
**난이도**: ⭐⭐☆☆☆ (쉬움)  
**필요 사항**: Python 3.11+, 인터넷 연결
