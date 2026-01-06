
import sys
import os
import pandas as pd
import numpy as np
import logging
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ai.hmm_regime import HammMarketRegime
from ai.signal_generator import SignalGenerator, SignalType, TechnicalAnalyzer
from risk.risk_manager import RiskManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Test")

def test_hmm():
    logger.info("Testing HMM Regime...")
    try:
        # Create dummy data with patterns
        dates = pd.date_range(start='2024-01-01', periods=1200, freq='H')
        df = pd.DataFrame(index=dates)
        
        # Simulated price: Flat then Trend then Volatile
        # 1. Flat (Sideways)
        p1 = 100 + np.random.normal(0, 0.5, 400).cumsum()
        # 2. Trend
        p2 = p1[-1] + np.linspace(0, 50, 400) + np.random.normal(0, 1.0, 400)
        # 3. Volatile
        p3 = p2[-1] + np.random.normal(0, 5.0, 400).cumsum()
        
        prices = np.concatenate([p1, p2, p3])
        df['close'] = prices
        df['high'] = prices + 1.0
        df['low'] = prices - 1.0
        df['volume'] = np.random.randint(100, 1000, 1200).astype(float)
        
        hmm = HammMarketRegime(train_window=500)
        hmm.train(df)
        
        regime, prob = hmm.predict_regime(df)
        logger.info(f"HMM Prediction: {regime} (Prob: {prob:.2f})")
        
        if regime in ["SIDEWAYS", "TRENDING", "VOLATILE"]:
            logger.info("✅ HMM Prediction Valid")
        else:
            logger.error(f"❌ HMM Invalid Regime: {regime}")
            
    except Exception as e:
        logger.error(f"❌ HMM Test Failed: {e}")

def test_signal_generator():
    logger.info("\nTesting Signal Generator...")
    try:
        # Dummy data
        df = pd.DataFrame({
            'close': np.random.random(100) * 100,
            'high': np.random.random(100) * 105,
            'low': np.random.random(100) * 95,
            'volume': np.random.random(100) * 1000
        })
        
        # Calculate indicators
        ta = TechnicalAnalyzer()
        df = ta.calculate_indicators(df)
        
        sig_gen = SignalGenerator()
        
        # Test 1: Volatile Regime -> Should be None
        sig = sig_gen.generate_signal("BTC/USDT", df, market_trend="VOLATILE")
        if sig is None:
            logger.info("✅ Volatile Regime blocked signal correctly")
        else:
            logger.error("❌ Volatile Regime failed to block signal")
            
        # Test 2: Sideways Regime
        # Force RSI to generate BUY (Low RSI) in last closed candle (iloc[-2])
        # We need to manipulate the data so iloc[-2] has specific values
        
        # Set all to neutral first
        df['rsi_14'] = 50
        df['stoch_k'] = 50
        df['macd_hist'] = 0
        
        # Target: iloc[-2] (closed candle)
        # Sideways Buy: RSI < 30
        df.iloc[-2, df.columns.get_loc('rsi_14')] = 25 
        df.iloc[-2, df.columns.get_loc('stoch_k')] = 15
        df.iloc[-2, df.columns.get_loc('stoch_d')] = 20
        
        sig = sig_gen.generate_signal("BTC/USDT", df, market_trend="SIDEWAYS")
        
        if sig and sig.signal_type == SignalType.BUY:
            logger.info("✅ Sideways Buy Signal Generated (using iloc[-2])")
        else:
            # Maybe score wasn't high enough?
            logger.warning(f"⚠️ Sideways Signal check: {sig}")
            
    except Exception as e:
        logger.error(f"❌ Signal Gen Test Failed: {e}")

def test_risk_manager():
    logger.info("\nTesting Risk Manager (SQLite)...")
    try:
        if os.path.exists('risk.db'):
            os.remove('risk.db')
            
        rm = RiskManager()
        
        # Test DB creation
        if os.path.exists('risk.db'):
            logger.info("✅ risk.db created")
        else:
            logger.error("❌ risk.db not found")
            
        # Open Position
        res = rm.open_position("ETH/USDT", "LONG", 2000, 1.5, 1950, 2100)
        if res:
            logger.info("✅ Position Opened")
        else:
            logger.error("❌ Failed to open position")
            
        # Verify persistence
        del rm
        rm2 = RiskManager()
        if "ETH/USDT" in rm2.open_positions:
            logger.info("✅ Persistent State Loaded from DB")
        else:
            logger.error("❌ Failed to load state from DB")
            
    except Exception as e:
        logger.error(f"❌ Risk Manager Test Failed: {e}")

if __name__ == "__main__":
    test_hmm()
    test_signal_generator()
    test_risk_manager()
