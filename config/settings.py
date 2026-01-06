# ============================================================
# NEXUS PRO - Settings
# ============================================================
# Merkezi konfigürasyon dosyası
# Tüm ayarlar buradan yönetilir
# ============================================================

import os
from dataclasses import dataclass, field
from typing import List, Dict
from enum import Enum

class MarketRegime(Enum):
    BULL = "BULL"
    BEAR = "BEAR"
    SIDEWAYS = "SIDEWAYS"

@dataclass
class ExchangeSettings:
    """Borsa ayarları"""
    name: str = "binance_futures"
    api_key: str = field(default_factory=lambda: os.environ.get("BINANCE_API_KEY", ""))
    api_secret: str = field(default_factory=lambda: os.environ.get("BINANCE_API_SECRET", ""))
    testnet: bool = True  # Güvenlik: Default testnet

@dataclass 
class TradingSettings:
    """Trading ayarları"""
    # Sinyal hedefleri
    max_signals_per_day: int = 100
    min_confidence: float = 0.65  # 65+ puan geçer
    
    # HFT / Scalping Settings
    hft_enabled: bool = True  # GOD MODE
    max_scalp_hold_time: int = 180 
    ofi_threshold: float = 0.4
    
    # Timeframe
    primary_timeframe: str = "5m"
    confirmation_timeframes: List[str] = field(default_factory=lambda: ["15m", "1h"])
    
    # Sembol ayarları
    max_symbols: int = 50
    blacklisted_symbols: List[str] = field(default_factory=list)

@dataclass
class RiskSettings:
    """Risk yönetimi ayarları"""
    # Pozisyon limitleri
    max_position_size: float = 0.02  # %2 maksimum
    max_open_positions: int = 5
    
    # Stop Loss / Take Profit
    default_sl_percent: float = 1.0  # %1
    default_tp_percent: float = 2.0  # %2 (2:1 R/R)
    use_atr_based_sl: bool = True
    atr_sl_multiplier: float = 1.5
    
    # Drawdown koruma
    max_daily_drawdown: float = 0.10  # %10
    pause_on_drawdown: bool = True

@dataclass
class AISettings:
    """AI/ML ayarları"""
    # Confidence Scorer ağırlıkları
    trend_weight: int = 25
    rsi_weight: int = 20
    macd_weight: int = 15
    volume_weight: int = 20
    history_weight: int = 20
    
    # RL Agent
    rl_enabled: bool = True
    rl_model_path: str = "models/rl_agent.zip"
    
    # Groq API (LLM)
    groq_api_key: str = field(default_factory=lambda: os.environ.get("GROQ_API_KEY", ""))
    groq_enabled: bool = False  # Default kapalı - basit başla

@dataclass
class FilterSettings:
    """Filtre ayarları"""
    # RSI filtreleri
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    
    # Volume filtresi
    min_volume_ratio: float = 1.5
    
    # ADX filtresi
    min_adx_trend: float = 25.0
    
    # Kalite skoru
    min_quality_score: int = 65

@dataclass
class Settings:
    """Ana ayarlar sınıfı"""
    exchange: ExchangeSettings = field(default_factory=ExchangeSettings)
    trading: TradingSettings = field(default_factory=TradingSettings)
    risk: RiskSettings = field(default_factory=RiskSettings)
    ai: AISettings = field(default_factory=AISettings)
    filters: FilterSettings = field(default_factory=FilterSettings)
    
    # Genel
    log_level: str = "INFO"
    database_path: str = "nexus_pro.db"

# Global settings instance
settings = Settings()

def load_settings_from_env():
    """Environment variables'dan ayarları yükle"""
    settings.exchange.api_key = os.environ.get("BINANCE_API_KEY", "")
    settings.exchange.api_secret = os.environ.get("BINANCE_API_SECRET", "")
    settings.ai.groq_api_key = os.environ.get("GROQ_API_KEY", "")
    return settings
