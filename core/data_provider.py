# ============================================================
# NEXUS PRO - Data Provider
# ============================================================
# Binance Futures WebSocket + REST API entegrasyonu
# Real-time veri akışı ve tarihsel veri
# ============================================================

import asyncio
import json
import logging
from typing import Dict, List, Callable, Optional
from dataclasses import dataclass
from datetime import datetime
import aiohttp
import pandas as pd

logger = logging.getLogger("nexus_pro.data")

@dataclass
class Candle:
    """Mum verisi"""
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    
    @property
    def datetime(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp / 1000)

class DataProvider:
    """
    Binance Futures veri sağlayıcı
    WebSocket ile gerçek zamanlı, REST ile tarihsel veri
    """
    
    BASE_URL = "https://fapi.binance.com"
    WS_URL = "wss://fstream.binance.com/stream"
    
    def __init__(self):
        self.candle_cache: Dict[str, Dict[str, pd.DataFrame]] = {}  # symbol -> timeframe -> df
        self.ticker_cache: Dict[str, Dict] = {}
        self.subscribers: List[Callable] = []
        self._running = False
        self._ws = None
        self._session: Optional[aiohttp.ClientSession] = None
        
    async def start(self, symbols: List[str], timeframes: List[str] = ["5m"]):
        """WebSocket bağlantısını başlat"""
        self._running = True
        self._session = aiohttp.ClientSession()
        
        # Tarihsel veriyi yükle
        await self._load_historical_data(symbols, timeframes)
        
        # WebSocket streams oluştur
        streams = []
        for symbol in symbols:
            sym = symbol.lower()
            for tf in timeframes:
                streams.append(f"{sym}@kline_{tf}")
            streams.append(f"{sym}@ticker")
        
        # WebSocket URL
        url = f"{self.WS_URL}?streams={'/'.join(streams[:200])}"  # Max 200 stream
        
        logger.info(f"📡 WebSocket bağlanıyor: {len(streams)} stream")
        
        try:
            async with self._session.ws_connect(url) as ws:
                self._ws = ws
                logger.info(f"✅ WebSocket Connected! Waiting for candles...")
                async for msg in ws:
                    if not self._running:
                        break
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        await self._process_message(json.loads(msg.data))
        except Exception as e:
            logger.error(f"WebSocket hatası: {e}")
            
    async def stop(self):
        """Bağlantıyı kapat"""
        self._running = False
        if self._ws:
            await self._ws.close()
        if self._session:
            await self._session.close()
            
    async def _load_historical_data(self, symbols: List[str], timeframes: List[str]):
        """Tarihsel veriyi yükle"""
        logger.info(f"📊 Tarihsel veri yükleniyor: {len(symbols)} sembol")
        
        for symbol in symbols:
            self.candle_cache[symbol] = {}
            for tf in timeframes:
                df = await self._fetch_klines(symbol, tf, limit=200)
                if df is not None:
                    self.candle_cache[symbol][tf] = df
                    
        logger.info("✅ Tarihsel veri yüklendi")
        
    async def _fetch_klines(self, symbol: str, interval: str, limit: int = 200) -> Optional[pd.DataFrame]:
        """REST API ile mum verisi çek"""
        url = f"{self.BASE_URL}/fapi/v1/klines"
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        
        try:
            async with self._session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    df = pd.DataFrame(data, columns=[
                        'timestamp', 'open', 'high', 'low', 'close', 'volume',
                        'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                        'taker_buy_quote', 'ignore'
                    ])
                    df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
                    for col in ['open', 'high', 'low', 'close', 'volume']:
                        df[col] = df[col].astype(float)
                    df['timestamp'] = df['timestamp'].astype(int)
                    return df
        except Exception as e:
            logger.error(f"Kline fetch hatası {symbol}: {e}")
        return None
        
    async def _process_message(self, data: dict):
        """WebSocket mesajını işle"""
        if 'stream' not in data:
            return
            
        stream = data['stream']
        payload = data['data']
        
        if '@kline_' in stream:
            await self._process_kline(payload)
        elif '@ticker' in stream:
            await self._process_ticker(payload)
            
    async def _process_kline(self, data: dict):
        """Mum verisini işle"""
        kline = data['k']
        symbol = data['s']
        interval = kline['i']
        is_closed = kline['x']
        
        candle = Candle(
            timestamp=kline['t'],
            open=float(kline['o']),
            high=float(kline['h']),
            low=float(kline['l']),
            close=float(kline['c']),
            volume=float(kline['v'])
        )
        
        # Cache güncelle
        if symbol in self.candle_cache and interval in self.candle_cache[symbol]:
            df = self.candle_cache[symbol][interval]
            if is_closed:
                # Yeni mum ekle
                new_row = pd.DataFrame([{
                    'timestamp': candle.timestamp,
                    'open': candle.open,
                    'high': candle.high,
                    'low': candle.low,
                    'close': candle.close,
                    'volume': candle.volume
                }])
                self.candle_cache[symbol][interval] = pd.concat([df, new_row]).tail(200)
                
                # Subscriber'lara bildir
                for callback in self.subscribers:
                    await callback(symbol, interval, candle)
                    
    async def _process_ticker(self, data: dict):
        """Ticker verisini işle"""
        symbol = data['s']
        self.ticker_cache[symbol] = {
            'price': float(data['c']),
            'price_change_pct': float(data['P']),
            'volume': float(data['v']),
            'high': float(data['h']),
            'low': float(data['l'])
        }
        
    def get_candles(self, symbol: str, timeframe: str = "5m") -> Optional[pd.DataFrame]:
        """Mum verisini al"""
        if symbol in self.candle_cache and timeframe in self.candle_cache[symbol]:
            return self.candle_cache[symbol][timeframe].copy()
        return None
    
    def get_klines(self, symbol: str, timeframe: str = "1h") -> Optional[pd.DataFrame]:
        """Alias for get_candles (for HMM compatibility)"""
        return self.get_candles(symbol, timeframe)
        
    def get_ticker(self, symbol: str) -> Optional[Dict]:
        """Ticker verisini al"""
        return self.ticker_cache.get(symbol)
        
    def subscribe(self, callback: Callable):
        """Mum kapanış event'lerine abone ol"""
        self.subscribers.append(callback)
        
    async def get_top_volatile_symbols(self, limit: int = 50) -> List[str]:
        """En volatil sembolleri getir"""
        url = f"{self.BASE_URL}/fapi/v1/ticker/24hr"
        
        try:
            async with self._session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # USDT paritelerini filtrele ve volatiliteye göre sırala
                    usdt_pairs = [
                        d for d in data 
                        if d['symbol'].endswith('USDT') 
                        and float(d['quoteVolume']) > 10000000  # Min 10M hacim
                    ]
                    sorted_pairs = sorted(
                        usdt_pairs, 
                        key=lambda x: abs(float(x['priceChangePercent'])), 
                        reverse=True
                    )
                    return [p['symbol'] for p in sorted_pairs[:limit]]
        except Exception as e:
            logger.error(f"Volatil sembol fetch hatası: {e}")
        return []
