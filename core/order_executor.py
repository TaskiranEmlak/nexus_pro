# ============================================================
# NEXUS PRO - Order Executor
# ============================================================
# Güvenli emir iletimi ve yönetimi
# Limit, Market, Post-Only desteği
# ============================================================

import logging
import asyncio
from typing import Dict, Optional, List, Callable
# ... imports ...

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
                logger.warning(f"Fiyat alınamadı {symbol}, deneme {i+1}")
                await asyncio.sleep(0.5)
                continue
                
            # 2. Limit Emir Gönder (Post-Only)
            order = await self.place_limit_order(
                symbol, side, quantity, current_price, post_only=True
            )
            
            if not order:
                logger.warning(f"Emir gönderilemedi {symbol}, tekrar deneniyor...")
                await asyncio.sleep(0.5)
                continue
                
            order_id = order['orderId']
                
            # 3. Bekle (Timeout)
            start_time = time.time()
            filled = False
            
            while time.time() - start_time < timeout:
                # Emrin durumunu kontrol et
                if self.simulation_mode:
                    filled = True # Simülasyonda hemen doldu varsay
                    break
                    
                status = await self.get_order_status(symbol, order_id)
                if status == "FILLED":
                    filled = True
                    break
                elif status == "CANCELED" or status == "EXPIRED":
                    break # Post-Only reject yedi, muhtemelen fiyat kaçtı
                    
                await asyncio.sleep(0.5)
                
            if filled:
                logger.info(f"✅ Smart Order Filled: {symbol} @ {current_price}")
                return order
            else:
                # Dolmadı, iptal et ve yeni fiyatla dene
                logger.info(f"⏳ Order Timeout ({i+1}/{max_retries}). Chasing price...")
                await self.cancel_order(symbol, order_id)
                await asyncio.sleep(0.2) # Rate limit koruma
                
        # Son çare: Market Order (veya iptal)
        logger.warning(f"⚠️ Chase failed after {max_retries} tries. Executing MARKET.")
        return await self.place_market_order(symbol, side, quantity)

    async def get_order_status(self, symbol: str, order_id: int):
        """Tekil emir durumu sorgula"""
        if self.simulation_mode: return "FILLED"
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
