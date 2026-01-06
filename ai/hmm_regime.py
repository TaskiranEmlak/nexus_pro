# ============================================================
# NEXUS PRO - HMM Market Regime Detector
# ============================================================
# Hidden Markov Model ile piyasa rejimi tespiti
# ============================================================

import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM
import logging
import pickle
from pathlib import Path
from typing import Tuple, Dict

from config import settings
from utils import get_logger

logger = get_logger("ai_hmm")

class HmmMarketRegime:
    """
    Gaussian Hidden Markov Model kullanarak piyasa rejimini analiz eder.
    Gizli durumlar (States):
    0: Düşük Volatilite / Trend Yok (Sideways)
    1: Yüksek Volatilite / Trend Başlangıcı (Bull/Bear)
    2: Extreme Volatilite (Crash/Pump)
    """
    
    def __init__(self, n_components: int = 3, train_window: int = 1000):
        self.n_components = n_components
        self.train_window = train_window
        self.model = GaussianHMM(
            n_components=n_components, 
            covariance_type="full", 
            n_iter=100,
            random_state=42
        )
        self.is_fitted = False
        self.last_update = 0
        
    def _extract_features(self, df: pd.DataFrame) -> np.ndarray:
        """
        HMM için feature mühendisliği:
        1. Log Returns (Fiyat değişimi)
        2. Range (High-Low farkı - Volatilite)
        3. Volume Change (Hacim değişimi)
        """
        df = df.copy()
        
        # 1. Log Returns
        df['log_ret'] = np.log(df['close'] / df['close'].shift(1))
        
        # 2. Volatility (High-Low Range normalized)
        df['range'] = (df['high'] - df['low']) / df['close']
        
        # 3. Volume Change
        df['vol_chg'] = df['volume'].pct_change()
        
        # Drop nan
        df.dropna(inplace=True)
        
        # Select features
        features = df[['log_ret', 'range', 'vol_chg']].values
        
        # Scale features (Standardization) - HMM assumes Gaussian
        # Basit bir scaling: Mean çıkar, std'ye böl
        mean = np.mean(features, axis=0)
        std = np.std(features, axis=0)
        
        # Avoid division by zero
        std[std == 0] = 1.0
        
        scaled_features = (features - mean) / std
        return scaled_features

    def train(self, df: pd.DataFrame):
        """Modeli eğit"""
        if len(df) < 100:
            logger.warning("HMM eğitimi için yetersiz veri.")
            return

        features = self._extract_features(df)
        
        try:
            self.model.fit(features)
            self.is_fitted = True
            logger.info(f"HMM model trained with {len(features)} samples.")
        except Exception as e:
            logger.error(f"HMM training failed: {e}")

    def predict_regime(self, df: pd.DataFrame) -> Tuple[str, float]:
        """
        Mevcut veriye göre rejimi tahmin et.
        Returns: (Regime Name, Probability)
        """
        if not self.is_fitted:
            self.train(df.tail(self.train_window))
            
        if not self.is_fitted:
            return "UNKNOWN", 0.0

        features = self._extract_features(df)
        if len(features) == 0:
            return "UNKNOWN", 0.0

        # Calculate variances for each component to identify regime type dynamically
        # covars_ shape depends on covariance_type:
        # 'full': (n_components, n_features, n_features)
        variances = []
        for i in range(self.model.n_components):
            if self.model.covariance_type == 'full':
                # average variance across features
                var = np.diag(self.model.covars_[i]).mean()
            elif self.model.covariance_type == 'diag':
                 var = self.model.covars_[i].mean()
            elif self.model.covariance_type == 'spherical':
                 var = self.model.covars_[i]
            else:
                 var = 0 # should not happen with defaults
            variances.append(var)
        
        # Sort indices by variance: Low -> High
        sorted_indices = np.argsort(variances)
        
        # Map sorted indices to regimes
        # 0 (Lowest Variance) -> SIDEWAYS
        # 1 (Medium Variance) -> TRENDING
        # 2 (Highest Variance) -> VOLATILE
        
        regime_map = {
            sorted_indices[0]: "SIDEWAYS",
            sorted_indices[1]: "TRENDING",
            sorted_indices[2]: "VOLATILE"
        }
        
        # Predict current state
        hidden_states = self.model.predict(features)
        current_state = hidden_states[-1]
        
        # Posterior probabilities for the last sample
        posteriors = self.model.predict_proba(features)[-1]
        probability = posteriors[current_state]
        
        regime = regime_map.get(current_state, "UNKNOWN")
        
        return regime, probability

    def save(self, path: str = "hmm_model.pkl"):
        """Modeli kaydet"""
        try:
            with open(path, 'wb') as f:
                pickle.dump(self.model, f)
        except Exception as e:
            logger.error(f"Model save failed: {e}")
            
    def load(self, path: str = "hmm_model.pkl"):
        """Modeli yükle"""
        if not Path(path).exists():
            return
        try:
            with open(path, 'rb') as f:
                self.model = pickle.load(f)
            self.is_fitted = True
            logger.info("HMM model loaded.")
        except Exception as e:
            logger.error(f"Model load failed: {e}")
