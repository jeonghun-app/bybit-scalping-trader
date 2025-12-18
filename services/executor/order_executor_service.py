"""
Order Executor Service - 실제 주문 실행
5초마다 DynamoDB trading-positions 스캔하여 진입 조건 확인 및 주문 실행
"""
import os
import time
import boto3
from datetime import datetime, timezone
from decimal import Decimal
from pybit.unified_trading import HTTP

class OrderExecutorService:
    def __init__(self):
        # Bybit 클라이언트
        self.session = HTTP(
            testnet=os.getenv('BYBIT_TESTNET', 'False') == 'True',
            api_key=os.getenv('BYBIT_API_KEY'),
            api_secret=os.getenv('BYBIT_API_SECRET')
        )
        
        # DynamoDB
        self.dynamodb = boto3.resource('dynamodb', region_name=os.getenv('AWS_REGION', 'ap-northeast-2'))
        self.positions_table = self.dynamodb.Table(os.getenv('DYNAMODB_POSITIONS_TABLE', 'crypto-trading-positions'))
        
        self.executor_id = os.getenv('HOSTNAME', 'executor-1')
        
        # 설정
        self.position_size = float(os.getenv('POSITION_SIZE', '100.0'))  # $100 고정
        self.leverage = int(os.getenv('LEVERAGE', '10'))  # 10x 레버리지
        self.scan_interval = int(os.getenv('SCAN_INTERVAL', '5'))  # 5초
        
        # 진입 조건
        self.entry_conditions = {
            'price_tolerance': 0.005,  # 0.5% 이내 (진입가 대비) - 0.2%에서 완화
            'min_confidence': 60,      # 최소 신뢰도 60점 (기본 전략 허용)
            'check_volume': True,      # 거래량 확인
            'check_spread': True       # 스프레드 확인 (0.1% 이내)
        }
    
    def get_account_balance(self):
        """계정 잔고 조회 (사용 가능한 USDT)"""
        try:
            result = self.session.get_wallet_balance(accountType="UNIFIED")
            
            if result['retCode'] == 0:
                account = result['result']['list'][0]
                
                # 총 사용 가능 잔고 사용 (USDT 기준)
                total_available = float(account.get('totalAvailableBalance') or 0)
                total_equity = float(account.get('totalEquity') or 0)
                total_wallet = float(account.get('totalWalletBalance') or 0)
                
                print(f"💰 계정 잔고:")
                print(f"  - 총 자산: ${total_equity:.2f}")
                print(f"  - 지갑 잔고: ${total_wallet:.2f}")
                print(f"  - 사용 가능: ${total_available:.2f}")
                
                return total_available
            
            print(f"⚠️  잔고 조회 응답: {result}")
            return 0.0
            
        except Exception as e:
            print(f"❌ 잔고 조회 실패: {e}")
            import traceback
            traceback.print_exc()
            return 0.0
    
    def get_open_positions(self):
        """현재 오픈된 포지션 조회"""
        try:
            result = self.session.get_positions(
                category="linear",
                settleCoin="USDT"
            )
            
            if result['retCode'] == 0:
                positions = result['result']['list']
                # 실제 포지션만 필터링 (size > 0)
                open_positions = [p for p in positions if float(p['size']) > 0]
                
                if open_positions:
                    print(f"\n📊 현재 오픈 포지션: {len(open_positions)}개")
                    for pos in open_positions:
                        print(f"  - {pos['symbol']}: {pos['side']} {pos['size']} (진입가: ${float(pos['avgPrice']):.2f})")
                
                return open_positions
            
            return []
            
        except Exception as e:
            print(f"❌ 포지션 조회 실패: {e}")
            return []
    
    def get_active_positions_from_db(self):
        """DynamoDB에서 활성 포지션 조회"""
        try:
            response = self.positions_table.query(
                IndexName='StatusIndex',
                KeyConditionExpression='#status = :status',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={':status': 'active'},
                ScanIndexForward=False
            )
            
            items = response.get('Items', [])
            
            # Decimal을 float로 변환
            positions = []
            for item in items:
                position = {k: float(v) if isinstance(v, Decimal) else v for k, v in item.items()}
                positions.append(position)
            
            return positions
            
        except Exception as e:
            print(f"❌ DynamoDB 조회 실패: {e}")
            return []
    
    def get_current_price(self, symbol):
        """현재 시장 가격 조회"""
        try:
            result = self.session.get_tickers(category="linear", symbol=symbol)
            
            if result['retCode'] == 0 and result['result']['list']:
                ticker = result['result']['list'][0]
                return {
                    'last_price': float(ticker['lastPrice']),
                    'bid_price': float(ticker['bid1Price']),
                    'ask_price': float(ticker['ask1Price']),
                    'volume_24h': float(ticker['volume24h']),
                    'turnover_24h': float(ticker['turnover24h'])
                }
            
            return None
            
        except Exception as e:
            print(f"❌ 가격 조회 실패 ({symbol}): {e}")
            return None
    
    def check_entry_conditions(self, position, current_price_data):
        """진입 조건 확인"""
        entry_price = position['entry_price']
        current_price = current_price_data['last_price']
        bid_price = current_price_data['bid_price']
        ask_price = current_price_data['ask_price']
        
        # 1. 신뢰도 확인
        if position['confidence'] < self.entry_conditions['min_confidence']:
            return False, f"신뢰도 부족 ({position['confidence']}점 < {self.entry_conditions['min_confidence']}점)"
        
        # 2. 가격 범위 확인 (진입가 ±0.2% 이내)
        price_diff_pct = abs(current_price - entry_price) / entry_price
        if price_diff_pct > self.entry_conditions['price_tolerance']:
            return False, f"가격 범위 초과 ({price_diff_pct*100:.2f}% > {self.entry_conditions['price_tolerance']*100:.2f}%)"
        
        # 3. 스프레드 확인 (0.1% 이내)
        if self.entry_conditions['check_spread']:
            spread_pct = (ask_price - bid_price) / bid_price
            if spread_pct > 0.001:  # 0.1%
                return False, f"스프레드 과다 ({spread_pct*100:.3f}%)"
        
        # 4. 포지션 타입별 가격 확인
        if position['position_type'] == 'LONG':
            # 롱: 현재가가 진입가보다 낮거나 비슷할 때 진입
            if current_price > entry_price * 1.002:  # 0.2% 이상 높으면 대기
                return False, f"롱 진입 대기 (현재가 ${current_price:.2f} > 진입가 ${entry_price:.2f})"
        else:  # SHORT
            # 숏: 현재가가 진입가보다 높거나 비슷할 때 진입
            if current_price < entry_price * 0.998:  # 0.2% 이상 낮으면 대기
                return False, f"숏 진입 대기 (현재가 ${current_price:.2f} < 진입가 ${entry_price:.2f})"
        
        # 5. 거래량 확인 (최소 거래량)
        if self.entry_conditions['check_volume']:
            if current_price_data['volume_24h'] < 1000:  # 최소 거래량
                return False, f"거래량 부족 ({current_price_data['volume_24h']:.0f})"
        
        return True, "진입 조건 충족"
    
    def calculate_order_qty(self, symbol, entry_price, position_size, leverage):
        """주문 수량 계산 (정확한 계산)"""
        try:
            # 심볼 정보 조회 (최소 주문 수량, 수량 단위 등)
            result = self.session.get_instruments_info(category="linear", symbol=symbol)
            
            if result['retCode'] != 0 or not result['result']['list']:
                print(f"❌ 심볼 정보 조회 실패: {symbol}")
                return None
            
            instrument = result['result']['list'][0]
            
            # 최소/최대 주문 수량
            min_order_qty = float(instrument['lotSizeFilter']['minOrderQty'])
            max_order_qty = float(instrument['lotSizeFilter']['maxOrderQty'])
            qty_step = float(instrument['lotSizeFilter']['qtyStep'])
            
            # 수량 계산: (포지션 크기 × 레버리지) / 진입가
            # 예: ($100 × 10x) / $86,623 = 0.0115 BTC
            raw_qty = (position_size * leverage) / entry_price
            
            # qty_step에 맞춰 반올림
            # 예: qty_step = 0.001이면 0.0115 → 0.011
            qty = round(raw_qty / qty_step) * qty_step
            
            # 최소/최대 범위 확인
            if qty < min_order_qty:
                print(f"⚠️  계산된 수량({qty})이 최소 주문 수량({min_order_qty})보다 작음")
                qty = min_order_qty
            
            if qty > max_order_qty:
                print(f"⚠️  계산된 수량({qty})이 최대 주문 수량({max_order_qty})보다 큼")
                qty = max_order_qty
            
            # 소수점 자릿수 맞추기
            decimals = len(str(qty_step).split('.')[-1]) if '.' in str(qty_step) else 0
            qty = round(qty, decimals)
            
            print(f"📊 수량 계산:")
            print(f"  - 포지션 크기: ${position_size}")
            print(f"  - 레버리지: {leverage}x")
            print(f"  - 진입가: ${entry_price:.2f}")
            print(f"  - 계산된 수량: {qty}")
            print(f"  - 최소/최대: {min_order_qty} / {max_order_qty}")
            print(f"  - 수량 단위: {qty_step}")
            
            return qty
            
        except Exception as e:
            print(f"❌ 수량 계산 실패: {e}")
            return None
    
    def place_order(self, position, current_price):
        """주문 실행"""
        symbol = position['symbol']
        position_type = position['position_type']
        entry_price = position['entry_price']
        stop_loss = position['stop_loss']
        take_profit = position['take_profit']
        
        print(f"\n{'='*80}")
        print(f"📤 주문 실행: {symbol} ({position_type})")
        print(f"{'='*80}\n")
        
        try:
            # 1. 레버리지 설정
            print(f"[1/3] 레버리지 설정 ({self.leverage}x)...")
            try:
                leverage_result = self.session.set_leverage(
                    category="linear",
                    symbol=symbol,
                    buyLeverage=str(self.leverage),
                    sellLeverage=str(self.leverage)
                )
                
                if leverage_result['retCode'] != 0:
                    print(f"⚠️  레버리지 설정 실패 (이미 설정되어 있을 수 있음)")
                else:
                    print(f"✅ 레버리지 설정 완료")
            except Exception as lev_error:
                # 레버리지가 이미 설정되어 있으면 에러 무시
                if "110043" in str(lev_error) or "leverage not modified" in str(lev_error):
                    print(f"✅ 레버리지 이미 {self.leverage}x로 설정됨")
                else:
                    print(f"⚠️  레버리지 설정 오류: {lev_error}")
                    # 레버리지 설정 실패해도 계속 진행
            
            # 2. 주문 수량 계산
            print(f"[2/3] 주문 수량 계산...")
            qty = self.calculate_order_qty(symbol, entry_price, self.position_size, self.leverage)
            
            if not qty:
                return None
            
            # 3. 주문 실행 (Market Order + TP/SL)
            print(f"[3/3] 주문 실행...")
            
            side = "Buy" if position_type == "LONG" else "Sell"
            
            order_result = self.session.place_order(
                category="linear",
                symbol=symbol,
                side=side,
                orderType="Market",
                qty=str(qty),
                stopLoss=str(stop_loss),
                takeProfit=str(take_profit),
                positionIdx=0  # One-way mode
            )
            
            if order_result['retCode'] == 0:
                order_id = order_result['result']['orderId']
                
                print(f"\n✅ 주문 실행 성공!")
                print(f"  - Order ID: {order_id}")
                print(f"  - 심볼: {symbol}")
                print(f"  - 타입: {position_type}")
                print(f"  - 수량: {qty}")
                print(f"  - 진입가: ${entry_price:.2f} (예상)")
                print(f"  - 손절가: ${stop_loss:.2f}")
                print(f"  - 익절가: ${take_profit:.2f}")
                print(f"  - 포지션 크기: ${self.position_size}")
                print(f"  - 레버리지: {self.leverage}x\n")
                
                return {
                    'order_id': order_id,
                    'symbol': symbol,
                    'side': side,
                    'qty': qty,
                    'entry_price': current_price,  # 실제 체결가는 나중에 확인
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            else:
                print(f"❌ 주문 실행 실패: {order_result['retMsg']}")
                return None
                
        except Exception as e:
            print(f"❌ 주문 실행 오류: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def update_position_status(self, position, status, order_info=None):
        """DynamoDB 포지션 상태 업데이트"""
        try:
            update_expr = "SET #status = :status, updated_at = :updated"
            expr_values = {
                ':status': status,
                ':updated': datetime.now(timezone.utc).isoformat()
            }
            expr_names = {'#status': 'status'}
            
            # 주문 정보 추가
            if order_info:
                update_expr += ", order_id = :order_id, executed_at = :executed, executed_price = :exec_price"
                expr_values.update({
                    ':order_id': order_info['order_id'],
                    ':executed': order_info['timestamp'],
                    ':exec_price': Decimal(str(order_info['entry_price']))
                })
            
            self.positions_table.update_item(
                Key={
                    'symbol': position['symbol'],
                    'signal_timestamp': position['signal_timestamp']
                },
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values
            )
            
            print(f"✅ DynamoDB 상태 업데이트: {position['symbol']} → {status}")
            return True
            
        except Exception as e:
            print(f"❌ DynamoDB 업데이트 실패: {e}")
            return False
    
    def process_position(self, position):
        """포지션 처리"""
        symbol = position['symbol']
        
        # 심볼 정보 조회 (소수점 자릿수 확인)
        try:
            instrument_result = self.session.get_instruments_info(category="linear", symbol=symbol)
            if instrument_result['retCode'] == 0:
                instrument = instrument_result['result']['list'][0]
                tick_size = float(instrument['priceFilter']['tickSize'])
                if tick_size < 1:
                    price_decimals = len(f"{tick_size:.10f}".rstrip('0').split('.')[-1])
                else:
                    price_decimals = 0
            else:
                price_decimals = 2  # 기본값
        except:
            price_decimals = 2  # 기본값
        
        print(f"\n{'='*80}")
        print(f"🔍 포지션 확인: {symbol}")
        print(f"{'='*80}")
        print(f"  - 진입가: ${position['entry_price']:.{price_decimals}f}")
        print(f"  - 타입: {position['position_type']}")
        print(f"  - 신뢰도: {position['confidence']}점")
        print(f"  - 상태: {position['status']}")
        
        # 1. 현재 가격 조회
        current_price_data = self.get_current_price(symbol)
        
        if not current_price_data:
            print(f"⚠️  가격 조회 실패 - 스킵")
            return
        
        current_price = current_price_data['last_price']
        print(f"  - 현재가: ${current_price:.{price_decimals}f}")
        
        # 2. 진입 조건 확인
        can_enter, reason = self.check_entry_conditions(position, current_price_data)
        
        if not can_enter:
            print(f"⏳ 진입 대기: {reason}")
            return
        
        print(f"✅ 진입 조건 충족: {reason}")
        
        # 3. 잔고 및 마진 확인
        balance = self.get_account_balance()
        open_positions = self.get_open_positions()
        
        # 사용 중인 마진 계산
        used_margin = 0.0
        for pos in open_positions:
            pos_size = float(pos['size'])
            pos_price = float(pos['avgPrice'])
            pos_leverage = float(pos['leverage'])
            used_margin += (pos_size * pos_price) / pos_leverage
        
        # 사용 가능한 마진
        available_margin = balance - used_margin
        required_margin = self.position_size / self.leverage
        
        print(f"  - 사용 가능 마진: ${available_margin:.2f}")
        print(f"  - 필요 마진: ${required_margin:.2f}")
        print(f"  - 오픈 포지션: {len(open_positions)}개")
        
        if available_margin < required_margin:
            print(f"⚠️  마진 부족 (${available_margin:.2f} < ${required_margin:.2f}) - 대기")
            return
        
        # 4. 주문 실행
        order_info = self.place_order(position, current_price)
        
        if order_info:
            # 5. 상태 업데이트 (active → executing)
            self.update_position_status(position, 'executing', order_info)
        else:
            print(f"❌ 주문 실행 실패")
    
    def run_once(self):
        """1회 실행"""
        print(f"\n{'='*80}")
        print(f"🔄 Order Executor 스캔 시작 - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
        print(f"{'='*80}\n")
        
        # 1. 활성 포지션 조회
        positions = self.get_active_positions_from_db()
        
        if not positions:
            print("⚠️  활성 포지션 없음")
            return
        
        print(f"✅ {len(positions)}개 활성 포지션 발견\n")
        
        # 2. 각 포지션 처리
        for position in positions:
            try:
                self.process_position(position)
            except Exception as e:
                print(f"❌ 포지션 처리 오류 ({position['symbol']}): {e}")
                import traceback
                traceback.print_exc()
        
        print(f"\n{'='*80}")
        print(f"✅ 스캔 완료")
        print(f"{'='*80}\n")
    
    def run(self):
        """메인 실행 로직 (무한 루프)"""
        print(f"\n{'='*80}")
        print(f"🚀 Order Executor Service 시작")
        print(f"{'='*80}")
        print(f"Executor ID: {self.executor_id}")
        print(f"포지션 크기: ${self.position_size}")
        print(f"레버리지: {self.leverage}x")
        print(f"스캔 주기: {self.scan_interval}초")
        print(f"진입 조건:")
        print(f"  - 가격 허용 범위: ±{self.entry_conditions['price_tolerance']*100:.2f}%")
        print(f"  - 최소 신뢰도: {self.entry_conditions['min_confidence']}점")
        print(f"  - 스프레드 확인: {self.entry_conditions['check_spread']}")
        print(f"  - 거래량 확인: {self.entry_conditions['check_volume']}")
        print(f"{'='*80}\n")
        
        try:
            while True:
                self.run_once()
                time.sleep(self.scan_interval)
                
        except KeyboardInterrupt:
            print(f"\n\n{'='*80}")
            print(f"⏹️  Order Executor Service 종료")
            print(f"{'='*80}\n")

if __name__ == "__main__":
    service = OrderExecutorService()
    service.run()
