
import sys
import os
import asyncio
import pandas as pd
import numpy as np
import logging
from unittest.mock import MagicMock, AsyncMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.order_executor import OrderExecutor
from ai.rl_agent import TradingEnv, RLAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestPhase2")

async def test_order_executor():
    logger.info("Testing Order Executor (Mocked)...")
    try:
        executor = OrderExecutor("key", "secret")
        
        # Mock Binance Client
        mock_client = AsyncMock()
        mock_client.futures_create_order.return_value = {'orderId': 12345, 'status': 'NEW'}
        executor.client = mock_client
        
        # Test Place Order
        order = await executor.place_limit_order("BTCUSDT", "BUY", 0.001, 50000)
        
        if order and order['orderId'] == 12345:
            logger.info("✅ Limit Order Placed Successfully (Mock)")
        else:
            logger.error("❌ Order Placement Failed")
            
    except Exception as e:
        logger.error(f"❌ Executor Test Failed: {e}")

def test_rl_env():
    logger.info("\nTesting RL Environment...")
    try:
        # Dummy Data
        df = pd.DataFrame({
            'close': np.random.random(200) * 100 + 100,
            'rsi_14': np.random.random(200) * 100,
            'atr_pct': np.random.random(200) * 5,
            'bb_width': np.random.random(200) * 10,
            'adx_14': np.random.random(200) * 100
        })
        
        env = TradingEnv(df)
        obs, _ = env.reset()
        
        logger.info(f"Initial Observation: {obs}")
        
        # Check Observation Shape
        if obs.shape == (5,):
             logger.info("✅ Observation Shape Correct (5,)")
        else:
             logger.error(f"❌ Wrong Observation Shape: {obs.shape}")
             
        # Take a step
        action = env.action_space.sample() # Random action 0, 1, 2
        obs, reward, done, _, _ = env.step(action)
        
        logger.info(f"Step Result -> Action: {action}, Reward: {reward:.4f}, Balance: {env.balance:.2f}")
        
        if isinstance(reward, float):
            logger.info("✅ Reward Calculation Works")
        else:
            logger.error("❌ Reward is not float")

    except Exception as e:
        logger.error(f"❌ RL Test Failed: {e}")

if __name__ == "__main__":
    test_rl_env()
    asyncio.run(test_order_executor())
