# ============================================================
# NEXUS PRO - GOD MODE DASHBOARD (Tkinter Edition)
# ============================================================

import customtkinter as ctk
import threading
import time
import queue
from datetime import datetime
import asyncio
import sys
import os

# Path hack
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import NexusPro
from config import settings

import logging

# --- LOGGING SETUP ---
class QueueHandler(logging.Handler):
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        msg = self.format(record)
        self.log_queue.put(msg)

# --- THEME SETUP ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

# --- MAIN DASHBOARD CLASS ---
class NexusDashboard(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Logging Queue
        self.log_queue = queue.Queue()
        self.queue_handler = QueueHandler(self.log_queue)
        self.queue_handler.setFormatter(logging.Formatter('%(asctime)s | %(message)s', datefmt='%H:%M:%S'))
        
        # Inject Logging
        root_logger = logging.getLogger()
        root_logger.addHandler(self.queue_handler)
        root_logger.setLevel(logging.INFO)

        # Window Config
        self.title("NEXUS PRO | HFT GOD MODE ⚡")
        self.geometry("1280x800")
        
        # --- LAYOUT CONFIGURATION ---
        self.grid_columnconfigure(0, weight=1) # Main Content
        self.grid_columnconfigure(1, weight=0) # Sidebar (Right)
        
        self.grid_rowconfigure(0, weight=0) # Header
        self.grid_rowconfigure(1, weight=1) # Body
        self.grid_rowconfigure(2, weight=0) # Footer
        
        # ================= HEADER =================
        self.header_frame = ctk.CTkFrame(self, height=60, corner_radius=0, fg_color="#1a1a1a")
        self.header_frame.grid(row=0, column=0, columnspan=2, sticky="ew")
        
        self.lbl_title = ctk.CTkLabel(self.header_frame, text="NEXUS PRO v3.0", font=("Roboto", 24, "bold"), text_color="#00ff00")
        self.lbl_title.pack(side="left", padx=20, pady=10)
        
        self.lbl_mode = ctk.CTkLabel(self.header_frame, text="⚡ HFT GOD MODE ACTIVE", font=("Roboto", 14, "bold"), text_color="cyan")
        self.lbl_mode.pack(side="left", padx=20)
        
        self.lbl_pnl = ctk.CTkLabel(self.header_frame, text="PnL: 0.00 USDT", font=("Roboto", 18, "bold"), text_color="white")
        self.lbl_pnl.pack(side="right", padx=20)
        
        self.lbl_status = ctk.CTkLabel(self.header_frame, text="OFFLINE", font=("Roboto", 14, "bold"), text_color="red")
        self.lbl_status.pack(side="right", padx=20)

        # ================= BODY =================
        
        # --- LEFT PANEL (SIGNALS & LOGS) ---
        self.left_panel = ctk.CTkFrame(self, fg_color="transparent")
        self.left_panel.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.left_panel.grid_rowconfigure(0, weight=1) # Signals
        self.left_panel.grid_rowconfigure(1, weight=1) # Logs
        self.left_panel.grid_columnconfigure(0, weight=1)

        # 1. Signal Feed
        self.signal_frame = ctk.CTkFrame(self.left_panel)
        self.signal_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        
        ctk.CTkLabel(self.signal_frame, text="📡 LIVE SIGNALS", font=("Roboto", 14, "bold")).pack(pady=5, anchor="w", padx=10)
        self.signal_scroll = ctk.CTkScrollableFrame(self.signal_frame, fg_color="#2b2b2b")
        self.signal_scroll.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 2. Terminal Logs
        self.log_frame = ctk.CTkFrame(self.left_panel)
        self.log_frame.grid(row=1, column=0, sticky="nsew")
        
        ctk.CTkLabel(self.log_frame, text="📟 SYSTEM TERMINAL", font=("Roboto", 14, "bold")).pack(pady=5, anchor="w", padx=10)
        self.log_textbox = ctk.CTkTextbox(self.log_frame, font=("Consolas", 12), fg_color="#000000", text_color="#00ff00")
        self.log_textbox.pack(fill="both", expand=True, padx=5, pady=5)
        self.log_textbox.configure(state="disabled")

        # --- RIGHT PANEL (STATS & POSITIONS & CONTROLS) ---
        self.right_panel = ctk.CTkFrame(self, width=350, corner_radius=0)
        self.right_panel.grid(row=1, column=1, rowspan=2, sticky="nsew")
        
        # 1. HFT Gauges
        self.gauge_frame = ctk.CTkFrame(self.right_panel)
        self.gauge_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(self.gauge_frame, text="🧠 AI BRAIN", font=("Roboto", 16, "bold")).pack(pady=5)
        
        self.lbl_hmm = ctk.CTkLabel(self.gauge_frame, text="REGIME: UNKNOWN", font=("Roboto", 14), text_color="gray")
        self.lbl_hmm.pack(pady=2)
        
        self.lbl_ofi = ctk.CTkLabel(self.gauge_frame, text="market pressure: NEUTRAL", font=("Roboto", 12))
        self.lbl_ofi.pack(pady=2)
        
        # 2. Stats
        self.stats_frame = ctk.CTkFrame(self.right_panel)
        self.stats_frame.pack(fill="x", padx=10, pady=10)
        
        self.lbl_trades = ctk.CTkLabel(self.stats_frame, text="Trades: 0")
        self.lbl_trades.pack(pady=2)
        
        self.lbl_winrate = ctk.CTkLabel(self.stats_frame, text="Win Rate: 0%")
        self.lbl_winrate.pack(pady=2)
        
        # 3. Open Positions
        self.pos_frame = ctk.CTkFrame(self.right_panel)
        self.pos_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(self.pos_frame, text="💎 OPEN POSITIONS", font=("Roboto", 14, "bold")).pack(pady=5)
        self.pos_scroll = ctk.CTkScrollableFrame(self.pos_frame)
        self.pos_scroll.pack(fill="both", expand=True, padx=2, pady=2)
        
        # 4. Controls
        self.control_frame = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        self.control_frame.pack(fill="x", padx=10, pady=20, side="bottom")
        
        self.btn_start = ctk.CTkButton(self.control_frame, text="START ENGINE", fg_color="green", height=40, font=("Roboto", 14, "bold"), command=self.start_bot)
        self.btn_start.pack(fill="x", pady=5)
        
        self.btn_stop = ctk.CTkButton(self.control_frame, text="STOP", fg_color="gray", height=40, state="disabled", command=self.stop_bot)
        self.btn_stop.pack(fill="x", pady=5)
        
        self.btn_panic = ctk.CTkButton(self.control_frame, text="☢️ PANIC STOP", fg_color="#8B0000", hover_color="red", height=50, font=("Roboto", 16, "bold"), command=self.panic_stop)
        self.btn_panic.pack(fill="x", pady=(20, 5))
        
        # --- BOT INIT ---
        self.bot_thread = None
        self.bot = None
        self.loop = None
        
        # Start UI Update Loop
        self.after(100, self.update_ui)

    # --- LOGIC ---
    
    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_queue.put(f"[{timestamp}] {message}")

    def update_ui(self):
        # 1. Process Logs
        while not self.log_queue.empty():
            msg = self.log_queue.get()
            self.log_textbox.configure(state="normal")
            self.log_textbox.insert("end", msg + "\n")
            self.log_textbox.see("end")
            self.log_textbox.configure(state="disabled")
            
        # 2. Update Bot Stats (if running)
        if self.bot and self.bot._running:
            try:
                # HEADER
                stats = self.bot.risk_manager.get_daily_stats()
                pnl = stats['pnl']
                
                # Live PnL Calculation
                unrealized = 0
                for sym, pos in self.bot.risk_manager.open_positions.items():
                    ticker = self.bot.data_provider.get_ticker(sym)
                    curr = ticker['price'] if ticker else pos.entry_price
                    diff = (curr - pos.entry_price) if pos.direction == "BUY" else (pos.entry_price - curr)
                    unrealized += diff * pos.quantity
                
                total_pnl = pnl + unrealized
                color = "#00ff00" if total_pnl >= 0 else "#ff0000"
                self.lbl_pnl.configure(text=f"PnL: {total_pnl:.2f} USDT", text_color=color)
                
                self.lbl_trades.configure(text=f"Trades: {stats['trades']}")
                self.lbl_winrate.configure(text=f"Win Rate: {stats['win_rate']*100:.1f}%")
                
                # POSITIONS
                for w in self.pos_scroll.winfo_children(): w.destroy()
                
                for sym, pos in self.bot.risk_manager.open_positions.items():
                    f = ctk.CTkFrame(self.pos_scroll, fg_color="#333333")
                    f.pack(fill="x", pady=2)
                    
                    ticker = self.bot.data_provider.get_ticker(sym)
                    curr = ticker['price'] if ticker else pos.entry_price
                    diff = (curr - pos.entry_price) if pos.direction == "BUY" else (pos.entry_price - curr)
                    upnl = diff * pos.quantity
                    c_pnl = "green" if upnl >=0 else "red"
                    
                    ctk.CTkLabel(f, text=f"{sym} {pos.direction}", font=("Roboto", 12, "bold")).pack(side="left", padx=5)
                    ctk.CTkLabel(f, text=f"{upnl:.2f}", text_color=c_pnl, font=("Roboto", 12, "bold")).pack(side="right", padx=5)
                    
                # SIGNALS
                for w in self.signal_scroll.winfo_children(): w.destroy()
                for sig in self.bot.recent_signals[:10]: # Last 10
                    f = ctk.CTkFrame(self.signal_scroll, fg_color="#222222")
                    f.pack(fill="x", pady=2)
                    c = "green" if "BUY" in sig['type'] else "red"
                    ctk.CTkLabel(f, text=f"{sig['symbol']}", font=("Roboto", 12, "bold"), text_color="white").pack(side="left", padx=5)
                    ctk.CTkLabel(f, text=f"{sig['type']}", text_color=c).pack(side="left", padx=5)
                    ctk.CTkLabel(f, text=f"Conf: {sig['confidence']}", text_color="gray").pack(side="right", padx=5)
                    
            except Exception as e:
                pass
                
        self.after(500, self.update_ui)

    def start_bot(self):
        if self.bot_thread and self.bot_thread.is_alive(): return
        
        self.log("Initializing God Mode Engine...")
        self.lbl_status.configure(text="STARTING...", text_color="yellow")
        self.btn_start.configure(state="disabled", fg_color="gray")
        self.btn_stop.configure(state="normal", fg_color="red")
        
        self.bot_thread = threading.Thread(target=self._run_bot, daemon=True)
        self.bot_thread.start()
        
    def stop_bot(self):
        if self.bot:
            self.bot._running = False
            asyncio.run_coroutine_threadsafe(self.bot.stop(), self.loop)
            self.lbl_status.configure(text="STOPPING...", text_color="orange")
            
    def panic_stop(self):
        if not self.bot or not self.bot._running: return
        dialog = ctk.CTkInputDialog(text="TYPE 'YES' TO LIQUIDATE ALL POSITIONS:", title="PANIC STOP")
        res = dialog.get_input()
        if res and res.upper() == "YES":
            self.log("⚠️ PANIC STOP INITIATED")
            for sym, pos in list(self.bot.risk_manager.open_positions.items()):
                ticker = self.bot.data_provider.get_ticker(sym)
                price = ticker['price'] if ticker else pos.entry_price
                asyncio.run_coroutine_threadsafe(self.bot.close_trade(sym, pos, price, "PANIC"), self.loop)
            self.stop_bot()

    def _run_bot(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.bot = NexusPro()
        
        # Update Status to Online
        self.after(0, lambda: self.lbl_status.configure(text="ONLINE", text_color="#00ff00"))
        
        try:
            self.loop.run_until_complete(self.bot.start())
        except Exception as e:
            self.log(f"CRITICAL ERROR: {e}")
            self.after(0, lambda: self.lbl_status.configure(text="ERROR", text_color="red"))
        finally:
            self.log("Engine Shutdown.")
            self.after(0, lambda: self.lbl_status.configure(text="OFFLINE", text_color="grey"))
            self.after(0, lambda: self.btn_start.configure(state="normal", fg_color="green"))
            self.after(0, lambda: self.btn_stop.configure(state="disabled", fg_color="gray"))

if __name__ == "__main__":
    app = NexusDashboard()
    app.mainloop()
