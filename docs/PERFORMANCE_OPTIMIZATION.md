# 백테스팅 성능 최적화 가이드

## 🐌 현재 병목 지점

### 1. 비트코인 추세 분석 (가장 큰 병목!)
```python
# 매 진입 신호마다 비트코인 데이터를 새로 가져옴
btc_trend = self.trend_analyzer.get_btc_trend(self.client, timeframe_minutes=60)
```
**문제**: 1000개 캔들 × 10개 코인 = 10,000번 API 호출!

### 2. 멀티 타임프레임 피보나치
```python
# 5개 타임프레임 × 10개 코인 = 50번 API 호출
mtf_fib = Indicators.calculate_multi_timeframe_fibonacci(...)
```

### 3. 슬라이딩 윈도우
```python
# 매번 전체 데이터프레임 복사
window_df = entry_df.iloc[:i+1].copy()
```

---

## 🚀 최적화 방법

### 1. 비트코인 데이터 캐싱 (가장 중요!)
```python
# ❌ 이전: 매번 API 호출
btc_trend = self.trend_analyzer.get_btc_trend(self.client, 60)

# ✅ 개선: 한 번만 가져와서 재사용
# 백테스팅 시작 시 한 번만 로드
btc_df = self.client.get_klines('BTCUSDT', interval=1, limit=1000)
# 각 시점의 추세를 미리 계산
btc_trends = self._precalculate_btc_trends(btc_df)
```

**예상 효과**: 10,000번 → 1번 (99.99% 감소!)

### 2. 지표 사전 계산
```python
# ❌ 이전: 매 루프마다 계산
for i in range(len(df)):
    window_df = df.iloc[:i+1].copy()
    df = Indicators.calculate_bollinger_bands(window_df, ...)
    df = Indicators.calculate_rsi(window_df, ...)

# ✅ 개선: 한 번만 계산
df = Indicators.calculate_bollinger_bands(df, ...)
df = Indicators.calculate_rsi(df, ...)
for i in range(len(df)):
    latest = df.iloc[i]
    # 이미 계산된 지표 사용
```

**예상 효과**: 1000번 → 1번 (99.9% 감소!)

### 3. 데이터프레임 복사 제거
```python
# ❌ 이전: 매번 복사
window_df = entry_df.iloc[:i+1].copy()

# ✅ 개선: 인덱스만 사용
latest = entry_df.iloc[i]
prev = entry_df.iloc[i-1]
```

**예상 효과**: 메모리 사용량 90% 감소

### 4. 병렬 처리 (선택사항)
```python
from concurrent.futures import ThreadPoolExecutor

# 여러 코인을 동시에 백테스팅
with ThreadPoolExecutor(max_workers=4) as executor:
    futures = [executor.submit(self._backtest_symbol, symbol) 
               for symbol in symbols]
```

**예상 효과**: 4배 속도 향상

---

## 📊 예상 성능 개선

### 현재
- 10개 코인 × 1000개 캔들 = **약 5-10분**
- API 호출: 약 10,050번
- 메모리: 높음

### 최적화 후
- 10개 코인 × 1000개 캔들 = **약 30초-1분**
- API 호출: 약 60번 (99.4% 감소)
- 메모리: 낮음

**속도 향상: 5-10배!**

---

## 🔧 구현 우선순위

### 1단계: 비트코인 캐싱 (필수) ⭐⭐⭐
- 효과: 가장 큼
- 난이도: 쉬움
- 예상 시간: 10분

### 2단계: 지표 사전 계산 (필수) ⭐⭐⭐
- 효과: 큼
- 난이도: 중간
- 예상 시간: 20분

### 3단계: 데이터프레임 최적화 (권장) ⭐⭐
- 효과: 중간
- 난이도: 쉬움
- 예상 시간: 10분

### 4단계: 병렬 처리 (선택) ⭐
- 효과: 중간
- 난이도: 어려움
- 예상 시간: 30분

---

## 💡 추가 최적화 팁

### 1. 캔들 수 줄이기
```python
# 테스트 시: 100-200개
# 최종 검증: 1000개
candles = 200  # 빠른 테스트
```

### 2. 코인 수 줄이기
```python
# 테스트 시: 3-5개
# 최종 검증: 10개
TOP_BACKTEST_COINS = 5  # 빠른 테스트
```

### 3. 타임프레임 줄이기
```python
# 피보나치 타임프레임 줄이기
FIBONACCI_TIMEFRAMES = [15, 60]  # 5개 → 2개
```

### 4. 진행 상황 표시
```python
from tqdm import tqdm

for i in tqdm(range(len(df)), desc="백테스팅"):
    # ...
```
