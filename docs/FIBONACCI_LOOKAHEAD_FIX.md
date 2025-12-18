# 피보나치 Look-ahead Bias 수정

## 🚨 문제점 발견

### 현재 방식 (잘못됨)
```python
# 전체 1000개 캔들로 피보나치 계산
df = get_klines(symbol, limit=1000)  # 0번 ~ 999번 캔들
high = df['high'].max()  # 전체 기간의 최고점
low = df['low'].min()    # 전체 기간의 최저점
fib_levels = calculate_fibonacci(high, low)

# 1번째 캔들부터 백테스팅
for i in range(0, 1000):
    if price_near_fib_level(df[i], fib_levels):
        enter_trade()  # ❌ 미래 데이터 사용!
```

**문제**:
- 1번째 캔들 시점에서는 999번째 캔들의 고점/저점을 알 수 없음
- 미래 데이터를 보고 과거에 거래하는 것
- 백테스팅 결과가 실제보다 좋게 나옴 (과최적화)

### 예시
```
시간: 2024-01-01 00:00 (1번째 캔들)
피보나치 계산: 2024-01-01 ~ 2024-01-10 전체 데이터 사용
→ 2024-01-10의 최고점을 이미 알고 있음 ❌

실제 거래:
시간: 2024-01-01 00:00
알 수 있는 데이터: 2024-01-01 00:00까지만
→ 2024-01-10의 최고점을 모름 ✅
```

---

## ✅ 올바른 방식

### 롤링 피보나치 (Rolling Fibonacci)
```python
# 각 시점에서 최근 N개 캔들만 사용
lookback = 100  # 최근 100개 캔들

for i in range(100, 1000):
    # 현재 시점에서 최근 100개만 사용
    window = df[i-100:i]  # 미래 데이터 제외!
    high = window['high'].max()
    low = window['low'].min()
    fib_levels = calculate_fibonacci(high, low)
    
    # 현재 시점의 가격으로 판단
    if price_near_fib_level(df[i], fib_levels):
        enter_trade()  # ✅ 올바른 방식!
```

**장점**:
- 각 시점에서 그 시점까지의 데이터만 사용
- 실제 거래와 동일한 조건
- 정확한 백테스팅 결과

### 예시
```
시간: 2024-01-05 10:00 (500번째 캔들)
피보나치 계산: 최근 100개 (400~499번 캔들)
→ 2024-01-05 10:00 시점에서 알 수 있는 데이터만 사용 ✅

시간: 2024-01-05 11:00 (501번째 캔들)
피보나치 계산: 최근 100개 (401~500번 캔들)
→ 피보나치가 업데이트됨 (실제와 동일) ✅
```

---

## 📊 구현 방법

### 1. 롤링 피보나치 계산
```python
from src.utils.rolling_fibonacci import RollingFibonacci

# 1분봉 데이터
df = get_klines(symbol, limit=1000)

# 롤링 피보나치 계산 (최근 100개 캔들 기준)
fib_df = RollingFibonacci.calculate_rolling_fibonacci(df, lookback_period=100)

# 각 시점의 피보나치 레벨
for i in range(100, 1000):
    fib_data = RollingFibonacci.get_fibonacci_at_index(fib_df, i)
    fib_levels = fib_data['levels']
    
    # 현재 가격으로 판단
    current_price = df.iloc[i]['close']
    is_near, level_name, level_price = RollingFibonacci.is_near_fibonacci_level(
        current_price, fib_levels
    )
```

### 2. 멀티 타임프레임 롤링 피보나치
```python
# 여러 타임프레임의 롤링 피보나치
timeframes = {
    '5m': 100,   # 5분봉 최근 100개 (500분 = 8.3시간)
    '15m': 100,  # 15분봉 최근 100개 (1500분 = 25시간)
    '1h': 100,   # 1시간봉 최근 100개 (100시간 = 4.2일)
}

mtf_fib = RollingFibonacci.calculate_multi_timeframe_rolling_fibonacci(df, timeframes)

# 특정 시점의 멀티 타임프레임 피보나치
for i in range(100, 1000):
    fib_5m = RollingFibonacci.get_fibonacci_at_index(mtf_fib['5m'], i)
    fib_15m = RollingFibonacci.get_fibonacci_at_index(mtf_fib['15m'], i)
    fib_1h = RollingFibonacci.get_fibonacci_at_index(mtf_fib['1h'], i)
```

