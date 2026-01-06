# ============================================================
# NEXUS PRO - Confidence Scorer
# ============================================================
# Multi-indicator güven puanlama sistemi
# Her sinyal 0-100 arası puan alır, 65+ geçer
# ============================================================

import logging
from typing import Dict, Optional
from dataclasses import dataclass
import pandas as pd
import numpy as np

logger = logging.getLogger("nexus_pro.ai")

@dataclass
class ConfidenceResult:
    """Güven skoru sonucu"""
    total_score: int
    passed: bool
    components: Dict[str, int]
    reasoning: str

class ConfidenceScorer:
    """
    Multi-Indicator Confidence Scoring
    
    Bileşenler:
    - Trend Uyumu: +25 puan
    - RSI Doğrulama: +20 puan  
    - MACD Onayı: +15 puan
    - Volume Desteği: +20 puan
    - Geçmiş Performans: +20 puan
    
    Toplam: 100 puan
    Geçme eşiği: 65+
    """
    
    def __init__(self, min_score: int = 65):
        self.min_score = min_score
        
        # Ağırlıklar
        self.weights = {
            'trend': 25,
            'rsi': 20,
            'macd': 15,
            'volume': 20,
            'history': 20
        }
        
        # Sembol performans geçmişi
        self.symbol_performance: Dict[str, Dict] = {}
        
    def calculate_score(
        self,
        signal_type: str,  # "BUY" veya "SELL"
        features: Dict,
        market_trend: str,  # "BULL", "BEAR", "SIDEWAYS"
        symbol: str
    ) -> ConfidenceResult:
        """
        Sinyal için güven skoru hesapla
        
        Args:
            signal_type: "BUY" veya "SELL"
            features: Teknik göstergeler (rsi, macd_hist, volume_ratio, adx, etc.)
            market_trend: Piyasa rejimi
            symbol: Trading sembolü
            
        Returns:
            ConfidenceResult: Toplam skor ve bileşenler
        """
        components = {}
        reasons = []
        
        # 1. TREND UYUMU (+25)
        trend_score = self._check_trend_alignment(signal_type, market_trend, features)
        components['trend'] = trend_score
        if trend_score > 0:
            reasons.append(f"Trend uyumlu (+{trend_score})")
        else:
            reasons.append("Trend ters (0)")
            
        # 2. RSI DOĞRULAMA (+20)
        rsi_score = self._check_rsi(signal_type, features.get('rsi_14', 50))
        components['rsi'] = rsi_score
        if rsi_score > 0:
            reasons.append(f"RSI doğruladı (+{rsi_score})")
            
        # 3. MACD ONAYI (+15)
        macd_score = self._check_macd(signal_type, features)
        components['macd'] = macd_score
        if macd_score > 0:
            reasons.append(f"MACD onayladı (+{macd_score})")
            
        # 4. VOLUME DESTEĞİ (+20)
        volume_score = self._check_volume(features.get('volume_ratio', 1.0))
        components['volume'] = volume_score
        if volume_score > 0:
            reasons.append(f"Hacim desteği (+{volume_score})")
            
        # 5. GEÇMİŞ PERFORMANS (+20)
        history_score = self._check_history(symbol, signal_type)
        components['history'] = history_score
        if history_score > 0:
            reasons.append(f"Geçmiş olumlu (+{history_score})")
            
        # Toplam
        total_score = sum(components.values())
        passed = total_score >= self.min_score
        
        reasoning = " | ".join(reasons) if reasons else "Yeterli onay yok"
        
        logger.debug(f"📊 {symbol} {signal_type}: {total_score}/100 -> {'✅' if passed else '❌'}")
        
        return ConfidenceResult(
            total_score=total_score,
            passed=passed,
            components=components,
            reasoning=reasoning
        )
        
    def _check_trend_alignment(self, signal_type: str, market_trend: str, features: Dict) -> int:
        """Trend uyumu kontrolü"""
        adx = features.get('adx_14', 20)
        
        # Zayıf trend = neutral, her iki yön ok
        if adx < 20:
            return self.weights['trend'] // 2  # Yarım puan
            
        # Güçlü trend
        if market_trend == "BULL" and signal_type == "BUY":
            return self.weights['trend']
        elif market_trend == "BEAR" and signal_type == "SELL":
            return self.weights['trend']
        elif market_trend == "SIDEWAYS":
            return self.weights['trend'] // 2
        else:
            return 0  # Trend ters
            
    def _check_rsi(self, signal_type: str, rsi: float) -> int:
        """RSI doğrulama"""
        if signal_type == "BUY":
            if rsi < 30:
                return self.weights['rsi']  # Aşırı satım - mükemmel
            elif rsi < 45:
                return self.weights['rsi'] // 2  # Yarım puan
            elif rsi > 70:
                return 0  # Aşırı alım - BUY için kötü
            else:
                return self.weights['rsi'] // 3
        else:  # SELL
            if rsi > 70:
                return self.weights['rsi']  # Aşırı alım - mükemmel
            elif rsi > 55:
                return self.weights['rsi'] // 2
            elif rsi < 30:
                return 0  # Aşırı satım - SELL için kötü
            else:
                return self.weights['rsi'] // 3
                
    def _check_macd(self, signal_type: str, features: Dict) -> int:
        """MACD onayı"""
        macd_hist = features.get('macd_hist', 0)
        macd_signal = features.get('macd_signal', 0)
        macd = features.get('macd', 0)
        
        if signal_type == "BUY":
            # Histogram pozitife dönüyor veya pozitif
            if macd_hist > 0 and macd > macd_signal:
                return self.weights['macd']
            elif macd_hist > 0:
                return self.weights['macd'] // 2
            else:
                return 0
        else:  # SELL
            # Histogram negatife dönüyor veya negatif
            if macd_hist < 0 and macd < macd_signal:
                return self.weights['macd']
            elif macd_hist < 0:
                return self.weights['macd'] // 2
            else:
                return 0
                
    def _check_volume(self, volume_ratio: float) -> int:
        """Volume desteği kontrolü"""
        if volume_ratio >= 2.0:
            return self.weights['volume']  # Çok güçlü
        elif volume_ratio >= 1.5:
            return int(self.weights['volume'] * 0.8)
        elif volume_ratio >= 1.2:
            return int(self.weights['volume'] * 0.5)
        else:
            return 0  # Zayıf hacim
            
    def _check_history(self, symbol: str, signal_type: str) -> int:
        """Geçmiş performans kontrolü"""
        key = f"{symbol}_{signal_type}"
        
        if key not in self.symbol_performance:
            # İlk trade - neutral puan
            return self.weights['history'] // 2
            
        perf = self.symbol_performance[key]
        total = perf.get('wins', 0) + perf.get('losses', 0)
        
        if total < 5:
            return self.weights['history'] // 2  # Yetersiz veri
            
        win_rate = perf['wins'] / total
        
        if win_rate >= 0.7:
            return self.weights['history']  # Çok iyi
        elif win_rate >= 0.55:
            return int(self.weights['history'] * 0.7)
        elif win_rate >= 0.45:
            return int(self.weights['history'] * 0.3)
        else:
            return 0  # Kötü performans
            
    def record_result(self, symbol: str, signal_type: str, is_win: bool):
        """Trade sonucunu kaydet"""
        key = f"{symbol}_{signal_type}"
        
        if key not in self.symbol_performance:
            self.symbol_performance[key] = {'wins': 0, 'losses': 0}
            
        if is_win:
            self.symbol_performance[key]['wins'] += 1
        else:
            self.symbol_performance[key]['losses'] += 1
            
    def get_symbol_stats(self, symbol: str) -> Dict:
        """Sembol istatistiklerini getir"""
        buy_key = f"{symbol}_BUY"
        sell_key = f"{symbol}_SELL"
        
        return {
            'BUY': self.symbol_performance.get(buy_key, {'wins': 0, 'losses': 0}),
            'SELL': self.symbol_performance.get(sell_key, {'wins': 0, 'losses': 0})
        }
