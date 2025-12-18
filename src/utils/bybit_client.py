from pybit.unified_trading import HTTP
from config.config import Config
import pandas as pd
from datetime import datetime, timedelta
import time

class BybitClient:
    def __init__(self):
        self.session = HTTP(
            testnet=Config.BYBIT_TESTNET,
            api_key=Config.BYBIT_API_KEY,
            api_secret=Config.BYBIT_API_SECRET
        )
    
    def get_tickers(self, category='linear'):
        """모든 티커 정보 가져오기"""
        try:
            response = self.session.get_tickers(category=category)
            if response['retCode'] == 0:
                return response['result']['list']
            return []
        except Exception as e:
            print(f"티커 조회 오류: {e}")
            return []
    
    def get_klines(self, symbol, interval='60', limit=200):
        """K라인(캔들) 데이터 가져오기 (UTC 시간)"""
        try:
            response = self.session.get_kline(
                category='linear',
                symbol=symbol,
                interval=interval,
                limit=limit
            )
            if response['retCode'] == 0:
                klines = response['result']['list']
                # 데이터프레임으로 변환
                df = pd.DataFrame(klines, columns=[
                    'timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'
                ])
                df = df.astype({
                    'open': float,
                    'high': float,
                    'low': float,
                    'close': float,
                    'volume': float
                })
                # UTC 시간으로 변환
                df['timestamp'] = pd.to_datetime(df['timestamp'].astype(int), unit='ms', utc=True)
                df = df.sort_values('timestamp').reset_index(drop=True)
                return df
            return pd.DataFrame()
        except Exception as e:
            print(f"K라인 조회 오류 ({symbol}): {e}")
            return pd.DataFrame()
    
    def get_klines_for_days(self, symbol, interval, days):
        """특정 기간의 K라인 데이터 가져오기"""
        # 인터벌별 필요한 캔들 수 계산
        interval_minutes = self._interval_to_minutes(interval)
        required_candles = int((days * 24 * 60) / interval_minutes)
        
        # Bybit API 제한: 최대 200개씩
        all_data = []
        remaining = min(required_candles, 1000)  # 최대 1000개
        
        while remaining > 0:
            limit = min(remaining, 200)
            df = self.get_klines(symbol, interval=interval, limit=limit)
            
            if df.empty:
                break
            
            all_data.append(df)
            remaining -= limit
            
            if remaining > 0:
                time.sleep(0.1)  # Rate limit 방지
        
        if all_data:
            result = pd.concat(all_data, ignore_index=True)
            result = result.drop_duplicates(subset=['timestamp']).sort_values('timestamp').reset_index(drop=True)
            return result
        
        return pd.DataFrame()
    
    def _interval_to_minutes(self, interval):
        """인터벌을 분으로 변환"""
        if interval == 'D':
            return 1440
        return int(interval)
    
    def get_usdt_perpetuals(self):
        """USDT 무기한 선물 목록 가져오기"""
        tickers = self.get_tickers(category='linear')
        usdt_pairs = [
            ticker for ticker in tickers 
            if ticker['symbol'].endswith('USDT')
        ]
        return usdt_pairs
    
    def get_instrument_info(self, symbol):
        """심볼의 거래 규칙 조회 (tickSize, qtyStep 등)"""
        try:
            response = self.session.get_instruments_info(
                category='linear',
                symbol=symbol
            )
            
            if response['retCode'] == 0 and response['result']['list']:
                instrument = response['result']['list'][0]
                
                # 가격 필터
                price_filter = instrument['priceFilter']
                tick_size = float(price_filter['tickSize'])
                min_price = float(price_filter['minPrice'])
                max_price = float(price_filter['maxPrice'])
                
                # 수량 필터
                lot_size_filter = instrument['lotSizeFilter']
                qty_step = float(lot_size_filter['qtyStep'])
                min_order_qty = float(lot_size_filter['minOrderQty'])
                max_order_qty = float(lot_size_filter['maxOrderQty'])
                
                # 소수점 자릿수 계산 (과학적 표기법 처리)
                # 1e-05 -> 5자리, 0.01 -> 2자리
                if tick_size < 1:
                    price_decimals = len(f"{tick_size:.10f}".rstrip('0').split('.')[-1])
                else:
                    price_decimals = 0
                
                if qty_step < 1:
                    qty_decimals = len(f"{qty_step:.10f}".rstrip('0').split('.')[-1])
                else:
                    qty_decimals = 0
                
                return {
                    'symbol': symbol,
                    'tick_size': tick_size,
                    'min_price': min_price,
                    'max_price': max_price,
                    'price_decimals': price_decimals,
                    'qty_step': qty_step,
                    'min_order_qty': min_order_qty,
                    'max_order_qty': max_order_qty,
                    'qty_decimals': qty_decimals
                }
            
            return None
            
        except Exception as e:
            print(f"심볼 정보 조회 오류 ({symbol}): {e}")
            return None
    
    def round_price(self, price, tick_size, price_decimals):
        """가격을 tickSize에 맞게 반올림"""
        rounded = round(price / tick_size) * tick_size
        return round(rounded, price_decimals)
    
    def round_quantity(self, qty, qty_step, qty_decimals):
        """수량을 qtyStep에 맞게 반올림"""
        rounded = round(qty / qty_step) * qty_step
        return round(rounded, qty_decimals)
    
    def get_instrument_info(self, symbol):
        """심볼의 거래 규칙 정보 가져오기 (tickSize, minOrderQty 등)"""
        try:
            response = self.session.get_instruments_info(
                category='linear',
                symbol=symbol
            )
            if response['retCode'] == 0 and response['result']['list']:
                instrument = response['result']['list'][0]
                
                # 가격 필터 (tickSize)
                price_filter = instrument['priceFilter']
                tick_size = float(price_filter['tickSize'])
                min_price = float(price_filter['minPrice'])
                max_price = float(price_filter['maxPrice'])
                
                # 수량 필터
                lot_size_filter = instrument['lotSizeFilter']
                min_order_qty = float(lot_size_filter['minOrderQty'])
                max_order_qty = float(lot_size_filter['maxOrderQty'])
                qty_step = float(lot_size_filter['qtyStep'])
                
                return {
                    'symbol': symbol,
                    'tick_size': tick_size,
                    'min_price': min_price,
                    'max_price': max_price,
                    'min_order_qty': min_order_qty,
                    'max_order_qty': max_order_qty,
                    'qty_step': qty_step,
                    'price_decimals': len(str(tick_size).rstrip('0').split('.')[-1]) if '.' in str(tick_size) else 0,
                    'qty_decimals': len(str(qty_step).rstrip('0').split('.')[-1]) if '.' in str(qty_step) else 0
                }
            
            return None
            
        except Exception as e:
            print(f"심볼 정보 조회 오류 ({symbol}): {e}")
            return None
    
    def round_price_to_tick(self, price, tick_size):
        """가격을 tickSize에 맞게 반올림"""
        return round(price / tick_size) * tick_size
    
    def round_qty_to_step(self, qty, qty_step):
        """수량을 qtyStep에 맞게 반올림"""
        return round(qty / qty_step) * qty_step
