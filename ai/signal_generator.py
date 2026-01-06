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
    HFT Sinyal Üretici (OFI + VWAP + HMM)
    
    YENİ MANTIK (GOD MODE):
    1. Mikro Yapı Analizi (Order Flow Imbalance - OFI)
    2. HMM Rejim Filtresi (Volatilite koruması)
    3. VWAP Sapması (Fiyatın adil değere göre konumu)
    """
    
    def __init__(self, trading_settings=None):
        self.signals_today = 0
        self.max_signals = trading_settings.max_signals_per_day if trading_settings else 100
        
        # Microstructure Module import (Lazy load to avoid circular import if any)
        from .microstructure import MicrostructureAnalyzer
        self.micro_analyzer = MicrostructureAnalyzer()
        
    def generate_signal(
        self, 
        symbol: str, 
        df: pd.DataFrame,
        market_trend: str = "SIDEWAYS",
        orderbook: Dict = None # YENİ: Order Book datası şart
    ) -> Optional[Signal]:
        """
        HFT Sinyal Üret
        """
        if df is None or len(df) < 50:
            return None
            
        # 1. HMM REJİM KONTROLÜ
        # Volatil piyasada Scalping tehlikelidir (Slippage artar)
        if market_trend == "VOLATILE":
            # logger.info(f"Market is VOLATILE for {symbol}. Blocking scalp.")
            return None

        # 2. MICROSTRUCTURE ANALİZİ (Order Book yoksa işlem yok)
        if not orderbook:
            return None
            
        latest = df.iloc[-1]
        
        # OFI Hesapla (-1.0 ile 1.0 arası)
        ofi = self.micro_analyzer.calculate_ofi(orderbook)
        
        # VWAP Hesapla (Basit yaklaşım: son 20 mumun VWAP'ı)
        # Gerçek HFT'de tick-by-tick hesaplanır ama burada mum verisinden approx.
        vwap = (df['close'] * df['volume']).rolling(20).sum() / df['volume'].rolling(20).sum()
        current_vwap = vwap.iloc[-1]
        current_price = latest['close']
        
        # Sinyal Gücünü Ölç
        analysis = self.micro_analyzer.get_signal_strength(ofi, current_price, current_vwap)
        
        direction = analysis['direction'] # 'BUY', 'SELL', 'NEUTRAL'
        strength = analysis['strength']   # 0.0 - 1.0
        
        # 3. KARAR MEKANİZMASI
        # OFI eşiği: 0.3 (Mikro yapıda belirgin dengesizlik)
        # Güç eşiği: 0.6 (Yüksek güven)
        
        threshold_strength = 0.6
        
        if direction == "NEUTRAL" or strength < threshold_strength:
            return None
            
        signal_type = SignalType.BUY if direction == "BUY" else SignalType.SELL
        
        # 4. HEDEFLER (Scalping için dar hedefler)
        atr = latest.get('atr_14', current_price * 0.005)
        
        if signal_type == SignalType.BUY:
            stop_loss = current_price - (atr * 0.8)  # Çok dar SL
            take_profit = current_price + (atr * 1.5) # 1.5R - 2R
        else:
            stop_loss = current_price + (atr * 0.8)
            take_profit = current_price - (atr * 1.5)

        features = self._extract_features(latest)
        features['ofi'] = ofi
        features['vwap_dist'] = (current_price - current_vwap) / current_vwap * 100
        
        reasoning = f"HFT SIGNAL | {analysis['reason']} | OFI: {ofi:.3f}"
        
        # Güven Skoru
        confidence = 0.6 + (strength * 0.3) # 0.6 taban, OFI gücüyle artar
        
        return Signal(
            symbol=symbol,
            signal_type=signal_type,
            confidence=confidence,
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            features=features,
            reasoning=reasoning,
            timestamp=int(latest.get('timestamp', 0))
        )

    # _detect_signal artık kullanılmıyor (Legacy)
    def _detect_signal(self, latest: pd.Series, prev: pd.Series, market_trend: str) -> SignalType:
        return SignalType.NONE

    def _calculate_base_confidence(self, latest: pd.Series, signal_type: SignalType) -> float:
        return 0.5
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
