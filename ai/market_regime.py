# ============================================================
# NEXUS PRO - Market Regime Detector
# ============================================================
# Piyasa rejimi tespiti (Bull/Bear/Sideways)
# ADX + EMA + Trend analizi
# ============================================================

import logging
from typing import Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import numpy as np

logger = logging.getLogger("nexus_pro.ai")

class MarketRegime(Enum):
    STRONG_BULL = "STRONG_BULL"
    BULL = "BULL"
    SIDEWAYS = "SIDEWAYS"
    BEAR = "BEAR"
    STRONG_BEAR = "STRONG_BEAR"

@dataclass
class RegimeResult:
    """Rejim analiz sonucu"""
    regime: MarketRegime
    strength: float  # 0-100
    adx: float
    trend_direction: str  # "UP", "DOWN", "NEUTRAL"
    reasoning: str

class MarketRegimeDetector:
    """
    Piyasa Rejimi Tespiti
    
    Kriterler:
    - ADX > 40: Çok güçlü trend
    - ADX 25-40: Güçlü trend  
    - ADX < 25: Zayıf trend / Sideways
    - Plus_DI > Minus_DI: Bullish
    - Minus_DI > Plus_DI: Bearish
    """
    
    def __init__(self):
        self._cache: dict = {}
        
    def detect(self, df: pd.DataFrame, symbol: str = "MARKET") -> RegimeResult:
        """
        Piyasa rejimini tespit et
        
        Args:
            df: OHLCV DataFrame (göstergeler hesaplanmış)
            symbol: Sembol adı (cache için)
            
        Returns:
            RegimeResult
        """
        if df is None or len(df) < 30:
            return RegimeResult(
                regime=MarketRegime.SIDEWAYS,
                strength=0,
                adx=20,
                trend_direction="NEUTRAL",
                reasoning="Yetersiz veri"
            )
            
        latest = df.iloc[-1]
        
        adx = float(latest.get('adx_14', 20))
        plus_di = float(latest.get('plus_di', 0))
        minus_di = float(latest.get('minus_di', 0))
        
        # EMA trend
        close = float(latest.get('close', 0))
        ema_12 = float(latest.get('ema_12', close))
        ema_26 = float(latest.get('ema_26', close))
        
        # Trend yönü
        if plus_di > minus_di:
            trend_direction = "UP"
            di_diff = plus_di - minus_di
        elif minus_di > plus_di:
            trend_direction = "DOWN"
            di_diff = minus_di - plus_di
        else:
            trend_direction = "NEUTRAL"
            di_diff = 0
            
        # EMA onayı
        ema_bullish = close > ema_12 > ema_26
        ema_bearish = close < ema_12 < ema_26
        
        # Rejim belirleme
        if adx >= 40:
            # Çok güçlü trend
            if trend_direction == "UP" and ema_bullish:
                regime = MarketRegime.STRONG_BULL
                strength = min(adx + di_diff, 100)
            elif trend_direction == "DOWN" and ema_bearish:
                regime = MarketRegime.STRONG_BEAR
                strength = min(adx + di_diff, 100)
            else:
                regime = MarketRegime.BULL if trend_direction == "UP" else MarketRegime.BEAR
                strength = adx
        elif adx >= 25:
            # Güçlü trend
            if trend_direction == "UP":
                regime = MarketRegime.BULL
                strength = adx + (di_diff * 0.5)
            elif trend_direction == "DOWN":
                regime = MarketRegime.BEAR
                strength = adx + (di_diff * 0.5)
            else:
                regime = MarketRegime.SIDEWAYS
                strength = 50 - adx
        else:
            # Zayıf trend / Sideways
            regime = MarketRegime.SIDEWAYS
            strength = max(0, 50 - adx)
            
        reasoning = self._build_reasoning(adx, plus_di, minus_di, ema_bullish, ema_bearish)
        
        result = RegimeResult(
            regime=regime,
            strength=strength,
            adx=adx,
            trend_direction=trend_direction,
            reasoning=reasoning
        )
        
        # Cache
        self._cache[symbol] = result
        
        logger.debug(f"📈 {symbol} Rejim: {regime.value} (ADX: {adx:.1f}, Güç: {strength:.1f})")
        
        return result
        
    def _build_reasoning(
        self, 
        adx: float, 
        plus_di: float, 
        minus_di: float,
        ema_bull: bool,
        ema_bear: bool
    ) -> str:
        """Rejim gerekçesi oluştur"""
        parts = []
        
        parts.append(f"ADX={adx:.1f}")
        
        if plus_di > minus_di:
            parts.append(f"+DI>{minus_di:.1f}")
        else:
            parts.append(f"-DI>{plus_di:.1f}")
            
        if ema_bull:
            parts.append("EMA↑")
        elif ema_bear:
            parts.append("EMA↓")
        else:
            parts.append("EMA→")
            
        return " | ".join(parts)
        
    def get_cached(self, symbol: str) -> Optional[RegimeResult]:
        """Cache'den rejim al"""
        return self._cache.get(symbol)
        
    def is_trending(self, symbol: str) -> bool:
        """Trend var mı?"""
        result = self._cache.get(symbol)
        if result:
            return result.regime not in [MarketRegime.SIDEWAYS]
        return False
        
    def is_bullish(self, symbol: str) -> bool:
        """Bullish mi?"""
        result = self._cache.get(symbol)
        if result:
            return result.regime in [MarketRegime.BULL, MarketRegime.STRONG_BULL]
        return False
        
    def is_bearish(self, symbol: str) -> bool:
        """Bearish mi?"""
        result = self._cache.get(symbol)
        if result:
            return result.regime in [MarketRegime.BEAR, MarketRegime.STRONG_BEAR]
        return False
