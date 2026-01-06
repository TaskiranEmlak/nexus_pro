
import sys
import os
import asyncio
import pandas as pd
import numpy as np
import logging
from unittest.mock import MagicMock, AsyncMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import NexusPro
from ai.signal_generator import SignalType, Signal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("IntegrationTest")

async def test_full_pipeline():
    logger.info("🚀 Testing Full Integration (Mocked)...")
    
    bot = NexusPro()
    
    # 1. Mock DataProvider
    bot.data_provider = MagicMock()
    bot.data_provider.get_candles.return_value = pd.DataFrame({
        'close': np.random.random(100) * 100 + 50000,
        'high': np.random.random(100) * 105 + 50000,
        'low': np.random.random(100) * 95 + 50000,
        'open': np.random.random(100) * 100 + 50000,
        'volume': np.random.random(100) * 1000
    })
    
    # 2. Mock OrderExecutor
    bot.order_executor = AsyncMock()
    bot.order_executor.place_limit_order.return_value = {'orderId': 999, 'status': 'NEW'}
    
    # 3. Mock RLAgent
    bot.rl_agent = MagicMock()
    bot.rl_agent.predict_risk_profile.return_value = 2 # Aggressive
    
    # 4. Mock Signal Generator to FORCE a signal
    real_sig_gen = bot.signal_generator
    bot.signal_generator = MagicMock()
    
    # Force a BUY signal
    mock_signal = Signal(
        symbol="BTCUSDT",
        signal_type=SignalType.BUY,
        confidence=0.9,
        entry_price=50000.0,
        stop_loss=49000.0,
        take_profit=52000.0,
        features={'rsi_14': 30, 'atr_pct': 1.0},
        reasoning="Integration Test Force",
        timestamp=123456789
    )
    bot.signal_generator.generate_signal.return_value = mock_signal
    
    # 5. Disable HMM for test speed
    bot.hmm_detector = None 
    
    # RUN ANALYSIS
    logger.info("▶️ Triggering analyze_symbol('BTCUSDT')...")
    await bot.analyze_symbol("BTCUSDT")
    
    # VERIFY
    # Check if Risk Profile was requested
    if bot.rl_agent.predict_risk_profile.called:
        logger.info("✅ RL Agent Consulted for Risk Profile")
    else:
        logger.error("❌ RL Agent IGNORED")
        
    # Check if Order was placed
    if bot.order_executor.place_limit_order.called:
        call_args = bot.order_executor.place_limit_order.call_args
        logger.info(f"✅ Order Placed: {call_args}")
        
        # Verify Post-Only
        if call_args.kwargs.get('post_only') is True:
             logger.info("✅ Order is Post-Only")
        else:
             logger.error("❌ Order is NOT Post-Only")
    else:
        logger.error("❌ No Order Placed (Maybe Risk Manager blocked it?)")
        
    # Check Risk Manager State
    if "BTCUSDT" in bot.risk_manager.open_positions:
        logger.info("✅ Position Recorded in Risk Manager")
    else:
        logger.error("❌ Position NOT Recorded in Risk Manager")

if __name__ == "__main__":
    asyncio.run(test_full_pipeline())
