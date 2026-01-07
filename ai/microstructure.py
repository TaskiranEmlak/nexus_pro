# ============================================================
# NEXUS PRO - Microstructure Analysis (True OFI)
# ============================================================
# Order Book değişimlerini (Flow) analiz eder.
# HFT Sinyalleri: True OFI, Z-Score, VWAP Delta
# ============================================================

from typing import Dict, List
import numpy as np

class MicrostructureAnalyzer:
    """
    Mikro yapı analizörü: Order Book & Trade verilerini işler
    
    Özellikler:
    - True OFI (Order Flow Imbalance) Hesaplama (Stateful)
    - Z-Score bazlı Dinamik Eşik
    - VWAP Analizi
    """
    
    def __init__(self):
        # State for True OFI Calculation
        self.prev_best_bid = None
        self.prev_best_ask = None
        self.prev_bid_vol = 0.0
        self.prev_ask_vol = 0.0
        
        # OFI History for Z-Score
        self.ofi_history = []
        self.max_history = 100

    def reset(self):
        """
        WebSocket yeniden bağlantısında veya sembol değişikliğinde state sıfırla.
        Bu, yeniden bağlantı sonrası yanlış OFI spike'larını önler.
        """
        self.prev_best_bid = None
        self.prev_best_ask = None
        self.prev_bid_vol = 0.0
        self.prev_ask_vol = 0.0
        self.ofi_history.clear()

    def calculate_ofi(self, orderbook: Dict) -> float:
        """
        TRUE OFI (Order Flow Imbalance) Hesapla
        Formül: Cont et al. (Limit Order Book değişimlerine göre)
        
        Args:
            orderbook: {'bids': [[price, vol], ...], 'asks': ...}
            
        Returns:
            OFI Value (Ham akış değeri, normalize edilmemiş)
        """
        try:
            # L2 verisi kontrolü
            if not orderbook.get('bids') or not orderbook.get('asks'):
                return 0.0

            # En iyi fiyatlar ve hacimler (Level 1)
            best_bid = float(orderbook['bids'][0][0])
            bid_vol = float(orderbook['bids'][0][1])
            best_ask = float(orderbook['asks'][0][0])
            ask_vol = float(orderbook['asks'][0][1])

            # İlk veri mi?
            if self.prev_best_bid is None:
                self._update_prev(best_bid, bid_vol, best_ask, ask_vol)
                return 0.0
                
            # --- OFI Logic (Cont et al.) ---
            
            # 1. Bid Tarafındaki Değişim (e_n)
            e_n = 0.0
            if best_bid > self.prev_best_bid:
                e_n = bid_vol # Fiyat arttı -> Agresif Alıcı
            elif best_bid == self.prev_best_bid:
                e_n = bid_vol - self.prev_bid_vol # Hacim değişimi
            else:
                e_n = -self.prev_bid_vol # Fiyat düştü -> Alıcı geri çekildi
                
            # 2. Ask Tarafındaki Değişim (e_m)
            e_m = 0.0
            if best_ask < self.prev_best_ask:
                e_m = ask_vol # Fiyat düştü -> Agresif Satıcı
            elif best_ask == self.prev_best_ask:
                e_m = ask_vol - self.prev_ask_vol # Hacim değişimi
            else:
                e_m = -self.prev_ask_vol # Fiyat yükseldi -> Satıcı geri çekildi
            
            # True OFI
            ofi = e_n - e_m
            
            # State Update
            self._update_prev(best_bid, bid_vol, best_ask, ask_vol)
            
            # History Update (Z-Score için)
            self.ofi_history.append(ofi)
            if len(self.ofi_history) > self.max_history:
                self.ofi_history.pop(0)

            return ofi

        except Exception as e:
            # Hata durumunda akışı bozma
            return 0.0

    def _update_prev(self, bb, bv, ba, av):
        """Önceki durumları güncelle"""
        self.prev_best_bid, self.prev_bid_vol = bb, bv
        self.prev_best_ask, self.prev_ask_vol = ba, av

    def get_z_score_ofi(self, current_ofi: float) -> float:
        """OFI Z-Score hesapla (Dinamik Eşik için)"""
        if len(self.ofi_history) < 20:
            return 0.0
        
        mean = np.mean(self.ofi_history)
        std = np.std(self.ofi_history)
        
        if std == 0: return 0.0
        
        return (current_ofi - mean) / std

    def get_signal_strength(self, ofi: float, price: float, vwap: float) -> Dict:
        """
        OFI + VWAP sinyal gücü analizi
        Z-Score kullanarak dinamik karar verir.
        """
        z_score = self.get_z_score_ofi(ofi)
        
        signal = "NEUTRAL"
        strength = 0.0
        reason = ""
        
        # Dynamic Thresholds (Sigma levels)
        # 1.5 Sigma -> Normal Sinyal
        # 2.0 Sigma -> Güçlü Sinyal
        
        sigma_threshold = 1.5
        
        if z_score > sigma_threshold:
            # Bullish OFI
            if price < vwap:
                # Underpriced + Buying Pressure = STRONG BUY
                signal = "BUY"
                strength = min(abs(z_score) / 3.0, 1.0) 
                reason = "High Buy Pressure + Underpriced"
            else:
                # Momentum Buy
                signal = "BUY"
                strength = min(abs(z_score) / 4.0, 0.7)
                reason = "Momentum Buy"
                
        elif z_score < -sigma_threshold:
            # Bearish OFI
            if price > vwap:
                # Overpriced + Selling Pressure = STRONG SELL
                signal = "SELL"
                strength = min(abs(z_score) / 3.0, 1.0)
                reason = "High Sell Pressure + Overpriced"
            else:
                # Panic Sell
                signal = "SELL"
                strength = min(abs(z_score) / 4.0, 0.7)
                reason = "Panic Sell"
                
        return {
            "direction": signal,
            "strength": strength,
            "reason": reason,
            "z_score": z_score
        }

    @staticmethod
    def calculate_spread(orderbook: Dict) -> float:
        """Spread (Alış-Satış Makası) Hesapla (%)"""
        if not orderbook or not orderbook.get('bids') or not orderbook.get('asks'):
            return 0.0
        best_bid = float(orderbook['bids'][0][0])
        best_ask = float(orderbook['asks'][0][0])
        if best_bid == 0: return 0.0
        return (best_ask - best_bid) / best_bid * 100 
