from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict
import json
import logging

from app.core.config import settings
from app.db.database import engine, Base
from app.api import endpoints

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create all tables on startup
Base.metadata.create_all(bind=engine)

# Run raw alter table queries to update schema if needed
from sqlalchemy import text
from app.db.database import SessionLocal
with SessionLocal() as db:
    try:
        db.execute(text("ALTER TABLE deliveries ADD COLUMN IF NOT EXISTS pc_no VARCHAR;"))
        db.execute(text("ALTER TABLE deliveries ADD COLUMN IF NOT EXISTS location VARCHAR;"))
        db.commit()
    except Exception as e:
        logger.error(f"Migration error: {e}")
        db.rollback()

# Seed Initial Data
from sqlalchemy.orm import Session
from app.db import models
from app.core import security

with SessionLocal() as db:
    # Seed users if none exist
    if db.query(models.User).count() == 0:
        db.add_all([
            models.User(username="admin", password_hash=security.get_password_hash("admin"), role="Admin"),
            models.User(username="roymsamriddha@gmail.com", password_hash=security.get_password_hash("123456"), role="Admin"),
            models.User(username="user", password_hash=security.get_password_hash("user"), role="Student"),
        ])
        db.commit()
    
    # Seed Inventory if none exist
    if db.query(models.Inventory).count() == 0:
        db.add_all([
            models.Inventory(name="Beaker 500ml", quantity=12),
            models.Inventory(name="Safety Goggles", quantity=4),
            models.Inventory(name="pH Sensor", quantity=2),
            models.Inventory(name="Pipette Set", quantity=0, available=False),
        ])
        db.commit()
    
    # Seed Racks if none exist
    if db.query(models.Rack).count() == 0:
        db.add_all([models.Rack(), models.Rack(), models.Rack(), models.Rack()])
        db.commit()
        
    # Seed SystemConfig if none exist
    if db.query(models.SystemConfig).count() == 0:
        db.add(models.SystemConfig())
        db.commit()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(endpoints.router, prefix=settings.API_V1_STR)


class ConnectionManager:
    def __init__(self):
        # UI clients (React frontends)
        self.ui_connections: List[WebSocket] = []
        # Bridge connections (ROS2 bridge)
        self.bridge_connections: List[WebSocket] = []
        # Latest telemetry snapshot for new UI clients
        self.latest_telemetry: Dict = {}

    async def connect_ui(self, websocket: WebSocket):
        await websocket.accept()
        self.ui_connections.append(websocket)
        # Send the latest snapshot immediately so the UI doesn't wait
        if self.latest_telemetry:
            try:
                await websocket.send_text(json.dumps(self.latest_telemetry))
            except Exception:
                pass
        logger.info(f"UI client connected. Total UI clients: {len(self.ui_connections)}")

    async def connect_bridge(self, websocket: WebSocket):
        await websocket.accept()
        self.bridge_connections.append(websocket)
        logger.info(f"Bridge client connected. Total bridge clients: {len(self.bridge_connections)}")

    def disconnect_ui(self, websocket: WebSocket):
        if websocket in self.ui_connections:
            self.ui_connections.remove(websocket)
        logger.info(f"UI client disconnected. Total UI clients: {len(self.ui_connections)}")

    def disconnect_bridge(self, websocket: WebSocket):
        if websocket in self.bridge_connections:
            self.bridge_connections.remove(websocket)
        logger.info(f"Bridge client disconnected.")

    async def broadcast_to_ui(self, message: str):
        dead = []
        for connection in self.ui_connections:
            try:
                await connection.send_text(message)
            except Exception:
                dead.append(connection)
        for d in dead:
            self.ui_connections.remove(d)

    async def send_to_bridge(self, message: str):
        for connection in self.bridge_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass


manager = ConnectionManager()


@app.websocket("/ws/bridge")
async def websocket_bridge(websocket: WebSocket):
    """Endpoint for the ROS2 bridge to push telemetry data."""
    await manager.connect_bridge(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                # Cache latest telemetry
                manager.latest_telemetry = payload
                # Broadcast to all connected UI clients
                await manager.broadcast_to_ui(data)
                logger.debug(f"Telemetry relayed: battery={payload.get('battery')}%")
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from bridge: {data}")
    except WebSocketDisconnect:
        manager.disconnect_bridge(websocket)


@app.websocket("/ws/ui")
async def websocket_ui(websocket: WebSocket):
    """Endpoint for React UI clients to receive live telemetry."""
    await manager.connect_ui(websocket)
    try:
        while True:
            # Listen for commands from UI (e.g. unlock rack)
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                if payload.get("type") == "command":
                    logger.info(f"Command received from UI: {payload}")
                    # Forward the command to bridge(s)
                    await manager.send_to_bridge(data)
                    # Echo acknowledgment back to UI
                    await websocket.send_text(json.dumps({
                        "type": "ack",
                        "command": payload.get("action"),
                        "status": "sent"
                    }))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        manager.disconnect_ui(websocket)
