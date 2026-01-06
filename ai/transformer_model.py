# ============================================================
# NEXUS PRO - Transformer Price Predictor
# ============================================================
# PyTorch tabanlı Fiyat Tahmin Modeli
# ============================================================

import logging
import numpy as np
import pandas as pd
from typing import Optional, List

# Try imports
try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

from utils import get_logger

logger = get_logger("ai_transformer")

class TimeSeriesTransformer(nn.Module if TORCH_AVAILABLE else object):
    """
    Basit Time-Series Transformer Modeli (Encoder Only)
    """
    def __init__(self, input_dim: int = 5, d_model: int = 64, nhead: int = 4, num_layers: int = 2, output_dim: int = 1):
        if not TORCH_AVAILABLE:
            return
        super().__init__()
        
        self.encoder_layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=nhead, batch_first=True)
        self.transformer_encoder = nn.TransformerEncoder(self.encoder_layer, num_layers=num_layers)
        
        self.input_proj = nn.Linear(input_dim, d_model)
        self.output_proj = nn.Linear(d_model, output_dim)
        
    def forward(self, src: 'torch.Tensor') -> 'torch.Tensor':
        if not TORCH_AVAILABLE:
            return None
        
        # src shape: [batch_size, seq_len, input_dim]
        x = self.input_proj(src)
        # x shape: [batch_size, seq_len, d_model]
        
        output = self.transformer_encoder(x)
        # output shape: [batch_size, seq_len, d_model]
        
        # Sadece son zaman adımını al
        last_step = output[:, -1, :]
        
        prediction = self.output_proj(last_step)
        return prediction

class PricePredictor:
    """
    Wrapper for using the model in the bot
    """
    def __init__(self, seq_len: int = 60):
        self.seq_len = seq_len
        self.model = None
        
        if TORCH_AVAILABLE:
            self.model = TimeSeriesTransformer()
            self.model.eval() # Inference mode
        else:
            logger.warning("PyTorch not installed. Transformer prediction disabled.")

    def predict_next_price(self, df: pd.DataFrame) -> Optional[float]:
        """
        Gelecek fiyatı tahmin et.
        Şu anlık pretrained weight olmadığı için dummy çalışır.
        İleride 'train.py' ile eğitilmeli.
        """
        if not TORCH_AVAILABLE or self.model is None:
            return None
            
        if len(df) < self.seq_len:
            return None
            
        # Prepare Data (OHLCV)
        # Normalize
        last_window = df.iloc[-self.seq_len:][['open', 'high', 'low', 'close', 'volume']].values
        
        # Simple specific normalization (last close as base)
        base_price = last_window[-1, 3] # Close price
        normalized_data = last_window / base_price
        
        try:
            tensor_data = torch.FloatTensor(normalized_data).unsqueeze(0) # Batch dim
            
            with torch.no_grad():
                prediction_norm = self.model(tensor_data)
                
            predicted_price = prediction_norm.item() * base_price
            return predicted_price
            
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return None
