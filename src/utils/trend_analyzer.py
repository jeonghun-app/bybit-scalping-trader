"""
실시간 단기 추세 분석기
- 비트코인 시장 추세 (시장 전체 방향성)
- 개별 코인 추세 (30분/1시간)
"""
import pandas as pd
from config.config import Config

class TrendAnalyzer:
    
    @staticmethod
    def get_btc_trend(client, timeframe_minutes=60):
        """
        비트코인 추세 분석 (시장 전체 방향성)
        
        Args:
            client: BybitClient 인스턴스
            timeframe_minutes: 분석 기간 (기본 60분)
        
        Returns:
            dict: {
                'trend': 'UPTREND' | 'DOWNTREND' | 'SIDEWAYS',
                'strength': 0-100 (추세 강도),
                'price_change_pct': 변화율,
                'ma_5': 5분봉 이동평균,
                'ma_20': 20분봉 이동평균
            }
        """
        # 비트코인 데이터 가져오기 (1분봉)
        df = client.get_klines('BTCUSDT', interval=1, limit=timeframe_minutes)
        
        if df.empty or len(df) < 20:
            return {
                'trend': 'UNKNOWN',
                'strength': 0,
                'price_change_pct': 0,
                'ma_5': 0,
                'ma_20': 0
            }
        
        # 이동평균 계산
        df['ma_5'] = df['close'].rolling(5).mean()
        df['ma_20'] = df['close'].rolling(20).mean()
        
        latest = df.iloc[-1]
        first = df.iloc[0]
        
        # 가격 변화율
        price_change_pct = ((latest['close'] - first['close']) / first['close']) * 100
        
        # 추세 판단
        ma_5 = latest['ma_5']
        ma_20 = latest['ma_20']
        
        # 추세 강도 계산 (MA 간격)
        if ma_20 > 0:
            ma_diff_pct = ((ma_5 - ma_20) / ma_20) * 100
        else:
            ma_diff_pct = 0
        
        # 추세 분류
        if ma_5 > ma_20 and price_change_pct > 0.3:
            trend = 'UPTREND'
            strength = min(100, abs(ma_diff_pct) * 50 + abs(price_change_pct) * 10)
        elif ma_5 < ma_20 and price_change_pct < -0.3:
            trend = 'DOWNTREND'
            strength = min(100, abs(ma_diff_pct) * 50 + abs(price_change_pct) * 10)
        else:
            trend = 'SIDEWAYS'
            strength = 50 - min(50, abs(ma_diff_pct) * 25)
        
        return {
            'trend': trend,
            'strength': round(strength, 2),
            'price_change_pct': round(price_change_pct, 2),
            'ma_5': round(ma_5, 2),
            'ma_20': round(ma_20, 2)
        }
    
    @staticmethod
    def get_coin_trend(df, timeframe_minutes=30):
        """
        개별 코인 추세 분석 (30분 또는 1시간)
        
        Args:
            df: 캔들 데이터 (최소 30개 이상)
            timeframe_minutes: 분석 기간 (기본 30분)
        
        Returns:
            dict: {
                'trend': 'UPTREND' | 'DOWNTREND' | 'SIDEWAYS',
                'strength': 0-100,
                'price_change_pct': 변화율,
                'volume_trend': 'INCREASING' | 'DECREASING',
                'ma_5': 5봉 이동평균,
                'ma_20': 20봉 이동평균
            }
        """
        if df.empty or len(df) < 20:
            return {
                'trend': 'UNKNOWN',
                'strength': 0,
                'price_change_pct': 0,
                'volume_trend': 'UNKNOWN',
                'ma_5': 0,
                'ma_20': 0
            }
        
        # 최근 N개 봉만 사용
        recent_df = df.tail(timeframe_minutes).copy()
        
        # 이동평균 계산
        recent_df['ma_5'] = recent_df['close'].rolling(5).mean()
        recent_df['ma_20'] = recent_df['close'].rolling(20).mean()
        
        latest = recent_df.iloc[-1]
        first = recent_df.iloc[0]
        
        # 가격 변화율
        price_change_pct = ((latest['close'] - first['close']) / first['close']) * 100
        
        # 거래량 추세
        volume_first_half = recent_df.iloc[:len(recent_df)//2]['volume'].mean()
        volume_second_half = recent_df.iloc[len(recent_df)//2:]['volume'].mean()
        volume_trend = 'INCREASING' if volume_second_half > volume_first_half else 'DECREASING'
        
        # 이동평균
        ma_5 = latest['ma_5']
        ma_20 = latest['ma_20']
        
        # 추세 강도 계산
        if ma_20 > 0:
            ma_diff_pct = ((ma_5 - ma_20) / ma_20) * 100
        else:
            ma_diff_pct = 0
        
        # 추세 분류
        if ma_5 > ma_20 and price_change_pct > 0.5:
            trend = 'UPTREND'
            strength = min(100, abs(ma_diff_pct) * 50 + abs(price_change_pct) * 5)
        elif ma_5 < ma_20 and price_change_pct < -0.5:
            trend = 'DOWNTREND'
            strength = min(100, abs(ma_diff_pct) * 50 + abs(price_change_pct) * 5)
        else:
            trend = 'SIDEWAYS'
            strength = 50 - min(50, abs(ma_diff_pct) * 25)
        
        return {
            'trend': trend,
            'strength': round(strength, 2),
            'price_change_pct': round(price_change_pct, 2),
            'volume_trend': volume_trend,
            'ma_5': round(ma_5, 2) if pd.notna(ma_5) else 0,
            'ma_20': round(ma_20, 2) if pd.notna(ma_20) else 0
        }
    
    @staticmethod
    def should_enter_long(btc_trend, coin_trend):
        """
        롱 진입 가능 여부 판단
        
        조건:
        1. 비트코인이 상승 또는 횡보 (하락장 제외)
        2. 코인이 상승 추세
        3. 거래량 증가 중
        
        Returns:
            tuple: (bool, str) - (진입 가능 여부, 이유)
        """
        # 비트코인 하락장이면 롱 진입 금지
        if btc_trend['trend'] == 'DOWNTREND' and btc_trend['strength'] > 60:
            return False, f"비트코인 강한 하락장 (BTC {btc_trend['price_change_pct']:.2f}%)"
        
        # 코인이 하락 추세면 롱 진입 금지
        if coin_trend['trend'] == 'DOWNTREND':
            return False, f"코인 하락 추세 ({coin_trend['price_change_pct']:.2f}%)"
        
        # 코인이 상승 추세이고 거래량 증가 중이면 진입
        if coin_trend['trend'] == 'UPTREND' and coin_trend['volume_trend'] == 'INCREASING':
            return True, f"강한 상승 추세 (코인 {coin_trend['price_change_pct']:.2f}%, BTC {btc_trend['price_change_pct']:.2f}%)"
        
        # 코인이 상승 추세이지만 거래량 감소 중
        if coin_trend['trend'] == 'UPTREND':
            return True, f"상승 추세 (코인 {coin_trend['price_change_pct']:.2f}%, 거래량 감소 주의)"
        
        # 횡보장
        return False, f"횡보장 (코인 {coin_trend['price_change_pct']:.2f}%, BTC {btc_trend['price_change_pct']:.2f}%)"
    
    @staticmethod
    def should_enter_short(btc_trend, coin_trend):
        """
        숏 진입 가능 여부 판단
        
        조건:
        1. 비트코인이 하락 또는 횡보 (상승장 제외)
        2. 코인이 하락 추세
        3. 거래량 증가 중
        
        Returns:
            tuple: (bool, str) - (진입 가능 여부, 이유)
        """
        # 비트코인 상승장이면 숏 진입 금지
        if btc_trend['trend'] == 'UPTREND' and btc_trend['strength'] > 60:
            return False, f"비트코인 강한 상승장 (BTC {btc_trend['price_change_pct']:.2f}%)"
        
        # 코인이 상승 추세면 숏 진입 금지
        if coin_trend['trend'] == 'UPTREND':
            return False, f"코인 상승 추세 ({coin_trend['price_change_pct']:.2f}%)"
        
        # 코인이 하락 추세이고 거래량 증가 중이면 진입
        if coin_trend['trend'] == 'DOWNTREND' and coin_trend['volume_trend'] == 'INCREASING':
            return True, f"강한 하락 추세 (코인 {coin_trend['price_change_pct']:.2f}%, BTC {btc_trend['price_change_pct']:.2f}%)"
        
        # 코인이 하락 추세이지만 거래량 감소 중
        if coin_trend['trend'] == 'DOWNTREND':
            return True, f"하락 추세 (코인 {coin_trend['price_change_pct']:.2f}%, 거래량 감소 주의)"
        
        # 횡보장
        return False, f"횡보장 (코인 {coin_trend['price_change_pct']:.2f}%, BTC {btc_trend['price_change_pct']:.2f}%)"
