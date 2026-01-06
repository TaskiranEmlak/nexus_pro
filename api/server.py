# ============================================================
# NEXUS PRO - API Server
# ============================================================
# FastAPI backend for the web dashboard
# ============================================================

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import logging
from typing import List, Dict
import json
from datetime import datetime

# Import Nexus Pro components
from core import DataProvider
from risk import RiskManager, DailyStats
from config import settings
from utils import get_logger

logger = get_logger("api")

app = FastAPI(title="Nexus Pro API", version="1.0.0")

# CORS config
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev loop, tighten in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances (to be injected from main or initialized here)
bot_instance = None

class ConnectionManager:
    """Manage WebSocket connections"""
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Broadcast error: {e}")

manager = ConnectionManager()

@app.get("/")
async def root():
    return {"status": "online", "system": "Nexus Pro Trading Bot"}

@app.get("/api/status")
async def get_status():
    """Get bot status and daily stats"""
    stats = {
        "running": False,
        "daily_stats": {}
    }
    
    if bot_instance:
        stats["running"] = bot_instance._running
        stats["daily_stats"] = bot_instance.risk_manager.get_daily_stats()
        
    return stats

@app.get("/api/config")
async def get_config():
    """Get current configuration"""
    return {
        "trading": settings.trading.__dict__,
        "risk": settings.risk.__dict__,
        "ai": settings.ai.__dict__
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and handle incoming commands if any
            data = await websocket.receive_text()
            # Echo or process commands
            await websocket.send_text(f"Command received: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WS error: {e}")
        manager.disconnect(websocket)

# Helper to broadcast updates from bot
async def broadcast_signal(signal_data: dict):
    if manager:
        await manager.broadcast({
            "type": "SIGNAL",
            "data": signal_data,
            "timestamp": datetime.now().isoformat()
        })

async def broadcast_stats(stats_data: dict):
    if manager:
        await manager.broadcast({
            "type": "STATS",
            "data": stats_data,
            "timestamp": datetime.now().isoformat()
        })

async def broadcast_log(log_entry: str):
    if manager:
        await manager.broadcast({
            "type": "LOG",
            "data": {"message": log_entry},
            "timestamp": datetime.now().isoformat()
        })

async def broadcast_ofi(symbol: str, ofi_value: float):
    """Broadcast OFI update for gauge"""
    if manager:
        await manager.broadcast({
            "type": "OFI",
            "data": {"symbol": symbol, "value": ofi_value},
            "timestamp": datetime.now().isoformat()
        })

@app.post("/api/panic")
async def panic_stop():
    """Emergency stop - Close all positions and stop bot"""
    if bot_instance:
        logger.warning("🚨 PANIC STOP triggered via API!")
        
        # Close all positions
        for symbol, pos in list(bot_instance.risk_manager.open_positions.items()):
            try:
                ticker = bot_instance.data_provider.get_ticker(symbol)
                if ticker:
                    await bot_instance.close_trade(symbol, pos, ticker['price'], "PANIC_STOP")
            except Exception as e:
                logger.error(f"Panic close error {symbol}: {e}")
        
        # Stop the bot
        await bot_instance.stop()
        
        return {"status": "success", "message": "All positions closed. Bot stopped."}
    
    return {"status": "error", "message": "Bot not running"}

@app.get("/api/positions")
async def get_positions():
    """Get current open positions"""
    if bot_instance:
        positions = []
        for symbol, pos in bot_instance.risk_manager.open_positions.items():
            ticker = bot_instance.data_provider.get_ticker(symbol)
            current_price = ticker['price'] if ticker else pos.entry_price
            pnl = (current_price - pos.entry_price) * pos.quantity if pos.direction == "BUY" else (pos.entry_price - current_price) * pos.quantity
            
            positions.append({
                "symbol": symbol,
                "direction": pos.direction,
                "entry_price": pos.entry_price,
                "current_price": current_price,
                "quantity": pos.quantity,
                "pnl": pnl,
                "sl": pos.stop_loss,
                "tp": pos.take_profit
            })
        return {"positions": positions}
    return {"positions": []}

