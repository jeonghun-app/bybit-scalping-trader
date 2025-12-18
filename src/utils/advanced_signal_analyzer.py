"""
고급 신호 분석기 - 다중 요소 종합 판단
1. 피보나치 거리 분석
2. 비트코인 상관관계
3. 펀딩비 (Funding Rate)
4. 추세 + 지표 종합
"""
import pandas as pd
from config.config import Config

class AdvancedSignalAnalyzer:
    
    @staticmethod
    def analyze_fib_distance(current_price, fib_levels):
        """
        현재 가격에서 주요 피보나치 레벨까지의 거리 분석
        
        Returns:
            dict: {
                'nearest_support': (level_name, price, distance_pct),
                'nearest_resistance': (level_name, price, distance_pct),
                'has_room_to_fall': bool,  # 하단까지 거리가 있는가?
                'has_room_to_rise': bool,  # 상단까지 거리가 있는가?
            }
        """
        if not fib_levels:
            return None
        
        # 지지선 (현재 가격 아래)
        supports = [(name, price) for name, price in fib_levels.items() if price < current_price]
        # 저항선 (현재 가격 위)
        resistances = [(name, price) for name, price in fib_levels.items() if price > current_price]
        
        nearest_support = None
        nearest_resistance = None
        
        if supports:
            # 가장 가까운 지지선
            nearest_support = max(supports, key=lambda x: x[1])
            support_distance_pct = ((current_price - nearest_support[1]) / current_price) * 100
            nearest_support = (nearest_support[0], nearest_support[1], support_distance_pct)
        
        if resistances:
            # 가장 가까운 저항선
            nearest_resistance = min(resistances, key=lambda x: x[1])
            resistance_distance_pct = ((nearest_resistance[1] - current_price) / current_price) * 100
            nearest_resistance = (nearest_resistance[0], nearest_resistance[1], resistance_distance_pct)
        
        # 하락/상승 여유 공간 판단
        has_room_to_fall = nearest_support and nearest_support[2] > 1.0  # 1% 이상 거리
        has_room_to_rise = nearest_resistance and nearest_resistance[2] > 1.0  # 1% 이상 거리
        
        return {
            'nearest_support': nearest_support,
            'nearest_resistance': nearest_resistance,
            'has_room_to_fall': has_room_to_fall,
            'has_room_to_rise': has_room_to_rise
        }
    
    @staticmethod
    def get_funding_rate(client, symbol):
        """
        펀딩비 조회 (Bybit API)
        
        양수: 롱 포지션이 숏에게 지불 (롱 과열)
        음수: 숏 포지션이 롱에게 지불 (숏 과열)
        
        Returns:
            dict: {
                'funding_rate': 0.0001,  # 0.01%
                'funding_rate_pct': 0.01,
                'sentiment': 'LONG_HEAVY' | 'SHORT_HEAVY' | 'NEUTRAL'
            }
        """
        try:
            # Bybit API로 펀딩비 조회
            response = client.session.get_tickers(
                category="linear",
                symbol=symbol
            )
            
            if response['retCode'] == 0 and response['result']['list']:
                ticker = response['result']['list'][0]
                funding_rate = float(ticker.get('fundingRate', 0))
                funding_rate_pct = funding_rate * 100
                
                # 펀딩비 기준 시장 심리 판단
                if funding_rate > 0.0001:  # 0.01% 이상
                    sentiment = 'LONG_HEAVY'  # 롱 과열
                elif funding_rate < -0.0001:  # -0.01% 이하
                    sentiment = 'SHORT_HEAVY'  # 숏 과열
                else:
                    sentiment = 'NEUTRAL'
                
                return {
                    'funding_rate': funding_rate,
                    'funding_rate_pct': round(funding_rate_pct, 4),
                    'sentiment': sentiment
                }
        except Exception as e:
            print(f"펀딩비 조회 실패: {e}")
        
        return {
            'funding_rate': 0,
            'funding_rate_pct': 0,
            'sentiment': 'NEUTRAL'
        }
    
    @staticmethod
    def should_enter_short_on_downtrend(
        current_price, 
        fib_levels, 
        btc_trend, 
        coin_trend, 
        funding_info,
        rsi
    ):
        """
        하락 추세 중 숏 진입 고급 판단
        
        시나리오: 하락 중인데 피보나치 하단까지 거리가 있음
        → 하단까지 더 떨어질 수 있으니 숏 진입
        
        조건:
        1. 코인이 하락 추세
        2. 피보나치 하단까지 거리가 있음 (1% 이상)
        3. 비트코인도 하락 또는 횡보
        4. (선택) 펀딩비가 양수 (롱 과열) → 숏 유리
        5. RSI가 아직 과매도 아님 (30 이상)
        
        Returns:
            tuple: (bool, str, int) - (진입 가능, 이유, 신뢰도 0-100)
        """
        fib_distance = AdvancedSignalAnalyzer.analyze_fib_distance(current_price, fib_levels)
        
        if not fib_distance:
            return False, "피보나치 데이터 없음", 0
        
        reasons = []
        confidence = 0
        
        # 1. 코인 하락 추세 확인
        if coin_trend['trend'] != 'DOWNTREND':
            return False, "코인이 하락 추세 아님", 0
        
        reasons.append(f"코인 하락 추세 ({coin_trend['price_change_pct']:.2f}%)")
        confidence += 30
        
        # 2. 피보나치 하단까지 거리 확인
        if not fib_distance['has_room_to_fall']:
            return False, "피보나치 하단에 근접 (반등 가능성)", 0
        
        support_distance = fib_distance['nearest_support'][2]
        reasons.append(f"하단까지 {support_distance:.1f}% 여유")
        confidence += 25
        
        # 3. 비트코인 추세 확인
        if btc_trend['trend'] == 'UPTREND' and btc_trend['strength'] > 60:
            return False, "비트코인 강한 상승 (역행 위험)", 0
        
        if btc_trend['trend'] == 'DOWNTREND':
            reasons.append(f"BTC도 하락 ({btc_trend['price_change_pct']:.2f}%)")
            confidence += 20
        else:
            reasons.append(f"BTC 횡보 ({btc_trend['price_change_pct']:.2f}%)")
            confidence += 10
        
        # 4. 펀딩비 확인 (선택적)
        if funding_info['sentiment'] == 'LONG_HEAVY':
            reasons.append(f"롱 과열 (펀딩비 {funding_info['funding_rate_pct']:.3f}%)")
            confidence += 15
        elif funding_info['sentiment'] == 'SHORT_HEAVY':
            reasons.append(f"숏 과열 주의 (펀딩비 {funding_info['funding_rate_pct']:.3f}%)")
            confidence -= 10
        
        # 5. RSI 확인 (과매도 아닌지)
        if rsi < 30:
            return False, "RSI 과매도 (반등 위험)", 0
        
        if rsi > 50:
            reasons.append(f"RSI 여유 ({rsi:.1f})")
            confidence += 10
        
        # 최종 판단
        if confidence >= 60:
            return True, " | ".join(reasons), confidence
        else:
            return False, f"신뢰도 부족 ({confidence}점)", confidence
    
    @staticmethod
    def should_enter_long_on_uptrend(
        current_price, 
        fib_levels, 
        btc_trend, 
        coin_trend, 
        funding_info,
        rsi
    ):
        """
        상승 추세 중 롱 진입 고급 판단
        
        시나리오: 상승 중인데 피보나치 상단까지 거리가 있음
        → 상단까지 더 오를 수 있으니 롱 진입
        
        조건:
        1. 코인이 상승 추세
        2. 피보나치 상단까지 거리가 있음 (1% 이상)
        3. 비트코인도 상승 또는 횡보
        4. (선택) 펀딩비가 음수 (숏 과열) → 롱 유리
        5. RSI가 아직 과매수 아님 (70 이하)
        
        Returns:
            tuple: (bool, str, int) - (진입 가능, 이유, 신뢰도 0-100)
        """
        fib_distance = AdvancedSignalAnalyzer.analyze_fib_distance(current_price, fib_levels)
        
        if not fib_distance:
            return False, "피보나치 데이터 없음", 0
        
        reasons = []
        confidence = 0
        
        # 1. 코인 상승 추세 확인
        if coin_trend['trend'] != 'UPTREND':
            return False, "코인이 상승 추세 아님", 0
        
        reasons.append(f"코인 상승 추세 ({coin_trend['price_change_pct']:.2f}%)")
        confidence += 30
        
        # 2. 피보나치 상단까지 거리 확인
        if not fib_distance['has_room_to_rise']:
            return False, "피보나치 상단에 근접 (저항 가능성)", 0
        
        resistance_distance = fib_distance['nearest_resistance'][2]
        reasons.append(f"상단까지 {resistance_distance:.1f}% 여유")
        confidence += 25
        
        # 3. 비트코인 추세 확인
        if btc_trend['trend'] == 'DOWNTREND' and btc_trend['strength'] > 60:
            return False, "비트코인 강한 하락 (역행 위험)", 0
        
        if btc_trend['trend'] == 'UPTREND':
            reasons.append(f"BTC도 상승 ({btc_trend['price_change_pct']:.2f}%)")
            confidence += 20
        else:
            reasons.append(f"BTC 횡보 ({btc_trend['price_change_pct']:.2f}%)")
            confidence += 10
        
        # 4. 펀딩비 확인 (선택적)
        if funding_info['sentiment'] == 'SHORT_HEAVY':
            reasons.append(f"숏 과열 (펀딩비 {funding_info['funding_rate_pct']:.3f}%)")
            confidence += 15
        elif funding_info['sentiment'] == 'LONG_HEAVY':
            reasons.append(f"롱 과열 주의 (펀딩비 {funding_info['funding_rate_pct']:.3f}%)")
            confidence -= 10
        
        # 5. RSI 확인 (과매수 아닌지)
        if rsi > 70:
            return False, "RSI 과매수 (하락 위험)", 0
        
        if rsi < 50:
            reasons.append(f"RSI 여유 ({rsi:.1f})")
            confidence += 10
        
        # 최종 판단
        if confidence >= 60:
            return True, " | ".join(reasons), confidence
        else:
            return False, f"신뢰도 부족 ({confidence}점)", confidence
    
    @staticmethod
    def should_enter_long_at_support(
        current_price, 
        fib_levels, 
        btc_trend, 
        coin_trend, 
        funding_info,
        rsi,
        bb_position
    ):
        """
        지지선 근처에서 롱 진입 판단 (반등 노리기)
        
        시나리오: 하락 후 피보나치 지지선 근처 도달
        → 반등 가능성 높으니 롱 진입
        
        조건:
        1. 피보나치 지지선 근처 (1% 이내)
        2. RSI 과매도 (30 이하)
        3. 볼린저 밴드 하단 근처
        4. 비트코인이 강한 하락 아님
        5. (선택) 펀딩비가 음수 (숏 과열)
        
        Returns:
            tuple: (bool, str, int) - (진입 가능, 이유, 신뢰도 0-100)
        """
        fib_distance = AdvancedSignalAnalyzer.analyze_fib_distance(current_price, fib_levels)
        
        if not fib_distance or not fib_distance['nearest_support']:
            return False, "지지선 데이터 없음", 0
        
        reasons = []
        confidence = 0
        
        # 1. 지지선 근처 확인
        support_distance = fib_distance['nearest_support'][2]
        if support_distance > 1.0:
            return False, f"지지선까지 {support_distance:.1f}% (아직 멀음)", 0
        
        support_name = fib_distance['nearest_support'][0]
        reasons.append(f"{support_name} 지지선 근처 ({support_distance:.2f}%)")
        confidence += 30
        
        # 2. RSI 과매도 확인
        if rsi > 35:
            return False, f"RSI 과매도 아님 ({rsi:.1f})", 0
        
        reasons.append(f"RSI 과매도 ({rsi:.1f})")
        confidence += 25
        
        # 3. 볼린저 밴드 하단 확인
        if bb_position > 0.2:  # 하단 20% 이내
            return False, f"볼린저 밴드 하단 아님 ({bb_position*100:.0f}%)", 0
        
        reasons.append(f"볼린저 하단 ({bb_position*100:.0f}%)")
        confidence += 20
        
        # 4. 비트코인 추세 확인
        if btc_trend['trend'] == 'DOWNTREND' and btc_trend['strength'] > 70:
            return False, "비트코인 폭락 중 (반등 어려움)", 0
        
        if btc_trend['trend'] == 'UPTREND':
            reasons.append(f"BTC 상승 ({btc_trend['price_change_pct']:.2f}%)")
            confidence += 15
        else:
            reasons.append(f"BTC 안정 ({btc_trend['price_change_pct']:.2f}%)")
            confidence += 5
        
        # 5. 펀딩비 확인
        if funding_info['sentiment'] == 'SHORT_HEAVY':
            reasons.append(f"숏 과열 (펀딩비 {funding_info['funding_rate_pct']:.3f}%)")
            confidence += 10
        
        # 최종 판단
        if confidence >= 65:
            return True, " | ".join(reasons), confidence
        else:
            return False, f"신뢰도 부족 ({confidence}점)", confidence
