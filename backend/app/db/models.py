from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(String) # Admin, Lab Staff, Student/User
    is_active = Column(Boolean, default=True)

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
    lock_status = Column(String, default="locked") # locked, unlocked
    assigned_item = Column(Integer, ForeignKey("inventory.id"), nullable=True)
    assigned_user = Column(Integer, ForeignKey("users.id"), nullable=True)
    delivery_status = Column(String, default="idle") # idle, in_transit, delivered
    access_history = relationship("Log", back_populates="rack")

class Delivery(Base):
    __tablename__ = "deliveries"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    rack_id = Column(Integer, ForeignKey("racks.id"))
    item_id = Column(Integer, ForeignKey("inventory.id"))
    destination = Column(String)
    status = Column(String) # pending, in_progress, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

class Log(Base):
    __tablename__ = "logs"
    
    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String, index=True) # auth, inventory, rack, hardware, system
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
    route_taken = Column(String) # JSON string of points or path
    travel_time = Column(Float)
    obstacles_encountered = Column(Integer, default=0)
    status = Column(String) # success, failed
    timestamp = Column(DateTime, default=datetime.utcnow)
