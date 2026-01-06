# ============================================================
# NEXUS PRO - Stream Manager (L2 Data)
# ============================================================
# Order Book (Derinlik) ve Trade (İşlem) verilerini
# WebSocket üzerinden gerçek zamanlı (L2) çeker.
# ============================================================

import asyncio
import logging
import ccxt.pro as ccxt  # CCXT Pro (Async + WS)
from typing import Dict, List, Callable, Optional
from datetime import datetime

logger = logging.getLogger("nexus_pro.stream")

class StreamManager:
    """
    WebSocket Stream Yöneticisi
    HFT için kritik olan L2 Order Book ve Trade Stream verilerini sağlar.
    """
    
    def __init__(self, symbols: List[str]):
        self.symbols = symbols
        self.orderbooks = {} # {symbol: {'bids': [], 'asks': [], 'timestamp': 0}}
        self.active = False
        self.exchange = None
        self.callbacks = [] # Veri geldiğinde tetiklenecek fonksiyonlar
        
    async def start(self):
        """Stream'i başlat"""
        self.active = True
        logger.info("📡 L2 Stream Manager Başlatılıyor (Order Book & Trades)...")
        
        # Binance Futures
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })
        
        # Her sembol için ayrı task yerine, ccxt.pro'nun watch_multiple özelliklerini kullanmak daha iyi
        # Ancak basitlik için loop döngüsü kuralım
        asyncio.create_task(self._watch_market_loop())
        
    async def stop(self):
        """Stream'i durdur"""
        self.active = False
        if self.exchange:
            await self.exchange.close()
        logger.info("🛑 L2 Stream Manager Durduruldu.")
        
    def add_callback(self, callback: Callable):
        """Veri güncellendiğinde çağrılacak fonksiyon ekle"""
        self.callbacks.append(callback)
        
    async def _watch_market_loop(self):
        """Ana döngü: Tüm sembolleri izle"""
        # Not: CCXT Pro ile watch_order_book genellikle tek sembol için blocking'dir.
        # Çoklu sembol için asyncio.gather kullanılır.
        
        tasks = [self._watch_symbol(symbol) for symbol in self.symbols]
        await asyncio.gather(*tasks)
            
    async def _watch_symbol(self, symbol: str):
        """Tek bir sembolü izle"""
        while self.active:
            try:
                # 1. Order Book (Limit: 5 derinlik yeterli HFT sinyali için - daha hızlı)
                # watch_order_book blocking'dir, veri gelince açılır
                orderbook = await self.exchange.watch_order_book(symbol, limit=5)
                
                # Veriyi işle
                self.orderbooks[symbol] = {
                    'bids': orderbook['bids'], # [[price, qty], ...]
                    'asks': orderbook['asks'],
                    'timestamp': self.exchange.milliseconds()
                }
                
                # 2. Opsiyonel: Trade Stream de izlenebilir (watch_trades)
                # Ancak loop içinde ardışık beklemek gecikme yaratır.
                # İdealde gather ile paralel bağlanmalı.
                
                # Sinyalcilere haber ver
                for callback in self.callbacks:
                    await callback(symbol, "ORDER_BOOK", self.orderbooks[symbol])
                    
            except Exception as e:
                # logger.error(f"Stream Error {symbol}: {e}")
                await asyncio.sleep(5) # Hata durumunda bekle

    def get_best_price(self, symbol: str, side: str) -> Optional[float]:
        """
        HFT Chase için güncel en iyi fiyatı (Maker) döndürür.
        BUY -> Best Bid
        SELL -> Best Ask
        """
        if symbol not in self.orderbooks:
            return None
        
        ob = self.orderbooks[symbol]
        # Check basic integrity
        if not ob or 'bids' not in ob or 'asks' not in ob:
            return None
            
        try:
            if not ob['bids'] or not ob['asks']:
                return None
                
            if side == 'BUY':
                return float(ob['bids'][0][0])
            elif side == 'SELL':
                return float(ob['asks'][0][0])
        except Exception:
            return None
        return None
