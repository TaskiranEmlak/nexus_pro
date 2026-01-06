# ============================================================
# NEXUS PRO - Signal Generator  
# ============================================================
# Teknik analiz + ML bazlı sinyal üretimi
# Multi-timeframe analiz ve trend tespiti
# ============================================================

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import numpy as np

logger = logging.getLogger("nexus_pro.ai")

class SignalType(Enum):
    NONE = "NONE"
    BUY = "BUY"
    SELL = "SELL"

@dataclass
class Signal:
    """Trading sinyali"""
    symbol: str
    signal_type: SignalType
    confidence: float
    entry_price: float
    stop_loss: float
    take_profit: float
    features: Dict
    reasoning: str
    timestamp: int

class TechnicalAnalyzer:
    """Teknik gösterge hesaplayıcı"""
    
    @staticmethod
    def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """Tüm teknik göstergeleri hesapla"""
        df = df.copy()
        
        # RSI
        df['rsi_14'] = TechnicalAnalyzer._rsi(df['close'], 14)
        
        # MACD
        df['ema_12'] = df['close'].ewm(span=12).mean()
        df['ema_26'] = df['close'].ewm(span=26).mean()
        df['macd'] = df['ema_12'] - df['ema_26']
        df['macd_signal'] = df['macd'].ewm(span=9).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        
        # Bollinger Bands
        df['bb_middle'] = df['close'].rolling(20).mean()
        df['bb_std'] = df['close'].rolling(20).std()
        df['bb_upper'] = df['bb_middle'] + 2 * df['bb_std']
        df['bb_lower'] = df['bb_middle'] - 2 * df['bb_std']
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle'] * 100
        
        # ADX
        df['adx_14'], df['plus_di'], df['minus_di'] = TechnicalAnalyzer._adx(df, 14)
        
        # ATR
        df['atr_14'] = TechnicalAnalyzer._atr(df, 14)
        df['atr_pct'] = df['atr_14'] / df['close'] * 100
        
        # Volume
        df['volume_sma'] = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']
        
        # Stochastic
        df['stoch_k'], df['stoch_d'] = TechnicalAnalyzer._stochastic(df, 14, 3)
        
        # EMA distances
        df['ema_12_dist'] = (df['close'] - df['ema_12']) / df['close'] * 100
        
        return df
        
    @staticmethod
    def _rsi(series: pd.Series, period: int) -> pd.Series:
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
        
    @staticmethod
    def _adx(df: pd.DataFrame, period: int) -> Tuple[pd.Series, pd.Series, pd.Series]:
        high, low, close = df['high'], df['low'], df['close']
        
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        
        tr = pd.concat([
            high - low,
            abs(high - close.shift()),
            abs(low - close.shift())
        ], axis=1).max(axis=1)
        
        atr = tr.rolling(period).mean()
        plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(period).mean() / atr)
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(period).mean()
        
        return adx, plus_di, minus_di
        
    @staticmethod
    def _atr(df: pd.DataFrame, period: int) -> pd.Series:
        high, low, close = df['high'], df['low'], df['close']
        tr = pd.concat([
            high - low,
            abs(high - close.shift()),
            abs(low - close.shift())
        ], axis=1).max(axis=1)
        return tr.rolling(period).mean()
        
    @staticmethod
    def _stochastic(df: pd.DataFrame, k_period: int, d_period: int) -> Tuple[pd.Series, pd.Series]:
        low_min = df['low'].rolling(k_period).min()
        high_max = df['high'].rolling(k_period).max()
        k = 100 * (df['close'] - low_min) / (high_max - low_min)
        d = k.rolling(d_period).mean()
        return k, d


