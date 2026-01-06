# ============================================================
# NEXUS PRO - Microstructure Analysis
# ============================================================
# Order Book ve Trade verilerinden mikro-yapı sinyalleri üretir.
# HFT Sinyalleri: OFI, Spread, Depth Imbalance
# ============================================================

from typing import Dict, Tuple

class MicrostructureAnalyzer:
    """
    Piyasa Mikro-Yapısı Analizörü
    """
    
    @staticmethod
    def calculate_ofi(orderbook: Dict, depth: int = 5) -> float:
        """
        OFI (Order Flow Imbalance) Hesapla
        
        Formül: (Bid_Vol - Ask_Vol) / (Bid_Vol + Ask_Vol)
        Değer Aralığı: -1.0 (Tam Satıcı) ile +1.0 (Tam Alıcı)
        """
        if not orderbook or 'bids' not in orderbook or 'asks' not in orderbook:
            return 0.0
            
        bids = orderbook['bids']
        asks = orderbook['asks']
        
        if not bids or not asks:
            return 0.0
            
        # İlk 'depth' kademesindeki hacimlerin toplamı
        bid_vol = sum([b[1] for b in bids[:depth]])
        ask_vol = sum([a[1] for a in asks[:depth]])
        
        total_vol = bid_vol + ask_vol
        
        if total_vol == 0:
            return 0.0
            
        imbalance = (bid_vol - ask_vol) / total_vol
        return imbalance
        
    @staticmethod
    def calculate_spread(orderbook: Dict) -> float:
        """Spread (Alış-Satış Makası) Hesapla"""
        if not orderbook or not orderbook['bids'] or not orderbook['asks']:
            return 0.0
            
        best_bid = orderbook['bids'][0][0]
        best_ask = orderbook['asks'][0][0]
        
        return (best_ask - best_bid) / best_bid * 100 # Yüzdelik
        
    @staticmethod
    def calculate_vwap(trades: list) -> float:
        """
        VWAP (Volume Weighted Average Price) Hesapla
        trades: [(price, volume, timestamp), ...]
        """
        if not trades:
            return 0.0
            
        total_volume = sum(t[1] for t in trades)
        if total_volume == 0:
            return 0.0
            
        vwap = sum(t[0] * t[1] for t in trades) / total_volume
        return vwap
        
    @staticmethod
    def get_signal_strength(ofi: float, current_price: float, vwap: float) -> dict:
        """
        OFI + VWAP Kombine Sinyal Gücü
        
        Returns:
            {
                'direction': 'BUY' | 'SELL' | 'NEUTRAL',
                'strength': 0.0 - 1.0,
                'reason': str
            }
        """
        result = {'direction': 'NEUTRAL', 'strength': 0.0, 'reason': ''}
        
        # OFI Threshold
        ofi_threshold = 0.3
        
        # VWAP Position
        price_vs_vwap = (current_price - vwap) / vwap * 100 if vwap > 0 else 0
        
        # Combined Logic
        if ofi > ofi_threshold and price_vs_vwap > 0:
            # Alıcılar baskın VE fiyat VWAP üstünde = GÜÇLÜ AL
            result['direction'] = 'BUY'
            result['strength'] = min(abs(ofi), 1.0)
            result['reason'] = f'OFI Bullish ({ofi:.2f}) + Price > VWAP'
            
        elif ofi < -ofi_threshold and price_vs_vwap < 0:
            # Satıcılar baskın VE fiyat VWAP altında = GÜÇLÜ SAT
            result['direction'] = 'SELL'
            result['strength'] = min(abs(ofi), 1.0)
            result['reason'] = f'OFI Bearish ({ofi:.2f}) + Price < VWAP'
            
        elif abs(ofi) > ofi_threshold:
            # Sadece OFI sinyali (zayıf)
            result['direction'] = 'BUY' if ofi > 0 else 'SELL'
            result['strength'] = min(abs(ofi), 1.0) * 0.5  # Yarı güç
            result['reason'] = f'OFI Only ({ofi:.2f}), VWAP conflict'
            
        return result