---

## 🎯 백테스팅 수정

### 이전 방식
```python
# 한 번만 계산 (잘못됨)
mtf_fib = calculate_multi_timeframe_fibonacci(client, symbol, timeframes)

for i in range(len(df)):
    signal = analyze_entry(df[i], mtf_fib)  # ❌ 고정된 피보나치
```

### 새로운 방식
```python
# 롤링 피보나치 사전 계산
df = get_klines(symbol, limit=1000)
fib_df = RollingFibonacci.calculate_rolling_fibonacci(df, lookback=100)

# 백테스팅 시작 (100번째 캔들부터)
for i in range(100, 1000):
    # 현재 시점의 피보나치
    fib_data = RollingFibonacci.get_fibonacci_at_index(fib_df, i)
    
    # 진입 신호 분석
    signal = analyze_entry(df[i], fib_data)  # ✅ 동적 피보나치
```

---

## 📈 예상 효과

### 백테스팅 결과 변화
```
이전 (Look-ahead Bias 있음):
- 승률: 45% (과대평가)
- ROI: +30% (과대평가)

수정 후 (Look-ahead Bias 없음):
- 승률: 35-40% (실제)
- ROI: +15-25% (실제)
```

**더 낮아지지만 정확함!**

### 실전 거래와의 일치도
```
이전: 백테스팅 +30% → 실전 +10% (큰 차이)
수정: 백테스팅 +20% → 실전 +18% (작은 차이)
```

---

## 🔧 파라미터 조정

### Lookback Period (피보나치 계산 기간)
```python
# 짧은 기간 (빠른 반응, 노이즈 많음)
lookback = 50  # 50개 캔들

# 중간 기간 (균형)
lookback = 100  # 100개 캔들 (권장)

# 긴 기간 (느린 반응, 안정적)
lookback = 200  # 200개 캔들
```

### 타임프레임별 Lookback
```python
timeframes = {
    '5m': 100,   # 5분봉: 8.3시간
    '15m': 100,  # 15분봉: 25시간
    '1h': 100,   # 1시간봉: 4.2일
    '4h': 60,    # 4시간봉: 10일
}
```

---

## 💡 추가 개선사항

### 1. 피보나치 유효성 확인
```python
# 고점/저점이 너무 오래된 경우 제외
if fib_data['high_time'] < current_time - 24hours:
    # 피보나치 무효 (너무 오래됨)
    skip_trade()
```

### 2. 피보나치 범위 확인
```python
# 고점/저점 범위가 너무 작으면 제외
if fib_data['range_pct'] < 2.0:  # 2% 미만
    # 피보나치 무효 (범위 너무 작음)
    skip_trade()
```

### 3. 동적 Lookback
```python
# 변동성에 따라 Lookback 조정
if volatility > 5%:
    lookback = 50  # 변동성 높으면 짧게
else:
    lookback = 100  # 변동성 낮으면 길게
```

---

## 🚀 다음 단계

1. ✅ **롤링 피보나치 구현** (완료)
2. ⏳ **백테스트 엔진 수정**
3. ⏳ **결과 비교** (이전 vs 수정 후)
4. ⏳ **파라미터 최적화**

---

## 🎯 결론

**Look-ahead Bias는 백테스팅의 가장 흔한 실수!**

- 미래 데이터 사용 → 과최적화 → 실전 실패
- 롤링 피보나치 → 정확한 백테스팅 → 실전 성공

**백테스팅 결과가 낮아지더라도, 실전과 일치하는 것이 중요!**
