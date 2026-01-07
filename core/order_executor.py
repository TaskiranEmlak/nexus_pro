# ============================================================
# NEXUS PRO - Order Executor
# ============================================================
# Güvenli emir iletimi ve yönetimi
# Limit, Market, Post-Only desteği
# ============================================================

import logging
import asyncio
from typing import Dict, Optional, List, Callable
from decimal import Decimal, ROUND_DOWN
import time

try:
    from binance import AsyncClient
    from binance.exceptions import BinanceAPIException, BinanceOrderException
    BINANCE_AVAILABLE = True
except ImportError:
    BINANCE_AVAILABLE = False
    AsyncClient = None
    BinanceAPIException = Exception
    BinanceOrderException = Exception

# Logger setup inside module explicitly if utils fails in future
logger = logging.getLogger("core_exec")

class OrderExecutor:
    """
    Emir İletim Motoru
    - Rate limit koruması
    - Hata yönetimi (Retry)
    - Post-Only desteği
    """
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.client: Optional[AsyncClient] = None
        self.active_orders = {} # Track orders locally
        
        # Simulation Check
        self.simulation_mode = not (self.api_key and self.api_secret)
        if self.simulation_mode:
            logger.warning("⚠️ No API Keys found. Running in SIMULATION MODE (Paper Trading).")

    async def connect(self):
        """Borsa bağlantısı"""
        if self.simulation_mode:
            logger.info("✅ Simulation Mode Active: Skipping Exchange Connection")
            return

        try:
            self.client = await AsyncClient.create(
                self.api_key, 
                self.api_secret, 
                testnet=self.testnet
            )
            logger.info("✅ OrderExecutor Connected to Exchange")
        except Exception as e:
            logger.error(f"❌ Connection Failed: {e}")
            raise

    async def disconnect(self):
        """Bağlantıyı kes"""
        if self.client:
            await self.client.close_connection()

    async def place_limit_order(
        self, 
        symbol: str, 
        side: str, 
        quantity: float, 
        price: float,
        reduce_only: bool = False,
        post_only: bool = True
    ) -> Optional[Dict]:
        """Limit emir gönder (veya simüle et)"""
        qty_str = f"{quantity:.3f}"
        price_str = f"{price:.2f}"
            
        if self.simulation_mode:
            # Simulate Order Placement
            order_id = int(time.time() * 1000)
            mock_order = {
                'orderId': order_id,
                'symbol': symbol,
                'status': 'NEW',
                'price': price_str,
                'origQty': qty_str,
                'side': side,
                'type': 'LIMIT',
                'timeInForce': 'GTX' if post_only else 'GTC'
            }
            logger.info(f"🧪 [SIMULATION] Limit Order: {side} {symbol} {qty_str} @ {price_str}")
            self.active_orders[order_id] = mock_order
            return mock_order

        if not self.client:
            logger.error("Client not connected!")
            return None
            
        try:
            time_in_force = "GTX" if post_only else "GTC"
            # logger.info(f"🚀 Placing Order: {side} {symbol} {qty_str} @ {price_str}")
            
            order = await self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type="LIMIT",
                timeInForce=time_in_force,
                quantity=qty_str,
                price=price_str,
                reduceOnly=reduce_only
            )
            
            self.active_orders[order['orderId']] = order
            return order
            
        except Exception as e:
            logger.error(f"❌ Limit Order Failed: {e}")
            return None

    async def place_maker_order_with_chase(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price_provider_callback: Callable,
        max_retries: int = 5,
        timeout: float = 2.0
    ):
        """
        Smart Limit Order (Chase Strategy)
        Maker olarak girmeye çalışır, dolmazsa fiyatı güncelleyip tekrar dener.
        """
        for i in range(max_retries):
            # 1. Güncel en iyi fiyatı al
            current_price = price_provider_callback(symbol, side)
            if not current_price:
                # Fiyat yoksa bekleme, sonraki denemeye geç
                await asyncio.sleep(0.5)
                continue
                
            # 2. Limit Emir Gönder (Post-Only)
            order = await self.place_limit_order(
                symbol, side, quantity, current_price, post_only=True
            )
            
            if not order:
                await asyncio.sleep(0.5)
                continue
                
            order_id = order['orderId']
                
            # 3. Bekle (Timeout)
            start_time = time.time()
            filled = False
            
            while time.time() - start_time < timeout:
                status = await self.get_order_status(symbol, order_id)
                
                if status == "FILLED":
                    filled = True
                    break
                elif status in ["CANCELED", "EXPIRED", "REJECTED"]:
                    break # Post-Only reject
                    
                await asyncio.sleep(0.5)
                
            if filled:
                logger.info(f"✅ Smart Order Filled: {symbol} @ {current_price}")
                return order
            else:
                # Dolmadı, iptal et ve yeni fiyatla dene
                logger.info(f"⏳ Chase Timeout ({i+1}/{max_retries}). Cancelling...")
                await self.cancel_order(symbol, order_id)
                await asyncio.sleep(0.2)
                
        # Son çare: Market Order
        logger.warning(f"⚠️ Chase failed after {max_retries} tries. Executing MARKET.")
        return await self.place_market_order(symbol, side, quantity)

    async def get_order_status(self, symbol: str, order_id: int):
        """Tekil emir durumu sorgula"""
        if self.simulation_mode: return "FILLED" # Simülasyonda her şey hemen dolar
        
        try:
             order = await self.client.futures_get_order(symbol=symbol, orderId=order_id)
             return order['status']
        except:
             return "UNKNOWN"

    async def place_market_order(self, symbol: str, side: str, quantity: float, reduce_only: bool = False):
        """Acil durumlar için Market emri"""
        if self.simulation_mode:
            logger.info(f"🧪 [SIMULATION] Market Order: {side} {symbol} {quantity}")
            return {'orderId': int(time.time()), 'status': 'FILLED'}

        try:
            order = await self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type="MARKET",
                quantity=f"{quantity:.3f}",
                reduceOnly=reduce_only
            )
            logger.info(f"🚨 Market Order Executed: {side} {symbol}")
            return order
        except Exception as e:
            logger.error(f"❌ Market Order Failed: {e}")
            return None

    async def cancel_order(self, symbol: str, order_id: int):
        """Emir iptal et"""
        if self.simulation_mode:
            self.active_orders.pop(order_id, None)
            return

        try:
            await self.client.futures_cancel_order(symbol=symbol, orderId=order_id)
            self.active_orders.pop(order_id, None)
        except Exception as e:
            logger.error(f"Cancel Failed: {e}")

    async def cancel_all_orders(self, symbol: str):
        """Tüm emirleri iptal et"""
        if self.simulation_mode:
            self.active_orders.clear()
            return

        try:
            await self.client.futures_cancel_all_open_orders(symbol=symbol)
            self.active_orders.clear() 
        except Exception as e:
            logger.error(f"Cancel All Failed: {e}")

    async def get_open_orders(self, symbol: str):
        """Açık emirleri çek"""
        if self.simulation_mode:
            return list(self.active_orders.values())

        try:
            return await self.client.futures_get_open_orders(symbol=symbol)
        except Exception as e:
            logger.error(f"Get Orders Failed: {e}")
            return []

    async def get_balance(self, asset: str = "USDT") -> float:
        """Toplam bakiyeyi çek"""
        if self.simulation_mode:
            logger.debug("🧪 [SIMULATION] Returning mock balance: 1000 USDT")
            return 1000.0  # Simülasyon için varsayılan
        
        if not self.client:
            logger.error("Client not connected!")
            return 0.0
        
        try:
            account_info = await self.client.futures_account_balance()
            for item in account_info:
                if item["asset"] == asset:
                    return float(item["balance"])
            return 0.0
        except Exception as e:
            logger.error(f"Get Balance Failed: {e}")
            return 0.0

    async def get_available_balance(self, asset: str = "USDT") -> float:
        """Kullanılabilir bakiyeyi çek (Mevcut olmayan marjin hariç)"""
        if self.simulation_mode:
            return 1000.0
        
        if not self.client:
            logger.error("Client not connected!")
            return 0.0
        
        try:
            account_info = await self.client.futures_account_balance()
            for item in account_info:
                if item["asset"] == asset:
                    return float(item["withdrawAvailable"])
            return 0.0
        except Exception as e:
            logger.error(f"Get Available Balance Failed: {e}")
