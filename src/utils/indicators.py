import pandas as pd
import numpy as np

class Indicators:
    @staticmethod
    def calculate_bollinger_bands(df, period=20, std=2):
        """볼린저 밴드 계산"""
        df = df.copy()
        df['bb_middle'] = df['close'].rolling(window=period).mean()
        df['bb_std'] = df['close'].rolling(window=period).std()
        df['bb_upper'] = df['bb_middle'] + (df['bb_std'] * std)
        df['bb_lower'] = df['bb_middle'] - (df['bb_std'] * std)
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle'] * 100
        return df
    
    @staticmethod
    def calculate_fibonacci_levels(high, low):
        """피보나치 되돌림 레벨 계산 (하락 후 반등 기준)"""
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
    def calculate_multi_timeframe_fibonacci(client, symbol, timeframes_config):
        """멀티 타임프레임 피보나치 계산"""
        fib_data = {}
        
        for interval, days in timeframes_config.items():
            df = client.get_klines_for_days(symbol, interval, days)
            
            if not df.empty and len(df) > 0:
                high = df['high'].max()
                low = df['low'].min()
                fib_levels = Indicators.calculate_fibonacci_levels(high, low)
                
                fib_data[interval] = {
                    'levels': fib_levels,
                    'high': high,
                    'low': low,
                    'range': high - low
                }
        
        return fib_data
    
    @staticmethod
    def calculate_volatility(df, period=14):
        """변동성 계산 (ATR 기반)"""
        df = df.copy()
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = abs(df['high'] - df['close'].shift(1))
        df['tr3'] = abs(df['low'] - df['close'].shift(1))
        df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        df['atr'] = df['tr'].rolling(window=period).mean()
        df['volatility_pct'] = (df['atr'] / df['close']) * 100
        return df
    
    @staticmethod
    def calculate_rsi(df, period=14):
        """RSI 계산"""
        df = df.copy()
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        return df
    
    @staticmethod
    def is_near_fibonacci_level(price, fib_levels, tolerance=0.015):
        """가격이 피보나치 레벨 근처인지 확인"""
        for level_name, level_price in fib_levels.items():
            if level_name in ['0.382', '0.5', '0.618', '0.786']:
                diff_pct = abs(price - level_price) / price
                if diff_pct <= tolerance:
                    return True, level_name, level_price
        return False, None, None
