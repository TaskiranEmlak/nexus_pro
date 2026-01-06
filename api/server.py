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
