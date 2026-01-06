# ============================================================
# NEXUS PRO - Risk Manager
# ============================================================
# Pozisyon boyutlandırma, SL/TP, Drawdown koruma
# ============================================================

import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, date
import sqlite3
import json # Kept for potential secondary usage or removing later if fully replaced
import os

logger = logging.getLogger("nexus_pro.risk")

@dataclass
class Position:
    """Açık pozisyon"""
    symbol: str
    direction: str  # "LONG" veya "SHORT"
    entry_price: float
    quantity: float
    stop_loss: float
    take_profit: float
    entry_time: datetime
    pnl: float = 0.0

@dataclass
class DailyStats:
    """Günlük istatistikler"""
    date: str
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0

class RiskManager:
    """
    Risk Yönetimi
    
    Özellikler:
    - Dinamik pozisyon boyutlandırma
    - ATR bazlı SL/TP
    - Günlük drawdown limiti
    - Max açık pozisyon limiti
    """
    
    def __init__(
        self,
        settings=None,  # Accept RiskSettings object
        max_position_size: float = 0.02,
        max_open_positions: int = 5,
        max_daily_drawdown: float = 0.10,
        default_sl_percent: float = 1.0,
        default_tp_percent: float = 2.0
    ):
        # If settings object provided, extract values from it
        if settings is not None:
            self.max_position_size = getattr(settings, 'max_position_size', max_position_size)
            self.max_open_positions = getattr(settings, 'max_open_positions', max_open_positions)
            self.max_daily_drawdown = getattr(settings, 'max_daily_drawdown', max_daily_drawdown)
            self.default_sl_percent = getattr(settings, 'default_sl_percent', default_sl_percent)
            self.default_tp_percent = getattr(settings, 'default_tp_percent', default_tp_percent)
        else:
            self.max_position_size = max_position_size
            self.max_open_positions = max_open_positions
            self.max_daily_drawdown = max_daily_drawdown
            self.default_sl_percent = default_sl_percent
            self.default_tp_percent = default_tp_percent
        
        self.open_positions: Dict[str, Position] = {}
        self.daily_stats = DailyStats(date=str(date.today()))
        self.is_paused = False
        
        self._init_db()
        self._load_state()
        
    def _init_db(self):
        """SQLite veritabanını başlat"""
        try:
            self.conn = sqlite3.connect('risk.db', check_same_thread=False)
            self.cursor = self.conn.cursor()
            
            # Daily Stats Table
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_stats (
                    date TEXT PRIMARY KEY,
                    total_trades INTEGER,
                    wins INTEGER,
                    losses INTEGER,
                    total_pnl REAL,
                    max_drawdown REAL,
                    current_drawdown REAL,
                    is_paused INTEGER
                )
            ''')
            
            # Open Positions Table
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS open_positions (
                    symbol TEXT PRIMARY KEY,
                    direction TEXT,
                    entry_price REAL,
                    quantity REAL,
                    stop_loss REAL,
                    take_profit REAL,
                    entry_time TEXT,
                    pnl REAL
                )
            ''')
            self.conn.commit()
        except Exception as e:
            logger.error(f"DB Init Failed: {e}")

    def _save_state(self):
        """Durumu SQLite'a kaydet"""
        try:
            # 1. Save Daily Stats
            ds = self.daily_stats
            self.cursor.execute('''
                INSERT OR REPLACE INTO daily_stats 
                (date, total_trades, wins, losses, total_pnl, max_drawdown, current_drawdown, is_paused)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                ds.date, ds.total_trades, ds.wins, ds.losses, 
                ds.total_pnl, ds.max_drawdown, ds.current_drawdown, 
                1 if self.is_paused else 0
            ))
            
            # 2. Sync Positions (Basit yöntem: Hepsini silip yeniden ekle veya tek tek upsert)
            # Burada tek tek DELETE + INSERT yapıyorum temizlik için
            self.cursor.execute("DELETE FROM open_positions")
            
            for symbol, pos in self.open_positions.items():
                self.cursor.execute('''
                    INSERT INTO open_positions 
                    (symbol, direction, entry_price, quantity, stop_loss, take_profit, entry_time, pnl)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    pos.symbol, pos.direction, pos.entry_price, pos.quantity,
                    pos.stop_loss, pos.take_profit, pos.entry_time.isoformat(),
                    pos.pnl
                ))
                
            self.conn.commit()
            
        except Exception as e:
            logger.error(f"State kaydetme hatası (SQLite): {e}")
            
    def _load_state(self):
        """Durumu SQLite'dan yükle"""
        if not hasattr(self, 'cursor'):
             return

        try:
            today_str = str(date.today())
            
            # 1. Load Daily Stats
            self.cursor.execute("SELECT * FROM daily_stats WHERE date=?", (today_str,))
            row = self.cursor.fetchone()
            
            if row:
                # Row order matches CREATE TABLE
                self.daily_stats = DailyStats(
                    date=row[0],
                    total_trades=row[1],
                    wins=row[2],
                    losses=row[3],
                    total_pnl=row[4],
                    max_drawdown=row[5],
                    current_drawdown=row[6]
                )
                self.is_paused = bool(row[7])
            else:
                # No record for today, start fresh
                self.daily_stats = DailyStats(date=today_str)
                
            # 2. Load Open Positions
            self.cursor.execute("SELECT * FROM open_positions")
            rows = self.cursor.fetchall()
            
            self.open_positions = {}
            for r in rows:
                # symbol, direction, entry_price, quantity, stop_loss, take_profit, entry_time, pnl
                pos = Position(
                    symbol=r[0],
                    direction=r[1],
                    entry_price=r[2],
                    quantity=r[3],
                    stop_loss=r[4],
                    take_profit=r[5],
                    entry_time=datetime.fromisoformat(r[6]),
                    pnl=r[7]
                )
                self.open_positions[pos.symbol] = pos
                
            logger.info(f"Loaded {len(self.open_positions)} open positions from DB.")
                
        except Exception as e:
            logger.error(f"State yükleme hatası (SQLite): {e}")

    def calculate_sl_tp(self, entry_price: float, direction: str, atr: float, atr_multiplier: float = 1.5) -> Tuple[float, float]:
        """ATR bazlı Stop Loss ve Take Profit hesapla"""
        sl_distance = atr * atr_multiplier
        tp_distance = atr * atr_multiplier * 2  # 2:1 R/R ratio
        
        if direction.upper() in ["BUY", "LONG"]:
            stop_loss = entry_price - sl_distance
            take_profit = entry_price + tp_distance
        else:  # SELL / SHORT
            stop_loss = entry_price + sl_distance
            take_profit = entry_price - tp_distance
            
        return stop_loss, take_profit
    
    def calculate_position_size(self, account_balance: float, entry_price: float, stop_loss: float, confidence: float = 0.7) -> float:
        """Dinamik pozisyon boyutlandırma"""
        # Risk miktarı = Bakiye * Max Pozisyon Oranı * Güven
        risk_amount = account_balance * self.max_position_size * confidence
        
        # SL uzaklığı
        sl_distance = abs(entry_price - stop_loss)
        if sl_distance == 0:
            sl_distance = entry_price * (self.default_sl_percent / 100)
        
        # Pozisyon boyutu = Risk / SL Uzaklığı
        position_size = risk_amount / sl_distance
        
        # Makul bir üst limit koy
        max_qty = (account_balance * 0.1) / entry_price  # Max %10 bakiye
        return min(position_size, max_qty)
    
    def can_open_position(self, symbol: str) -> Tuple[bool, str]:
        """Pozisyon açılabilir mi kontrol et"""
        # Duraklatılmış mı?
        if self.is_paused:
            return False, "Bot duraklatılmış (Drawdown limiti)"
            
        # Max pozisyon sayısı
        if len(self.open_positions) >= self.max_open_positions:
            return False, f"Max pozisyon sayısı aşıldı ({self.max_open_positions})"
            
        # Aynı sembölde açık pozisyon var mı?
        if symbol in self.open_positions:
            return False, f"{symbol} için zaten açık pozisyon var"
            
        # Günlük drawdown limiti
        if self.daily_stats.current_drawdown >= self.max_daily_drawdown:
            self.is_paused = True
            return False, f"Günlük drawdown limiti aşıldı ({self.max_daily_drawdown*100:.1f}%)"
            
        return True, "OK"
    
    def open_position(self, symbol: str, direction: str, entry_price: float, quantity: float, stop_loss: float, take_profit: float):
        """Yeni pozisyon aç ve kaydet"""
        pos = Position(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            quantity=quantity,
            stop_loss=stop_loss,
            take_profit=take_profit,
            entry_time=datetime.now()
        )
        self.open_positions[symbol] = pos
        self._save_state()
        logger.info(f"📈 Pozisyon Açıldı: {direction} {symbol} @ {entry_price:.4f}")
        
    def close_position(self, symbol: str, exit_price: float):
        """Pozisyonu kapat ve istatistikleri güncelle"""
        if symbol not in self.open_positions:
            return
            
        pos = self.open_positions[symbol]
        
        # PnL Hesapla
        if pos.direction.upper() in ["BUY", "LONG"]:
            pnl = (exit_price - pos.entry_price) * pos.quantity
        else:
            pnl = (pos.entry_price - exit_price) * pos.quantity
            
        # İstatistikleri güncelle
        self.daily_stats.total_trades += 1
        self.daily_stats.total_pnl += pnl
        
        if pnl > 0:
            self.daily_stats.wins += 1
        else:
            self.daily_stats.losses += 1
            
        # Drawdown güncelle
        if pnl < 0:
            self.daily_stats.current_drawdown += abs(pnl) / 1000  # Basitleştirilmiş
            if self.daily_stats.current_drawdown > self.daily_stats.max_drawdown:
                self.daily_stats.max_drawdown = self.daily_stats.current_drawdown
        
        del self.open_positions[symbol]
        self._save_state()
        logger.info(f"📉 Pozisyon Kapatıldı: {symbol} PnL: {pnl:.2f}")
        
    def get_daily_stats(self) -> Dict:
        """Günlük istatistikleri döndür"""
        ds = self.daily_stats
        win_rate = ds.wins / ds.total_trades if ds.total_trades > 0 else 0
        return {
            "trades": ds.total_trades,
            "wins": ds.wins,
            "losses": ds.losses,
            "pnl": ds.total_pnl,
            "win_rate": win_rate,
            "max_drawdown": ds.max_drawdown,
            "current_drawdown": ds.current_drawdown,
            "is_paused": self.is_paused
        }

    def __del__(self):
        """Destructor to close connection"""
        if hasattr(self, 'conn'):
            self.conn.close()
