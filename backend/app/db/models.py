"""
backend/app/db/models.py — Extended with BarcodeLocation and OTPLog tables.
These are appended to the existing models without modifying any existing class.
"""
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.database import Base

# ─── Existing models (unchanged) ─────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(String)
    is_active = Column(Boolean, default=True)
    profile = relationship("Profile", back_populates="user", uselist=False)

class Profile(Base):
    __tablename__ = "profiles"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    email = Column(String, unique=True, index=True, nullable=True)
    full_name = Column(String, nullable=True)
    department = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    user = relationship("User", back_populates="profile")

class Inventory(Base):
    __tablename__ = "inventory"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String)
    quantity = Column(Integer, default=0)
    rack_id = Column(Integer, ForeignKey("racks.id"), nullable=True)
    available = Column(Boolean, default=True)
    last_transaction = Column(DateTime, default=datetime.utcnow)

class Rack(Base):
    __tablename__ = "racks"
    id = Column(Integer, primary_key=True, index=True)
    lock_status = Column(String, default="locked")
    assigned_item = Column(Integer, ForeignKey("inventory.id"), nullable=True)
    assigned_user = Column(Integer, ForeignKey("users.id"), nullable=True)
    delivery_status = Column(String, default="idle")
    access_history = relationship("Log", back_populates="rack")

class Delivery(Base):
    __tablename__ = "deliveries"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    rack_id = Column(Integer, ForeignKey("racks.id"), nullable=True)
    item_id = Column(Integer, ForeignKey("inventory.id"))
    destination = Column(String, nullable=True)
    pc_no = Column(String, nullable=True)
    location = Column(String, nullable=True)
    location_id = Column(String, nullable=True) # New strict location reference
    robot_id = Column(String, nullable=True)
    status = Column(String)
    otp_hash = Column(String, nullable=True)
    otp_expires_at = Column(DateTime, nullable=True)
    otp_attempts = Column(Integer, default=0)
    email = Column(String, nullable=True)          # OTP delivery email
    eta_seconds = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)

class Log(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    rack_id = Column(Integer, ForeignKey("racks.id"), nullable=True)
    description = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    rack = relationship("Rack", back_populates="access_history")

class NavigationLog(Base):
    __tablename__ = "navigation_logs"
    id = Column(Integer, primary_key=True, index=True)
    start_pos_x = Column(Float)
    start_pos_y = Column(Float)
    dest_pos_x = Column(Float)
    dest_pos_y = Column(Float)
    route_taken = Column(String)
    travel_time = Column(Float)
    obstacles_encountered = Column(Integer, default=0)
    status = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

class SystemConfig(Base):
    __tablename__ = "system_config"
    id = Column(Integer, primary_key=True, index=True)
    max_speed = Column(Float, default=1.0)
    safe_mode = Column(Boolean, default=True)
    maintenance_mode = Column(Boolean, default=False)
    theme = Column(String, default="dark")
    telemetry_frequency = Column(Integer, default=1000)
    voice_assistant = Column(Boolean, default=True)
    auto_return_to_base = Column(Boolean, default=True)
    collision_margin = Column(Float, default=0.5)
    cargo_temp_target = Column(Float, default=20.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# ─── NEW: Barcode Locations ───────────────────────────────────────────────────
class BarcodeLocation(Base):
    """Maps a printed barcode value to a physical lab room and navigation goal."""
    __tablename__ = "barcode_locations"

    id            = Column(Integer, primary_key=True, index=True)
    barcode_value = Column(String, unique=True, index=True, nullable=False)
    department    = Column(String, nullable=True)
    room          = Column(String, nullable=True)
    nav_goal_name = Column(String, nullable=True)
    goal_x        = Column(Float, default=0.0)
    goal_y        = Column(Float, default=0.0)
    goal_theta    = Column(Float, default=0.0)
    description   = Column(String, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)

# ─── NEW: OTP Audit Log ───────────────────────────────────────────────────────
class OTPLog(Base):
    """Stores every OTP generation and verification event for audit."""
    __tablename__ = "otp_logs"

    id          = Column(Integer, primary_key=True, index=True)
    delivery_id = Column(Integer, ForeignKey("deliveries.id"), nullable=True)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=True)
    email       = Column(String, nullable=True)    # recipient email
    otp_code    = Column(String, nullable=False)
    action      = Column(String, nullable=True)    # send | verify | expire
    verified    = Column(Boolean, default=False)
    attempts    = Column(Integer, default=0)
    created_at  = Column(DateTime, default=datetime.utcnow)
    verified_at = Column(DateTime, nullable=True)

# ─── NEW: Robot Status Snapshot ──────────────────────────────────────────────
class RobotStatusSnapshot(Base):
    """Persists periodic robot telemetry snapshots for history & analytics."""
    __tablename__ = "robot_status_snapshots"

    id              = Column(Integer, primary_key=True, index=True)
    state           = Column(String, default="idle")
    mission         = Column(String, nullable=True)
    pos_x           = Column(Float, default=0.0)
    pos_y           = Column(Float, default=0.0)
    heading         = Column(Float, default=0.0)
    battery_percent = Column(Float, default=100.0)
    cpu_temp        = Column(Float, default=0.0)
    cpu_usage       = Column(Float, default=0.0)
    ram_usage       = Column(Float, default=0.0)
    arduino_ok      = Column(Boolean, default=False)
    lidar_ok        = Column(Boolean, default=False)
    active_delivery = Column(Integer, nullable=True)
    timestamp       = Column(DateTime, default=datetime.utcnow, index=True)

# ─── NEW: Strict Location System ─────────────────────────────────────────────
class Location(Base):
    """Maps strict location IDs to map coordinates for the robot."""
    __tablename__ = "locations"
    
    id = Column(Integer, primary_key=True, index=True)
    location_id = Column(String, unique=True, index=True, nullable=False) # e.g. "desk1"
    name = Column(String, nullable=False) # e.g. "Desk 1"
    x = Column(Float, default=0.0)
    y = Column(Float, default=0.0)
    yaw = Column(Float, default=0.0)
    map = Column(String, default="lab_map")
    created_at = Column(DateTime, default=datetime.utcnow)

# ─── NEW: Robot Model ────────────────────────────────────────────────────────
class Robot(Base):
    __tablename__ = "robots"
    
    id = Column(Integer, primary_key=True, index=True)
    robot_id = Column(String, unique=True, index=True, nullable=False)
    status = Column(String, default="OFFLINE") # ONLINE, OFFLINE, ERROR, EMERGENCY_STOP
    battery = Column(Float, default=100.0)
    current_order_id = Column(Integer, ForeignKey("deliveries.id"), nullable=True)
    last_heartbeat = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# ─── NEW: Robot Command History ──────────────────────────────────────────────
class RobotCommand(Base):
    __tablename__ = "robot_commands"
    
    id = Column(Integer, primary_key=True, index=True)
    command_id = Column(String, unique=True, index=True, nullable=False)
    robot_id = Column(String, index=True, nullable=False)
    order_id = Column(String, nullable=True)
    command = Column(String, nullable=False) # DELIVER, CANCEL_DELIVERY, UNLOCK_COMPARTMENT, etc.
    payload = Column(String, nullable=True) # JSON payload sent
    acknowledged = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
