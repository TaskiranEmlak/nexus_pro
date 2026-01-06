# ============================================================
# NEXUS PRO - Quality Filter
# ============================================================
# Sinyal kalite filtresi - son kontrol noktası
# ============================================================

import logging
from typing import Dict, Tuple
from dataclasses import dataclass

logger = logging.getLogger("nexus_pro.filters")

@dataclass
class FilterResult:
    """Filtre sonucu"""
    passed: bool
    score: int
    reason: str

class QualityFilter:
    """
    Sinyal Kalite Filtresi
    
    Son kontrol noktası - tüm kriterleri geçen sinyaller için
    ek kalite kontrolleri yapar.
    """
    
    def __init__(self, min_score: int = 65):
        self.min_score = min_score
        
    def check(
        self, 
        signal_type: str,
        features: Dict,
        confidence_score: int,
        market_trend: str
    ) -> FilterResult:
        """
        Kalite kontrolü yap
        
        Returns:
            FilterResult: passed, score, reason
        """
        score = confidence_score
        penalties = []
        bonuses = []
        
        # 1. Trend-karşıtı sinyal cezası
        if signal_type == "BUY" and market_trend == "BEAR":
            score -= 10
            penalties.append("Trend karşıtı (-10)")
        elif signal_type == "SELL" and market_trend == "BULL":
            score -= 10
            penalties.append("Trend karşıtı (-10)")
            
        # 2. Aşırı volatilite cezası
        atr_pct = features.get('atr_pct', 0)
        if atr_pct > 3.0:
            score -= 15
            penalties.append(f"Yüksek volatilite ({atr_pct:.1f}%) (-15)")
        elif atr_pct > 2.5:
            score -= 5
            penalties.append(f"Volatilite ({atr_pct:.1f}%) (-5)")
            
        # 3. Volume boost
        volume_ratio = features.get('volume_ratio', 1.0)
        if volume_ratio > 2.5:
            score += 5
            bonuses.append(f"Güçlü hacim ({volume_ratio:.1f}x) (+5)")
            
        # 4. RSI extreme bonus
        rsi = features.get('rsi_14', 50)
        if (signal_type == "BUY" and rsi < 25) or (signal_type == "SELL" and rsi > 75):
            score += 5
            bonuses.append(f"RSI extreme ({rsi:.1f}) (+5)")
            
        # Final check
        passed = score >= self.min_score
        
        reason_parts = penalties + bonuses
        reason = " | ".join(reason_parts) if reason_parts else "Standart"
        
        return FilterResult(
            passed=passed,
            score=score,
            reason=reason
        )


class TrendFilter:
    """Trend uyumu kontrolü"""
    
    def check(self, signal_type: str, market_trend: str, adx: float) -> Tuple[bool, str]:
        """
        Trend uyumu kontrolü
        
        Strong trend + karşıt sinyal = VETO
        Weak trend = OK
        """
        # Zayıf trend - her iki yön ok
        if adx < 25:
            return True, "Weak trend - OK"
            
        # Güçlü trend
        if adx >= 40:
            # Çok güçlü trend - sadece trend yönünde izin ver
            if market_trend in ["BULL", "STRONG_BULL"] and signal_type == "SELL":
                return False, f"Strong BULL trend (ADX={adx:.1f}) - SELL blocked"
            if market_trend in ["BEAR", "STRONG_BEAR"] and signal_type == "BUY":
                return False, f"Strong BEAR trend (ADX={adx:.1f}) - BUY blocked"
                
        return True, "Trend aligned"
        

class VolumeFilter:
    """Hacim desteği kontrolü"""
    
    def __init__(self, min_ratio: float = 1.2):
        self.min_ratio = min_ratio
        
    def check(self, volume_ratio: float) -> Tuple[bool, str]:
        """Hacim kontrolü"""
        if volume_ratio >= self.min_ratio:
            return True, f"Volume OK ({volume_ratio:.1f}x)"
        return False, f"Low volume ({volume_ratio:.1f}x < {self.min_ratio}x)"
