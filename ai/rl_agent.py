# ============================================================
# NEXUS PRO - RL Agent (PPO)
# ============================================================
# Reinforcement Learning Ajanı
# ============================================================

import logging
import numpy as np
import pandas as pd
from typing import Dict, Any

from utils import get_logger

logger = get_logger("ai_rl")

# Try imports
try:
    import gymnasium as gym
    from stable_baselines3 import PPO
    RL_AVAILABLE = True
except ImportError:
    RL_AVAILABLE = False


class TradingEnv(gym.Env if RL_AVAILABLE else object):
    """
    RL Environment for Risk Management
    Ajan, piyasa koşullarına göre en iyi SL/TP oranlarını (Risk Profili) seçer.
    """
    def __init__(self, df: pd.DataFrame):
        super().__init__()
        self.df = df
        self.current_step = 0
        self.max_steps = len(df) - 1
        
        # Track performance
        self.balance = 1000.0
        self.peak_balance = 1000.0
        self.max_drawdown = 0.0
        
        if RL_AVAILABLE:
            # Action Space: Risk Profiles
            # 0: Conservative (Tight SL, Low TP) - Low Risk
            # 1: Balanced (Normal SL, Normal TP) - Med Risk
            # 2: Aggressive (Wide SL, Huge TP) - High Risk
            self.action_space = gym.spaces.Discrete(3)
            
            # Observation Space: Risk Indicators
            # [RSI, ATR_Pct, Volatility, Trend_Strength, Current_Drawdown]
            self.observation_space = gym.spaces.Box(
                low=-np.inf, high=np.inf, shape=(5,), dtype=np.float32
            )

    def reset(self, seed=None):
        self.current_step = 100 # Warmup
        self.balance = 1000.0
        self.peak_balance = 1000.0
        self.max_drawdown = 0.0
        return self._get_observation(), {}

    def _get_observation(self):
        row = self.df.iloc[self.current_step]
        
        # Simple Feature Engineering for RL
        obs = np.array([
            row.get('rsi_14', 50) / 100.0,      # Norm RSI
            row.get('atr_pct', 1.0) / 5.0,      # Norm ATR
            row.get('bb_width', 2.0) / 10.0,    # Volatility
            row.get('adx_14', 20) / 100.0,      # Trend Strength
            self.max_drawdown                   # Current DD State
        ], dtype=np.float32)
        return obs

    def step(self, action):
        self.current_step += 1
        done = self.current_step >= self.max_steps
        
        # Simulate Trade based on Action (Risk Profile)
        # Action determines the SL/TP multiplier
        # 0: SL=1xATR, TP=1.5xATR
        # 1: SL=1.5xATR, TP=2.5xATR
        # 2: SL=2xATR,   TP=4xATR
        
        multipliers = {
            0: (1.0, 1.5),
            1: (1.5, 2.5),
            2: (2.0, 4.0)
        }
        sl_mult, tp_mult = multipliers[action]
        
        # Calculate theoretical PnL for this step (Dummy Simulation)
        # In real training, we would iterate until trade close.
        # Here we just look at next candle for simplicity in this structure
        current_price = self.df.iloc[self.current_step]['close']
        prev_price = self.df.iloc[self.current_step-1]['close']
        change = (current_price - prev_price) / prev_price
        
        # Assuming we are ALWAYS LONG for this RL training (simplified)
        # Real logic needs Signal Generator integration
        pnl = change * 100  # Dummy PnL magnitude
        
        # Update Balance
        self.balance += pnl
        if self.balance > self.peak_balance:
            self.peak_balance = self.balance
        
        dd = (self.peak_balance - self.balance) / self.peak_balance
        if dd > self.max_drawdown:
            self.max_drawdown = dd
            
        # REWARD FUNCTION
        # Reward = Profit / Risk
        # Penalty for Drawdown
        reward = pnl - (dd * 10) 
        
        return self._get_observation(), reward, done, False, {}

class RLAgent:
    """
    PPO Agent Yöneticisi
    """
    def __init__(self, model_path: str = "ppo_nexus_model"):
        self.model = None
        self.model_path = model_path
        
        if not RL_AVAILABLE:
            logger.warning("Stable-Baselines3 not installed. RL Agent disabled.")
            return

    def load(self):
        """Modeli yükle"""
        if not RL_AVAILABLE: return
        try:
            self.model = PPO.load(self.model_path)
            logger.info("RL Models loaded.")
        except Exception:
            logger.warning("No pre-trained RL model found. Agent will needs training.")
            self.model = None

    def predict_risk_profile(self, observation: np.ndarray) -> int:
        """
        Risk Profili tahmin et
        Returns: 
            0: Conservative (Düşük Risk)
            1: Balanced (Dengeli)
            2: Aggressive (Yüksek Risk)
        """
        if not self.model:
            return 1 # Default Balanced
            
        action, _ = self.model.predict(observation)
        return int(action)
