# ============================================================
# NEXUS PRO - Main Entry Point
# ============================================================
# Modüler, AI-destekli crypto trading botu
# Hedef: 100 sinyal/gün, %80+ win rate
# ============================================================

import asyncio
import logging
import signal
import sys
from typing import Optional
from datetime import datetime

# Nexus Pro modülleri
from config import settings, load_settings_from_env
from core import DataProvider
from ai import (
    SignalGenerator, 
    TechnicalAnalyzer,
    ConfidenceScorer,
    MarketRegimeDetector,
    SignalType
)
# Try optimized HMM
try:
    from ai.hmm_regime import HammMarketRegime
    HMM_AVAILABLE = True
except ImportError:
    HMM_AVAILABLE = False
from risk import RiskManager
from core.order_executor import OrderExecutor
from ai.rl_agent import RLAgent
from api import app, broadcast_signal, broadcast_stats, broadcast_log
import uvicorn

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("nexus_pro")

class NexusPro:
    """
    NEXUS PRO Trading Bot
    
    Ana bileşenler:
    - DataProvider: Gerçek zamanlı veri
    - SignalGenerator: Teknik analiz + sinyal üretimi
    - ConfidenceScorer: Multi-indicator güven puanlama
    - MarketRegimeDetector: Bull/Bear/Sideways tespiti
    - RiskManager: Pozisyon + risk yönetimi
    """
    
    def __init__(self):
        load_settings_from_env()
        
        # Bileşenler
        self.data_provider = DataProvider()
        self.signal_generator = SignalGenerator(settings.trading)
        self.confidence_scorer = ConfidenceScorer()
        self.regime_detector = MarketRegimeDetector()
        
        # HMM Initialization
        self.hmm_detector = HammMarketRegime() if HMM_AVAILABLE else None
        if HMM_AVAILABLE:
            logger.info("🧠 HMM AI Engine Active")
        else:
            logger.warning("⚠️ HMM not available (install hmmlearn). Using Rule-based.")
            
        self.risk_manager = RiskManager(settings.risk)
        
        # Execution Engine
        self.order_executor = OrderExecutor(
            api_key=settings.exchange.api_key,
            api_secret=settings.exchange.api_secret,
            testnet=settings.exchange.testnet
        )
        # Connect explicitly later or lazy load
        
        # RL Agent
        self.rl_agent = RLAgent()
        self.rl_agent.load()
        
        # State
        self._running = False
        self.signals_today = 0
        self.symbols: list = []
        self.recent_signals: list = [] # For GUI
        
        # Inject self into API
        import api.server
        api.server.bot_instance = self
        
        logger.info("🚀 NEXUS PRO initialized")
        
    async def start(self):
        """Botu başlat"""
        logger.info("=" * 50)
        logger.info("🚀 NEXUS PRO - Starting...")
        logger.info("=" * 50)
        
        self._running = True
        
        # Connect to Exchange
        if self.order_executor:
            await self.order_executor.connect()
        
        # En volatil sembolleri al
        async with self.data_provider._session or await self._init_session():
            self.symbols = await self.data_provider.get_top_volatile_symbols(
                limit=settings.trading.max_symbols
            )
            
        if not self.symbols:
            self.symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]  # Fallback
            
        logger.info(f"📊 {len(self.symbols)} sembol izlenecek")
        logger.info(f"🎯 Hedef: {settings.trading.max_signals_per_day} sinyal/gün")
        logger.info(f"📈 Min Confidence: {settings.trading.min_confidence * 100:.0f}%")
        
        # WebSocket'e abone ol
        self.data_provider.subscribe(self.on_candle_close)
        
        # Heartbeat loop
        asyncio.create_task(self._heartbeat_loop())
        
        # Ana döngü
        try:
            await self.data_provider.start(
                symbols=self.symbols,
                timeframes=[settings.trading.primary_timeframe]
            )
        except asyncio.CancelledError:
            logger.info("Shutdown signal received")
        finally:
            await self.stop()
            
    async def _init_session(self):
        """Session başlat"""
        import aiohttp
        self.data_provider._session = aiohttp.ClientSession()
        return self.data_provider._session
            
        
    async def _heartbeat_loop(self):
        """Periyodik durum güncellemesi"""
        while self._running:
            await asyncio.sleep(60) # Her 1 dakikada bir
            current_time = datetime.now().strftime("%H:%M:%S")
            logger.info(f"🟢 Sistem Aktif | {len(self.symbols)} Sembol taranıyor... | {current_time}")
            
    async def stop(self):
        """Botu durdur"""
        logger.info("🛑 NEXUS PRO durduruluyor...")
        self._running = False
        await self.data_provider.stop()
        
        if self.order_executor:
            await self.order_executor.disconnect()
        
        # Günlük özet
        stats = self.risk_manager.get_daily_stats()
        logger.info("=" * 50)
        logger.info("📊 GÜNLÜK ÖZET:")
        logger.info(f"   Toplam Sinyal: {self.signals_today}")
        logger.info(f"   İşlem: {stats['trades']} (W:{stats['wins']} L:{stats['losses']})")
        logger.info(f"   Win Rate: {stats['win_rate']*100:.1f}%")
        logger.info(f"   PnL: {stats['pnl']:.2f}")
        logger.info("=" * 50)
        
    async def on_candle_close(self, symbol: str, timeframe: str, candle):
        """Mum kapanış event handler"""
        if not self._running:
            return
            
        # Günlük sinyal limiti
        if self.signals_today >= settings.trading.max_signals_per_day:
            # Sinyal limiti dolsa bile pozisyonları yönetmeye devam et
            pass
            
        # Pozisyon Kontrolü (Her mum kapanışında)
        await self.manage_positions(symbol, candle.close)
            
        if self.signals_today >= settings.trading.max_signals_per_day:
             return
            
        try:
            await self.analyze_symbol(symbol)
        except Exception as e:
            logger.error(f"Analiz hatası {symbol}: {e}")
            await broadcast_log(f"ERROR: {symbol} analiz hatası: {str(e)}")
            
    async def analyze_symbol(self, symbol: str):
        """Sembölü analiz et ve sinyal üret"""
        # Veri al
        df = self.data_provider.get_candles(symbol, settings.trading.primary_timeframe)
        if df is None or len(df) < 50:
            # Sessizce atla - bu sembol için yeterli veri yok
            return
            
        # Göstergeleri hesapla
        df = TechnicalAnalyzer.calculate_indicators(df)
        
        # 1. Market Regime Analysis
        # HMM or Classic?
        latest = df.iloc[-1] # Get the latest candle for regime detection
        
        # HMM kullanımı için 1h verisi kontrol et
        klines_1h = self.data_provider.get_klines(symbol, '1h')
        use_hmm = self.hmm_detector and klines_1h is not None and len(klines_1h) > 100
        
        if use_hmm:
             hmm_regime, hmm_prob = self.hmm_detector.predict_regime(klines_1h)
             # Basic usage: If HMM says SIDEWAYS, warn user
             regime_result = self.regime_detector.detect(latest) # Still use classic for details
             if hmm_regime != "UNKNOWN":
                 regime_result.regime_name = f"{hmm_regime} (HMM)"
        else:
             regime_result = self.regime_detector.detect(latest)
            
        logger.debug(f"🔍 {symbol} Rejim: {regime_result.regime} (Adx: {regime_result.adx:.1f})")
        
        market_trend = regime_result.regime.value.replace("STRONG_", "")
        
        # Sinyal üret
        signal = self.signal_generator.generate_signal(symbol, df, market_trend)
        if signal is None or signal.signal_type == SignalType.NONE:
            return
            
        # Confidence skoru hesapla
        confidence_result = self.confidence_scorer.calculate_score(
            signal_type=signal.signal_type.value,
            features=signal.features,
            market_trend=market_trend,
            symbol=symbol
        )
        
        # Eşik kontrolü
        if not confidence_result.passed:
            logger.debug(f"❌ {symbol} reddedildi: {confidence_result.total_score}/100")
            return
            
        # Pozisyon açılabilir mi?
        can_open, reason = self.risk_manager.can_open_position(symbol)
        if not can_open:
            logger.warning(f"⚠️ {symbol}: {reason}")
            await broadcast_log(f"WARNING: {symbol} blocked by risk manager: {reason}")
            return
            
        # SİNYAL ONAYLANDI!
        self.signals_today += 1
        
        final_confidence = confidence_result.total_score / 100
        
        # Log to API
        signal_data = {
            "symbol": symbol,
            "type": signal.signal_type.value,
            "confidence": confidence_result.total_score,
            "regime": regime_result.regime.value,
            "entry": signal.entry_price,
            "sl": signal.stop_loss,
            "tp": signal.take_profit,
            "reason": confidence_result.reasoning,
            "timestamp": datetime.now().isoformat()
        }
        self.recent_signals.insert(0, signal_data)
        self.recent_signals = self.recent_signals[:50] # Keep last 50
        
        await broadcast_signal(signal_data)
        await broadcast_log(f"SIGNAL: {symbol} {signal.signal_type.value} ({confidence_result.total_score}/100)")
        
        # Update Stats on API
        stats = self.risk_manager.get_daily_stats()
        stats["signals_today"] = self.signals_today
        await broadcast_stats(stats)
        
        logger.info("=" * 50)
        logger.info(f"🎯 SİNYAL #{self.signals_today}: {symbol} {signal.signal_type.value}")
        logger.info(f"   📊 Confidence: {confidence_result.total_score}/100")
        logger.info(f"   📈 Rejim: {regime_result.regime.value} (ADX: {regime_result.adx:.1f})")
        logger.info(f"   💰 Entry: {signal.entry_price:.4f}")
        logger.info(f"   🛑 SL: {signal.stop_loss:.4f} | TP: {signal.take_profit:.4f}")
        logger.info(f"   📝 Reason: {confidence_result.reasoning}")
        logger.info("=" * 50)
        
        # TODO: Gerçek trade execution
        await self.execute_trade(symbol, signal, regime_result, final_confidence, high_risk_mode=(market_trend=="VOLATILE"))
        
    async def execute_trade(self, symbol: str, signal, regime, confidence: float, high_risk_mode: bool):
        """
        İşlemi gerçekleştir:
        1. RL Ajanından Risk Profili al
        2. Pozisyon büyüklüğü ve SL/TP hesapla
        3. Borsaya emir ilet (OrderExecutor)
        4. Risk Yöneticisine kaydet
        """
        # 1. RL Risk Profili
        # Observation: [RSI, ATR_Pct, Volatility, Trend, Drawdown]
        # Basitleştirilmiş feature vector
        obs = [
            signal.features.get('rsi_14', 50) / 100.0,
            signal.features.get('atr_pct', 1.0) / 5.0,
            signal.features.get('bb_width', 2.0) / 10.0,
            signal.features.get('adx_14', 20) / 100.0,
            self.risk_manager.daily_stats.current_drawdown
        ]
        
        # Eğer RL Ajanı varsa sor, yoksa Dengeli (1)
        risk_profile = 1
        if self.rl_agent:
            risk_profile = self.rl_agent.predict_risk_profile(obs)
            
        logger.info(f"🧠 RL Risk Profile: {risk_profile} (0=Conservative, 1=Balanced, 2=Aggressive)")
        
        # Risk Profiline göre Çarpanlar
        # 0: Sıkı SL (1.0 ATR)
        # 1: Normal SL (1.5 ATR)
        # 2: Geniş SL (2.0 ATR)
        sl_multipliers = {0: 1.0, 1: 1.5, 2: 2.0}
        sl_mult = sl_multipliers.get(risk_profile, 1.5)
        
        # SL/TP Yeniden Hesapla (Sinyalden gelen varsayılanı ezebiliriz)
        atr = signal.features.get('atr_14', 0)
        entry_price = signal.entry_price
        
        if atr > 0:
            sl_price, tp_price = self.risk_manager.calculate_sl_tp(
                entry_price=entry_price,
                direction=signal.signal_type.value,
                atr=atr,
                atr_multiplier=sl_mult
            )
        else:
            sl_price, tp_price = signal.stop_loss, signal.take_profit
            
        # 2. Pozisyon Büyüklüğü
        balance = 1000.0 # TODO: Borsa bakiyesini çek (self.order_executor.get_balance)
        quantity = self.risk_manager.calculate_position_size(
            account_balance=balance, 
            entry_price=entry_price, 
            stop_loss=sl_price, 
            confidence=confidence
        )
        
        # 3. Emir İletimi (OrderExecutor)
        if self.order_executor:
            # Side: BUY -> LONG, SELL -> SHORT (Binance Futures için BUY/SELL yeterli)
            side = signal.signal_type.value # "BUY" or "SELL"
            
            logger.info(f"🚀 Executing {side} {symbol} Size: {quantity:.4f}")
            
            order = await self.order_executor.place_limit_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=entry_price,
                post_only=True # Maker stratejisi
            )
            
            if order:
                # 4. Başarılı ise Risk Yöneticisine kaydet
                self.risk_manager.open_position(
                    symbol=symbol,
                    direction=side,
                    entry_price=entry_price,
                    quantity=quantity,
                    stop_loss=sl_price,
                    take_profit=tp_price
                )
                await broadcast_log(f"TRADE EXECUTED: {symbol} ID: {order['orderId']}")
            else:
                logger.error(f"❌ Order execution failed for {symbol}")
                await broadcast_log(f"ERROR: Order execution failed for {symbol}")
        else:
             logger.warning("⚠️ No OrderExecutor active. Paper trading mode (Simulated).")
             # Simulate
             self.risk_manager.open_position(
                symbol=symbol,
                direction=signal.signal_type.value,
                entry_price=entry_price,
                quantity=quantity,
                stop_loss=sl_price,
                take_profit=tp_price
        
    async def manage_positions(self, symbol: str, current_price: float):
        """Açık pozisyonları izle ve SL/TP kontrolü yap"""
        if symbol not in self.risk_manager.open_positions:
            return

        pos = self.risk_manager.open_positions[symbol]
        
        # TP Kontrol (Basit)
        tp_hit = False
        if pos.direction == "BUY" and current_price >= pos.take_profit:
            tp_hit = True
        elif pos.direction == "SELL" and current_price <= pos.take_profit:
            tp_hit = True
            
        # SL Kontrol (Basit)
        sl_hit = False
        if pos.direction == "BUY" and current_price <= pos.stop_loss:
            sl_hit = True
        elif pos.direction == "SELL" and current_price >= pos.stop_loss:
            sl_hit = True
                 
        if tp_hit or sl_hit:
            reason = "TAKE_PROFIT" if tp_hit else "STOP_LOSS"
            logger.info(f"⚡ {reason} Triggered for {symbol}. Price: {current_price}")
            
            # Close Position
            await self.close_trade(symbol, pos, current_price, reason)

    async def close_trade(self, symbol: str, pos, price: float, reason: str):
        """İşlemi kapat"""
        # 1. Close on Exchange (If connected)
        if self.order_executor and not self.order_executor.simulation_mode:
             logger.info(f"Closing {symbol} on exchange via MARKET order...")
             # TODO: Implement complete close logic with OrderExecutor (Market Order)
             # For now we assume simulation or manual close if API active
             pass 
        
        # 2. Update Risk Manager
        self.risk_manager.close_position(symbol, price)
        
        # 3. Broadcast
        pnl = (price - pos.entry_price) * pos.quantity if pos.direction == "BUY" else (pos.entry_price - price) * pos.quantity
        pnl_str = f"{pnl:.2f}"
        
        log_msg = f"TRADE CLOSED: {symbol} | {reason} | PnL: {pnl_str} USDT"
        await broadcast_log(log_msg)
        
        # 4. Update stats
        stats = self.risk_manager.get_daily_stats()
        await broadcast_stats(stats)
        
        logger.info("=" * 50)
        logger.info(log_msg)
        logger.info("=" * 50)

def main():
    """Ana giriş noktası"""
    print("""
    ╔═══════════════════════════════════════════════════════╗
    ║                                                       ║
    ║   ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗         ║
    ║   ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝         ║
    ║   ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗         ║
    ║   ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║         ║
    ║   ██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║         ║
    ║   ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝         ║
    ║                                                       ║
    ║              P R O   T R A D I N G   B O T            ║
    ║                                                       ║
    ║   🎯 Target: 100 signals/day | 80%+ win rate          ║
    ║   📊 Modular | AI-Powered | Risk-Managed              ║
    ║                                                       ║
    ╚═══════════════════════════════════════════════════════╝
    """)
    
    bot = NexusPro()
    
    # Signal handler
    def signal_handler(sig, frame):
        logger.info("Interrupt received, shutting down...")
        asyncio.create_task(bot.stop())
        sys.exit(0)
        
    signal.signal(signal.SIGINT, signal_handler)
    
    # Run
    try:
        # Create config for uvicorn
        config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
        server = uvicorn.Server(config)
        
        # Run bot and server concurrently
        loop = asyncio.get_event_loop()
        loop.create_task(bot.start())
        loop.run_until_complete(server.serve())
        
    except KeyboardInterrupt:
        pass
        
if __name__ == "__main__":
    main()
