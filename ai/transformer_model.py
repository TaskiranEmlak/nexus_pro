# ============================================================
# NEXUS PRO - Transformer Price Predictor (PyTorch)
# ============================================================
# GOD MODE: Gerçek zamanlı fiyat tahmini (Next Close Predictor)
# ============================================================

import torch
import torch.nn as nn
import numpy as np
import logging

logger = logging.getLogger("ai_transformer")

class TransformerModel(nn.Module):
    def __init__(self, input_dim=1, d_model=64, nhead=4, num_layers=2, output_dim=1):
        """
        PyTorch Transformer Model
        Default input_dim=1 (Sadece Close Price kullanılırsa)
        """
        super(TransformerModel, self).__init__()
        self.model_type = 'Transformer'
        
        # Basit bir Input projeksiyonu
        self.input_net = nn.Linear(input_dim, d_model)
        
        # Transformer Encoder
        self.encoder_layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=nhead, batch_first=False)
        self.transformer_encoder = nn.TransformerEncoder(self.encoder_layer, num_layers=num_layers)
        
        # Output Decoder
        self.decoder = nn.Linear(d_model, output_dim)
        
        self.init_weights()
        logger.info("🧠 Transformer Model Initialized (PyTorch)")

    def init_weights(self):
        initrange = 0.1
        self.decoder.bias.data.zero_()
        self.decoder.weight.data.uniform_(-initrange, initrange)

    def forward(self, src):
        """
        Forward Pass
        src shape: [batch_size, seq_len, input_dim]
        """
        # [Batch, Seq, Feature] -> [Seq, Batch, Feature] (Transformer default)
        # Ancak önce input projection
        src = self.input_net(src) # [Batch, Seq, d_model]
        
        src = src.permute(1, 0, 2) # [Seq, Batch, d_model]
        
        output = self.transformer_encoder(src)
        
        # Son zaman adımının çıktısı (Many-to-One)
        last_output = output[-1, :, :] # [Batch, d_model]
        
        prediction = self.decoder(last_output)
        return prediction

    def predict(self, recent_candles: list) -> float:
        """
        SignalGenerator uyumlu tahmin metodu.
        
        Args:
           recent_candles: Close fiyatlarının listesi (Last N)
        Returns:
           float: Tahmin edilen sonraki fiyat
        """
        if not recent_candles or len(recent_candles) < 3:
            return recent_candles[-1] if recent_candles else 0.0
            
        try:
            # --- NORMALIZATION (Percentage Returns) ---
            # Neural Networks ham fiyatlarla çalışamaz!
            # Log/Yüzde değişimlerini kullanıyoruz
            prices = np.array(recent_candles, dtype=np.float32)
            
            # Yüzde değişimleri hesapla (ilk eleman kaybolur)
            returns = np.diff(prices) / prices[:-1]
            
            # Çok küçük/büyük değerleri sınırla (numerical stability)
            returns = np.clip(returns, -0.1, 0.1)
            
            # Input Tensor (Normalized)
            # Shape: [Batch=1, Seq=N-1, Feature=1]
            data_arr = returns.reshape(1, -1, 1)
            src = torch.from_numpy(data_arr)
            
            # Eval mode
            self.eval()
            with torch.no_grad():
                pred_tensor = self.forward(src)
                # Çıktı: Tahmin edilen bir sonraki periyodun yüzde değişimi
                predicted_return = pred_tensor.item()
                
            # Tahmin edilen dönüşü sınırla
            predicted_return = np.clip(predicted_return, -0.05, 0.05)
            
            # Ham fiyata dönüştür
            last_price = recent_candles[-1]
            prediction = last_price * (1 + predicted_return)
                
            return prediction
            
        except Exception as e:
            logger.error(f"Transformer Prediction Error: {e}")
            # Hata durumunda son fiyatı döndür (Neutral etki)
            return recent_candles[-1] if recent_candles else 0.0
