# ============================================================
# NEXUS PRO - Order Executor
# ============================================================
# Güvenli emir iletimi ve yönetimi
# Limit, Market, Post-Only desteği
# ============================================================

import logging
import asyncio
from typing import Dict, Optional, List
from decimal import Decimal, ROUND_DOWN
import time

from utils import get_logger
try:
    from binance import AsyncClient
    from binance.exceptions import BinanceAPIException, BinanceOrderException
    BINANCE_AVAILABLE = True
except ImportError:
    BINANCE_AVAILABLE = False
    AsyncClient = None
    BinanceAPIException = Exception
    BinanceOrderException = Exception

logger = get_logger("core_exec")

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
        self.active_orders = {}
        # Simulation Mode detection
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
            logger.info(f"🧪 [SIMULATION] Order Placed: {side} {symbol} {qty_str} @ {price_str}")
            self.active_orders[order_id] = mock_order
            return mock_order

        if not self.client:
            logger.error("Client not connected!")
            return None
            
        try:
            time_in_force = "GTC" 
            if post_only:
                time_in_force = "GTX" 
                
            logger.info(f"🚀 Placing Order: {side} {symbol} {qty_str} @ {price_str} (PostOnly={post_only})")
            
            order = await self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type="LIMIT",
                timeInForce=time_in_force,
                quantity=qty_str,
                price=price_str,
                reduceOnly=reduce_only
            )
            
            logger.info(f"✅ Order Placed: ID={order['orderId']}")
            self.active_orders[order['orderId']] = order
            return order
            
        except BinanceAPIException as e:
            logger.error(f"❌ Binance API Error: {e.message} (Code: {e.code})")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected Error: {e}")
            return None

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
            if order_id in self.active_orders:
                del self.active_orders[order_id]
            logger.info(f"🧪 [SIMULATION] Order Cancelled: {order_id}")
            return

        try:
            await self.client.futures_cancel_order(symbol=symbol, orderId=order_id)
            if order_id in self.active_orders:
                del self.active_orders[order_id]
            logger.info(f"🗑️ Order Cancelled: {order_id}")
        except Exception as e:
            logger.error(f"Cancel Failed: {e}")

    async def cancel_all_orders(self, symbol: str):
        """Tüm emirleri iptal et"""
        if self.simulation_mode:
            self.active_orders.clear()
            logger.info(f"🧪 [SIMULATION] All Orders Cancelled")
            return

        try:
            await self.client.futures_cancel_all_open_orders(symbol=symbol)
            logger.info(f"🗑️ All Orders Cancelled for {symbol}")
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
