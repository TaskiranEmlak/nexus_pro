# ============================================================
# NEXUS PRO - Desktop Dashboard (Tkinter)
# ============================================================
# Native desktop GUI for Nexus Pro
# Modern UI with CustomTkinter
# ============================================================

import customtkinter as ctk
import threading
import time
import queue
from datetime import datetime
import asyncio
from typing import Dict, List
import sys

# Add current path to sys.path to ensure imports work
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import NexusPro
from config import settings

# Global Styles
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

import logging

class QueueHandler(logging.Handler):
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        msg = self.format(record)
        self.log_queue.put(msg)

class NexusDashboard(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Setup Logging to Queue
        self.log_queue = queue.Queue()
        self.queue_handler = QueueHandler(self.log_queue)
        self.queue_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', datefmt='%H:%M:%S'))
        
        # Root logger setup
        root_logger = logging.getLogger()
        root_logger.addHandler(self.queue_handler)
        root_logger.setLevel(logging.INFO)

        self.title("NEXUS PRO | AI Trading Bot")
        self.geometry("1100x700")
        
        # Grid layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # --- Sidebar (Controls) ---
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        self.logo_label = ctk.CTkLabel(self.sidebar, text="NEXUS PRO\nTrading Bot", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))
        
        self.status_label = ctk.CTkLabel(self.sidebar, text="STATUS: OFFLINE", text_color="red")
        self.status_label.grid(row=1, column=0, padx=20, pady=10)
        
        self.start_btn = ctk.CTkButton(self.sidebar, text="START BOT", command=self.start_bot, fg_color="green", hover_color="darkgreen")
        self.start_btn.grid(row=2, column=0, padx=20, pady=10)
        
        self.stop_btn = ctk.CTkButton(self.sidebar, text="STOP BOT", command=self.stop_bot, fg_color="red", hover_color="darkred", state="disabled")
        self.stop_btn.grid(row=3, column=0, padx=20, pady=10)
        
        # Stats in sidebar
        self.stats_frame = ctk.CTkFrame(self.sidebar)
        self.stats_frame.grid(row=4, column=0, padx=10, pady=20, sticky="ew")
        
        self.stats_labels = {}
        for i, key in enumerate(["Signals", "Trades", "Win Rate", "PnL"]):
            lbl = ctk.CTkLabel(self.stats_frame, text=f"{key}: 0")
            lbl.pack(pady=5)
            self.stats_labels[key] = lbl

        # --- Main Area ---
        self.main_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_frame.grid_rowconfigure(1, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        # 1. TabView for Signals vs Positions
        self.tab_view = ctk.CTkTabview(self.main_frame)
        self.tab_view.grid(row=0, column=0, rowspan=2, sticky="nsew", pady=(0, 10))
        
        self.tab_signals = self.tab_view.add("Signals")
        self.tab_positions = self.tab_view.add("Open Positions")
        
        # Signals Tab
        self.signals_scroll = ctk.CTkScrollableFrame(self.tab_signals)
        self.signals_scroll.pack(fill="both", expand=True)
        
        # Positions Tab
        self.positions_scroll = ctk.CTkScrollableFrame(self.tab_positions)
        self.positions_scroll.pack(fill="both", expand=True)
        
        # 2. Log Console
        self.log_label = ctk.CTkLabel(self.main_frame, text="System Logs", font=ctk.CTkFont(size=16, weight="bold"))
        self.log_label.grid(row=2, column=0, sticky="w", pady=(20, 10))
        
        self.log_box = ctk.CTkTextbox(self.main_frame, height=150)
        self.log_box.grid(row=3, column=0, sticky="ew")
        self.log_box.configure(state="disabled")
        
        # Bot Threading
        self.bot_thread = None
        self.bot = None
        self.loop = None
        
        # Update Loop
        self.after(100, self.update_ui)

    def log(self, message):
        """Add message to log queue"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_queue.put(f"[{timestamp}] {message}")

    def update_ui(self):
        """Process specific GUI updates"""
        # Logs
        while not self.log_queue.empty():
            msg = self.log_queue.get()
            self.log_box.configure(state="normal")
            self.log_box.insert("end", msg + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
            
        # Stats polling (if bot running)
        if self.bot and self.bot._running:
            try:
                # 1. Update Stats & PnL
                stats = self.bot.risk_manager.get_daily_stats()
                open_positions = self.bot.risk_manager.open_positions
                
                # Calculate Unrealized PnL
                unrealized_pnl = 0.0
                
                # --- Update Positions Tab ---
                # Clear old (naive)
                for widget in self.positions_scroll.winfo_children():
                    widget.destroy()
                    
                for symbol, pos in open_positions.items():
                    ticker = self.bot.data_provider.get_ticker(symbol)
                    current_price = pos.entry_price
                    if ticker:
                        current_price = ticker['price']
                    
                    if pos.direction == "BUY":
                        pnl = (current_price - pos.entry_price) * pos.quantity
                    else:
                        pnl = (pos.entry_price - current_price) * pos.quantity
                    unrealized_pnl += pnl
                    
                    # Render Position Card
                    card = ctk.CTkFrame(self.positions_scroll)
                    card.pack(fill="x", pady=2, padx=2)
                    
                    pnl_color = "green" if pnl >= 0 else "red"
                    
                    # Row 1: Symbol + Side
                    r1 = ctk.CTkFrame(card, fg_color="transparent")
                    r1.pack(fill="x", padx=5, pady=2)
                    ctk.CTkLabel(r1, text=f"{symbol}", font=ctk.CTkFont(weight="bold")).pack(side="left")
                    ctk.CTkLabel(r1, text=f"{pos.direction}", text_color="cyan").pack(side="left", padx=10)
                    ctk.CTkLabel(r1, text=f"{pnl:.2f} USDT", text_color=pnl_color, font=ctk.CTkFont(weight="bold")).pack(side="right")
                    
                    # Row 2: Details
                    r2 = ctk.CTkFrame(card, fg_color="transparent")
                    r2.pack(fill="x", padx=5, pady=2)
                    ctk.CTkLabel(r2, text=f"Entry: {pos.entry_price:.4f} | Cur: {current_price:.4f}", font=ctk.CTkFont(size=10)).pack(side="left")
                    ctk.CTkLabel(r2, text=f"Qty: {pos.quantity:.3f}", font=ctk.CTkFont(size=10)).pack(side="right")
                
                total_pnl = stats['pnl'] + unrealized_pnl
                
                self.stats_labels["Signals"].configure(text=f"Signals: {self.bot.signals_today}")
                self.stats_labels["Trades"].configure(text=f"Trades: {stats['trades']} (Open: {len(open_positions)})")
                self.stats_labels["Win Rate"].configure(text=f"Win Rate: {stats['win_rate']*100:.1f}%")
                self.stats_labels["PnL"].configure(text=f"PnL: {total_pnl:.2f} USDT")
                
                # Check paused status
                status_text = "STATUS: PAUSED (RISK)" if stats['is_paused'] else "STATUS: ONLINE (SIMULATION)" if self.bot.order_executor.simulation_mode else "STATUS: ONLINE"
                color = "orange" if stats['is_paused'] else "cyan" if self.bot.order_executor.simulation_mode else "green"
                self.status_label.configure(text=status_text, text_color=color)
                
                # 2. Update Signal Feed
                # Clear old widgets (naive approach, better to diff but ok for now)
                for widget in self.signals_scroll.winfo_children():
                    widget.destroy()
                    
                for sig in self.bot.recent_signals:
                    # Simple card
                    card = ctk.CTkFrame(self.signals_scroll)
                    card.pack(fill="x", pady=2, padx=2)
                    
                    time_str = sig['timestamp'].split('T')[1][:8]
                    color = "green" if "BUY" in sig['type'] else "red"
                    
                    lbl = ctk.CTkLabel(card, text=f"{time_str} | {sig['symbol']} | {sig['type']} | Conf: {sig['confidence']}", text_color=color, font=ctk.CTkFont(weight="bold"))
                    lbl.pack(side="left", padx=5)
                    
                    price_lbl = ctk.CTkLabel(card, text=f"@{sig['entry']:.4f}")
                    price_lbl.pack(side="right", padx=5)
                    
            except Exception as e:
                # self.log(f"GUI Update Error: {e}") 
                pass
            
        self.after(1000, self.update_ui) # Refresh every 1s

    def start_bot(self):
        if self.bot_thread and self.bot_thread.is_alive():
            return
            
        self.log("Starting Nexus Pro engine...")
        self.start_btn.configure(state="disabled", fg_color="gray")
        self.stop_btn.configure(state="normal", fg_color="red")
        self.status_label.configure(text="STATUS: STARTING...", text_color="yellow")
        
        self.bot_thread = threading.Thread(target=self._run_bot_process, daemon=True)
        self.bot_thread.start()
        
    def stop_bot(self):
        if self.bot:
            self.log("Stopping bot...")
            self.bot._running = False
            asyncio.run_coroutine_threadsafe(self.bot.stop(), self.loop)
            
            self.status_label.configure(text="STATUS: STOPPING...", text_color="orange")
            self.start_btn.configure(state="normal", fg_color="green")
            self.stop_btn.configure(state="disabled", fg_color="gray")

    def _run_bot_process(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        self.bot = NexusPro()
        
        try:
            self.loop.run_until_complete(self.bot.start())
        except Exception as e:
            self.log(f"Bot crash: {e}")
        finally:
            # self.loop.close()
            self.log("Bot stopped.")

if __name__ == "__main__":
    app = NexusDashboard()
    app.mainloop()
