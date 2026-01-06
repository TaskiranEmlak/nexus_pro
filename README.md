# 🚀 NEXUS PRO - Trading Bot

## Modüler, AI-Destekli Crypto Trading Botu

### Hedefler
- 📊 100 sinyal/gün
- 🎯 %80+ win rate
- ⚡ Gerçek zamanlı öğrenme

### Proje Yapısı

```
nexus_pro/
├── config/           # Merkezi ayarlar
│   └── settings.py   # Tüm konfigürasyon
├── core/             # Altyapı
│   └── data_provider.py  # Binance WebSocket
├── ai/               # AI Engine
│   ├── signal_generator.py   # Teknik analiz + sinyal
│   ├── confidence_scorer.py  # Multi-indicator puanlama
│   └── market_regime.py      # Bull/Bear/Sideways tespiti
├── filters/          # Kalite filtreleri
│   └── quality_filter.py     # Trend + Volume filtresi
├── risk/             # Risk yönetimi
│   └── risk_manager.py       # SL/TP + Pozisyon boyutu
├── utils/            # Yardımcılar
│   └── logger.py             # Loglama
└── main.py           # Ana giriş noktası
```

### Başlangıç

```bash
# Bağımlılıkları yükle
pip install -r requirements.txt

# Environment variables ayarla
export BINANCE_API_KEY="your_key"
export BINANCE_API_SECRET="your_secret"

# Botu başlat
python main.py
```

### Confidence Scorer Mantığı

| Bileşen | Puan | Açıklama |
|---------|------|----------|
| Trend Uyumu | +25 | Sinyal trend yönünde mi? |
| RSI Doğrulama | +20 | RSI oversold/overbought? |
| MACD Onayı | +15 | MACD histogram pozitif/negatif? |
| Volume Desteği | +20 | Hacim ortalamanın üzerinde mi? |
| Geçmiş Performans | +20 | Bu sembolde kazanma oranı? |

**Toplam: 100 puan | Geçme eşiği: 65+**

### Risk Yönetimi

- Max pozisyon: %2
- Stop Loss: ATR × 1.5
- Take Profit: ATR × 3 (2:1 R/R)
- Günlük drawdown limiti: %10
