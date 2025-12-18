# 빠른 백테스팅을 위한 팁

## 🚀 즉시 적용 가능한 방법

### 1. 캔들 수 줄이기 (가장 빠름!)
```python
# config/config.py
BACKTEST_CANDLES = 200  # 1000 → 200 (5배 빠름!)
```

**효과**: 1000개 → 200개 = **5배 빠름**
**단점**: 데이터가 적어서 정확도 낮음
**용도**: 빠른 테스트용

### 2. 코인 수 줄이기
```python
# config/config.py
TOP_BACKTEST_COINS = 3  # 10 → 3 (3배 빠름!)
```

**효과**: 10개 → 3개 = **3배 빠름**
**단점**: 다양한 코인 테스트 불가
**용도**: 전략 개발 중 빠른 검증

### 3. 피보나치 타임프레임 줄이기
```python
# config/config.py
FIBONACCI_TIMEFRAMES = [15, 60]  # 5개 → 2개 (2배 빠름!)
```

**효과**: 5개 → 2개 = **2배 빠름**
**단점**: 멀티 타임프레임 분석 약화
**용도**: 빠른 테스트용

### 4. 3분봉만 테스트
```python
# main_backtest.py
# 1분봉 주석 처리
# backtest_1m()  # 주석

# 3분봉만 실행
backtest_3m()
```

**효과**: **2배 빠름**
**단점**: 1분봉 결과 없음
**용도**: 3분봉 전략 집중 개발

---

## 📊 조합 예시

### 초고속 테스트 (10초)
```python
BACKTEST_CANDLES = 100
TOP_BACKTEST_COINS = 2
FIBONACCI_TIMEFRAMES = [60]
# 3분봉만
```
**속도**: 약 10초
**용도**: 코드 수정 후 즉시 확인

### 빠른 테스트 (30초)
```python
BACKTEST_CANDLES = 200
TOP_BACKTEST_COINS = 3
FIBONACCI_TIMEFRAMES = [15, 60]
# 3분봉만
```
**속도**: 약 30초
**용도**: 전략 개발 중

### 표준 테스트 (2-3분)
```python
BACKTEST_CANDLES = 500
TOP_BACKTEST_COINS = 5
FIBONACCI_TIMEFRAMES = [5, 15, 60]
# 1분봉 + 3분봉
```
**속도**: 약 2-3분
**용도**: 중간 검증

### 완전 테스트 (5-10분)
```python
BACKTEST_CANDLES = 1000
TOP_BACKTEST_COINS = 10
FIBONACCI_TIMEFRAMES = [5, 15, 30, 60, 240]
# 1분봉 + 3분봉
```
**속도**: 약 5-10분
**용도**: 최종 검증

---

## 🎯 권장 워크플로우

### 1단계: 초고속 테스트 (10초)
```bash
# 코드 수정
# config.py에서 BACKTEST_CANDLES = 100
python main_backtest.py
# 에러 없는지 확인
```

### 2단계: 빠른 테스트 (30초)
```bash
# config.py에서 BACKTEST_CANDLES = 200
python main_backtest.py
# 승률, ROI 대략 확인
```

### 3단계: 표준 테스트 (2-3분)
```bash
# config.py에서 BACKTEST_CANDLES = 500
python main_backtest.py
# 전략 효과 확인
```

### 4단계: 완전 테스트 (5-10분)
```bash
# config.py에서 BACKTEST_CANDLES = 1000
python main_backtest.py
# 최종 결과 확인
```

---

## 💡 추가 팁

### 1. 진행 상황 확인
```python
# 현재 어느 코인 처리 중인지 표시됨
print(f"심볼: {symbol}")
```

### 2. 중간 결과 확인
```python
# 각 코인마다 결과 출력됨
print(f"승률: {wins}/{total}")
```

### 3. 특정 코인만 테스트
```python
# main_backtest.py
symbols = ['BTCUSDT', 'ETHUSDT']  # 원하는 코인만
backtest.run_backtest(symbols=symbols)
```

---

## 🔧 Config 파일 수정

```python
# config/config.py

# 빠른 테스트용
BACKTEST_CANDLES = 200  # 기본 1000
TOP_BACKTEST_COINS = 3  # 기본 10
FIBONACCI_TIMEFRAMES = [15, 60]  # 기본 [5, 15, 30, 60, 240]

# 완전 테스트용 (주석 해제)
# BACKTEST_CANDLES = 1000
# TOP_BACKTEST_COINS = 10
# FIBONACCI_TIMEFRAMES = [5, 15, 30, 60, 240]
```

---

## 📈 예상 시간

| 설정 | 캔들 | 코인 | 타임프레임 | 예상 시간 |
|------|------|------|------------|-----------|
| 초고속 | 100 | 2 | 1개 | 10초 |
| 빠름 | 200 | 3 | 2개 | 30초 |
| 표준 | 500 | 5 | 3개 | 2-3분 |
| 완전 | 1000 | 10 | 5개 | 5-10분 |

---

## 🎯 결론

**개발 중**: 100-200 캔들, 2-3 코인 (10-30초)
**검증 시**: 500 캔들, 5 코인 (2-3분)
**최종 확인**: 1000 캔들, 10 코인 (5-10분)

이렇게 하면 개발 속도가 10배 빨라집니다!
