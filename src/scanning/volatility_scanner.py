from src.utils.bybit_client import BybitClient
from src.utils.indicators import Indicators
from config.config import Config
import pandas as pd
import sys

class VolatilityScanner:
    def __init__(self):
        self.client = BybitClient()
    
    def scan_coins(self):
        """거래량과 변동성 기준으로 코인 스캔 (Bybit API 티커 데이터 활용)"""
        print("\n" + "="*80)
        print("코인 스캔 시작 (Bybit API 티커 데이터)")
        print("="*80)
        
        # USDT 무기한 선물 목록 가져오기
        tickers = self.client.get_usdt_perpetuals()
        print(f"총 {len(tickers)}개 페어 발견")
        
        # 티커 데이터에서 직접 정보 추출
        print("티커 데이터 분석 중...", end='', flush=True)
        coin_data = []
        for ticker in tickers:
            volume = float(ticker.get('volume24h', 0))
            turnover = float(ticker.get('turnover24h', 0))
            price_change_pct = abs(float(ticker.get('price24hPcnt', 0)) * 100)
            
            if volume > 0 and turnover > 0:
                coin_data.append({
                    'symbol': ticker['symbol'],
                    'volume': volume,
                    'turnover': turnover,
                    'price': float(ticker.get('lastPrice', 0)),
                    'price_change_24h': float(ticker.get('price24hPcnt', 0)) * 100,
                    'price_change_abs': price_change_pct,  # 절대값 (변동성 지표)
                    'high_24h': float(ticker.get('highPrice24h', 0)),
                    'low_24h': float(ticker.get('lowPrice24h', 0))
                })
        
        df = pd.DataFrame(coin_data)
        
        # 24시간 변동폭 계산 (High-Low / Price)
        df['volatility_24h'] = ((df['high_24h'] - df['low_24h']) / df['price']) * 100
        
        print(f" ✅ {len(df)}개 활성 페어")
        
        # 1. 거래량 상위 20개
        print("\n[1] 거래량 상위 20개 선택...", end='', flush=True)
        top_volume = df.nlargest(20, 'turnover').copy()
        print(" ✅")
        
        # 2. 변동성 상위 20개 (24시간 변동폭 기준)
        print("[2] 변동성 상위 20개 선택 (24h 변동폭)...", end='', flush=True)
        top_volatility = df.nlargest(20, 'volatility_24h').copy()
        print(" ✅")
        
        # 결과 출력
        self._print_results(top_volume, top_volatility)
        
        # 백테스팅용: 두 그룹 합치기 (중복 제거)
        combined = pd.concat([top_volume, top_volatility]).drop_duplicates(subset=['symbol'])
        
        return combined
    
    def _print_results(self, top_volume, top_volatility):
        """결과 출력"""
        print("\n" + "="*80)
        print("📊 거래량(Turnover) 상위 20개 코인")
        print("="*80)
        display_vol = top_volume[['symbol', 'turnover', 'volume', 'price', 'price_change_24h', 'volatility_24h']].head(20).copy()
        display_vol['turnover'] = display_vol['turnover'].apply(lambda x: f"${x:,.0f}")
        display_vol['volume'] = display_vol['volume'].apply(lambda x: f"{x:,.0f}")
        display_vol['price'] = display_vol['price'].apply(lambda x: f"${x:.6f}")
        display_vol['price_change_24h'] = display_vol['price_change_24h'].apply(lambda x: f"{x:+.2f}%")
        display_vol['volatility_24h'] = display_vol['volatility_24h'].apply(lambda x: f"{x:.2f}%")
        print(display_vol.to_string(index=False))
        
        print("\n" + "="*80)
        print("🔥 변동성(24h 변동폭) 상위 20개 코인")
        print("="*80)
        display_volatility = top_volatility[['symbol', 'volatility_24h', 'turnover', 'volume', 'price', 'price_change_24h']].head(20).copy()
        display_volatility['volatility_24h'] = display_volatility['volatility_24h'].apply(lambda x: f"{x:.2f}%")
        display_volatility['turnover'] = display_volatility['turnover'].apply(lambda x: f"${x:,.0f}")
        display_volatility['volume'] = display_volatility['volume'].apply(lambda x: f"{x:,.0f}")
        display_volatility['price'] = display_volatility['price'].apply(lambda x: f"${x:.6f}")
        display_volatility['price_change_24h'] = display_volatility['price_change_24h'].apply(lambda x: f"{x:+.2f}%")
        print(display_volatility.to_string(index=False))
        
        print("\n" + "="*80)
    
    def scan_high_volatility_coins(self):
        """기존 호환성 유지"""
        return self.scan_coins()