class SignalGenerator:
    """
    Sinyal üretici
    
    Mantık:
    1. Teknik göstergeleri hesapla
    2. RSI + MACD + Stochastic kombinasyonu ile sinyal oluştur
    3. Trend filtresi uygula
    """
    
    def __init__(self, trading_settings=None):
        self.signals_today = 0
        self.max_signals = trading_settings.max_signals_per_day if trading_settings else 100
        
    def generate_signal(
        self, 
        symbol: str, 
        df: pd.DataFrame,
        market_trend: str = "SIDEWAYS"
    ) -> Optional[Signal]:
        """
        Sinyal üret
        
        Args:
            symbol: Trading sembolü
            df: OHLCV DataFrame (göstergeler hesaplanmış)
            market_trend: Piyasa rejimi
            
        Returns:
            Signal veya None
        """
        if df is None or len(df) < 50:
            return None
            
        # FIX: Repainting prevention - Use closed candles
        # iloc[-1] is the current (forming) candle. 
        # iloc[-2] is the last completed candle.
        latest = df.iloc[-2] 
        prev = df.iloc[-3]
        
        # Volatile regime check - STAY CASH
        if market_trend == "VOLATILE":
            logger.info(f"Market is VOLATILE for {symbol}. Staying in cash.")
            return None

        features = self._extract_features(latest)
        
        # Sinyal tespiti
        signal_type = self._detect_signal(latest, prev, market_trend)
        
        if signal_type == SignalType.NONE:
            return None
            
        # Entry, SL, TP hesapla
        entry_price = float(latest['close'])
        atr = float(latest.get('atr_14', entry_price * 0.01))
        
        if signal_type == SignalType.BUY:
            stop_loss = entry_price - (atr * 1.5)
            take_profit = entry_price + (atr * 3.0)  # 2:1 R/R
        else:
            stop_loss = entry_price + (atr * 1.5)
            take_profit = entry_price - (atr * 3.0)
            
        # Base confidence (daha sonra ConfidenceScorer detaylandıracak)
        confidence = self._calculate_base_confidence(latest, signal_type)
        
        reasoning = self._build_reasoning(latest, signal_type)
        
        return Signal(
            symbol=symbol,
            signal_type=signal_type,
            confidence=confidence,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            features=features,
            reasoning=reasoning,
            timestamp=int(latest.get('timestamp', 0))
        )
        
    def _detect_signal(self, latest: pd.Series, prev: pd.Series, market_trend: str) -> SignalType:
        """Sinyal tipi tespit et"""
        rsi = latest.get('rsi_14', 50)
        macd_hist = latest.get('macd_hist', 0)
        prev_macd_hist = prev.get('macd_hist', 0)
        stoch_k = latest.get('stoch_k', 50)
        stoch_d = latest.get('stoch_d', 50)
        
        buy_score = 0
        sell_score = 0
        
        # ==========================================
        # 1. SIDEWAYS REGIME (Yatay Piyasa)
        # Strateji: Mean Reversion (RSI 30-70)
        # ==========================================
        if market_trend == "SIDEWAYS":
            # Strict RSI limits for Sideways
            if rsi < 30:
                buy_score += 3 # Strong signal
            elif rsi > 70:
                sell_score += 3
            
            # Support with Stoch
            if stoch_k < 20 and stoch_k > stoch_d:
                buy_score += 1
            elif stoch_k > 80 and stoch_k < stoch_d:
                sell_score += 1

        # ==========================================
        # 2. TRENDING REGIME (Trend Piyasası)
        # Strateji: Trend Following (MACD, EMA)
        # RSI limits ignored (allow buy at 40-50 if trend is strong)
        # ==========================================
        elif market_trend == "TRENDING":
            # MACD Crossover is king here
            if macd_hist > 0 and prev_macd_hist <= 0:
                buy_score += 3
            elif macd_hist < 0 and prev_macd_hist >= 0:
                sell_score += 3
            elif macd_hist > 0:
                buy_score += 1
            elif macd_hist < 0:
                sell_score += 1
                
            # Buy the dip logic
            # e.g. Price above EMA50 but RSI dipped to 40
            if rsi < 45 and macd_hist > 0: 
               buy_score += 1
               
        # ==========================================
        # 3. GENERIC / FALLBACK
        # ==========================================
        else:
            # Default logic if no regime detected (shouldn't happen often)
            if rsi < 35: buy_score += 2
            elif rsi > 65: sell_score += 2
            
        # Minimum Score Threshold
        threshold = 3 
        
        if buy_score >= threshold and buy_score > sell_score:
            return SignalType.BUY
        elif sell_score >= threshold and sell_score > buy_score:
            return SignalType.SELL
            
        return SignalType.NONE
        
    def _calculate_base_confidence(self, latest: pd.Series, signal_type: SignalType) -> float:
        """Base confidence hesapla (0.0 - 1.0)"""
        confidence = 0.5  # Başlangıç
        
        rsi = latest.get('rsi_14', 50)
        adx = latest.get('adx_14', 20)
        volume_ratio = latest.get('volume_ratio', 1.0)
        
        # RSI extreme = daha iyi
        if signal_type == SignalType.BUY:
            if rsi < 30:
                confidence += 0.15
            elif rsi < 40:
                confidence += 0.10
        else:
            if rsi > 70:
                confidence += 0.15
            elif rsi > 60:
                confidence += 0.10
                
        # Güçlü trend = daha iyi
        if adx > 30:
            confidence += 0.10
        elif adx > 25:
            confidence += 0.05
            
        # Yüksek hacim = daha iyi
        if volume_ratio > 2.0:
            confidence += 0.10
        elif volume_ratio > 1.5:
            confidence += 0.05
            
        return min(confidence, 0.95)
        
    def _extract_features(self, row: pd.Series) -> Dict:
        """Teknik göstergeleri dict olarak çıkar"""
        return {
            'rsi_14': float(row.get('rsi_14', 50)),
            'macd': float(row.get('macd', 0)),
            'macd_signal': float(row.get('macd_signal', 0)),
            'macd_hist': float(row.get('macd_hist', 0)),
            'adx_14': float(row.get('adx_14', 20)),
            'plus_di': float(row.get('plus_di', 0)),
            'minus_di': float(row.get('minus_di', 0)),
            'atr_14': float(row.get('atr_14', 0)),
            'atr_pct': float(row.get('atr_pct', 0)),
            'volume_ratio': float(row.get('volume_ratio', 1.0)),
            'stoch_k': float(row.get('stoch_k', 50)),
            'stoch_d': float(row.get('stoch_d', 50)),
            'bb_width': float(row.get('bb_width', 0)),
            'close': float(row.get('close', 0))
        }
        
    def _build_reasoning(self, latest: pd.Series, signal_type: SignalType) -> str:
        """Sinyal gerekçesi oluştur"""
        reasons = []
        
        rsi = latest.get('rsi_14', 50)
        macd_hist = latest.get('macd_hist', 0)
        stoch_k = latest.get('stoch_k', 50)
        
        if signal_type == SignalType.BUY:
            if rsi < 35:
                reasons.append(f"RSI aşırı satım ({rsi:.1f})")
            if macd_hist > 0:
                reasons.append("MACD pozitif")
            if stoch_k < 30:
                reasons.append(f"Stoch düşük ({stoch_k:.1f})")
        else:
            if rsi > 65:
                reasons.append(f"RSI aşırı alım ({rsi:.1f})")
            if macd_hist < 0:
                reasons.append("MACD negatif")
            if stoch_k > 70:
                reasons.append(f"Stoch yüksek ({stoch_k:.1f})")
                
        return " | ".join(reasons) if reasons else "Teknik sinyaller"
