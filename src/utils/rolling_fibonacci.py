"""
롤링 피보나치 계산기 - Look-ahead Bias 방지
각 시점에서 그 시점까지의 데이터만 사용하여 피보나치 계산
"""
import pandas as pd
import numpy as np

class RollingFibonacci:
    
    @staticmethod
    def calculate_fibonacci_levels(high, low):
        """피보나치 되돌림 레벨 계산"""
        diff = high - low
        levels = {
            '0.0': low,
            '0.236': low + (diff * 0.236),
            '0.382': low + (diff * 0.382),
            '0.5': low + (diff * 0.5),
            '0.618': low + (diff * 0.618),
            '0.786': low + (diff * 0.786),
            '1.0': high
        }
        return levels
    
    @staticmethod
    def calculate_rolling_fibonacci(df, lookback_period=100):
        """
        롤링 피보나치 계산 (Look-ahead Bias 방지)
        
        각 시점에서 최근 N개 캔들의 고점/저점으로 피보나치 계산
        
        Args:
            df: 캔들 데이터
            lookback_period: 피보나치 계산에 사용할 최근 캔들 수 (기본 100개)
        
        Returns:
            DataFrame with fibonacci levels for each candle
        """
        if len(df) < lookback_period:
            return None
        
        fib_data = []
        
        for i in range(lookback_period, len(df)):
            # 현재 시점에서 최근 N개 캔들만 사용
            window = df.iloc[i-lookback_period:i]
            
            high = window['high'].max()
            low = window['low'].min()
            
            # 고점/저점이 언제 발생했는지 확인
            high_idx = window['high'].idxmax()
            low_idx = window['low'].idxmin()
            
            # 피보나치 레벨 계산
            fib_levels = RollingFibonacci.calculate_fibonacci_levels(high, low)
            
            fib_data.append({
                'index': i,
                'timestamp': df.iloc[i]['timestamp'],
                'high': high,
                'low': low,
                'high_time': window.loc[high_idx, 'timestamp'],
                'low_time': window.loc[low_idx, 'timestamp'],
                'levels': fib_levels,
                'range': high - low,
                'range_pct': ((high - low) / low) * 100
            })
        
        return pd.DataFrame(fib_data)
    
    @staticmethod
    def get_fibonacci_at_index(fib_df, index):
        """
        특정 인덱스의 피보나치 레벨 가져오기
        
        Args:
            fib_df: calculate_rolling_fibonacci 결과
            index: 캔들 인덱스
        
        Returns:
            dict: 피보나치 레벨 정보
        """
        if fib_df is None or fib_df.empty:
            return None
        
        # 해당 인덱스의 피보나치 찾기
        row = fib_df[fib_df['index'] == index]
        
        if row.empty:
            return None
        
        return {
            'levels': row.iloc[0]['levels'],
            'high': row.iloc[0]['high'],
            'low': row.iloc[0]['low'],
            'range': row.iloc[0]['range']
        }
    
    @staticmethod
    def calculate_multi_timeframe_rolling_fibonacci(df, timeframes):
        """
        멀티 타임프레임 롤링 피보나치
        
        Args:
            df: 1분봉 데이터
            timeframes: {
                '5m': 100,   # 5분봉 100개 = 500분
                '15m': 100,  # 15분봉 100개 = 1500분
                '1h': 100,   # 1시간봉 100개 = 100시간
            }
        
        Returns:
            dict: 각 타임프레임별 롤링 피보나치
        """
        mtf_fib = {}
        
        for timeframe_name, lookback in timeframes.items():
            # 타임프레임에 따라 리샘플링
            if timeframe_name == '5m':
                resampled = RollingFibonacci._resample_to_5m(df)
                fib_df = RollingFibonacci.calculate_rolling_fibonacci(resampled, lookback)
            elif timeframe_name == '15m':
                resampled = RollingFibonacci._resample_to_15m(df)
                fib_df = RollingFibonacci.calculate_rolling_fibonacci(resampled, lookback)
            elif timeframe_name == '1h':
                resampled = RollingFibonacci._resample_to_1h(df)
                fib_df = RollingFibonacci.calculate_rolling_fibonacci(resampled, lookback)
            else:
                continue
            
            if fib_df is not None:
                mtf_fib[timeframe_name] = fib_df
        
        return mtf_fib
    
    @staticmethod
    def _resample_to_5m(df):
        """1분봉을 5분봉으로 리샘플링"""
        df = df.copy()
        df.set_index('timestamp', inplace=True)
        
        resampled = df.resample('5T').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
        
        resampled.reset_index(inplace=True)
        return resampled
    
    @staticmethod
    def _resample_to_15m(df):
        """1분봉을 15분봉으로 리샘플링"""
        df = df.copy()
        df.set_index('timestamp', inplace=True)
        
        resampled = df.resample('15T').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
        
        resampled.reset_index(inplace=True)
        return resampled
    
    @staticmethod
    def _resample_to_1h(df):
        """1분봉을 1시간봉으로 리샘플링"""
        df = df.copy()
        df.set_index('timestamp', inplace=True)
        
        resampled = df.resample('1H').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
        
        resampled.reset_index(inplace=True)
        return resampled
    
    @staticmethod
    def is_near_fibonacci_level(price, fib_levels, tolerance=0.015):
        """가격이 피보나치 레벨 근처인지 확인"""
        if not fib_levels:
            return False, None, None
        
        for level_name, level_price in fib_levels.items():
            if level_name in ['0.236', '0.382', '0.5', '0.618', '0.786']:
                diff_pct = abs(price - level_price) / price
                if diff_pct <= tolerance:
                    return True, level_name, level_price
        
        return False, None, None
