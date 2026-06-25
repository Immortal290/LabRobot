from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

# Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# User Schemas
class UserBase(BaseModel):
    username: str
    role: str

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None

class ProfileBase(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    department: Optional[str] = None
    avatar_url: Optional[str] = None

class ProfileUpdate(ProfileBase):
    pass

class Profile(ProfileBase):
    id: int
    user_id: int
    class Config:
        from_attributes = True

class User(UserBase):
    id: int
    is_active: bool
    profile: Optional[Profile] = None
    class Config:
        from_attributes = True

# Inventory Schemas
class InventoryBase(BaseModel):
    name: str
    description: Optional[str] = None
    quantity: int
    available: bool = True

class InventoryCreate(InventoryBase):
    rack_id: Optional[int] = None

class InventoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    quantity: Optional[int] = None
    available: Optional[bool] = None
    rack_id: Optional[int] = None

class Inventory(InventoryBase):
    id: int
    rack_id: Optional[int] = None
    last_transaction: datetime
    class Config:
        from_attributes = True

# Rack Schemas
class RackUpdate(BaseModel):
    lock_status: Optional[str] = None
    assigned_item: Optional[int] = None
    assigned_user: Optional[int] = None
    delivery_status: Optional[str] = None

class Rack(BaseModel):
    id: int
    lock_status: str
    delivery_status: str
    assigned_item: Optional[int] = None
    assigned_user: Optional[int] = None
    class Config:
        from_attributes = True

class RackVerify(BaseModel):
    password: str

class RackTransaction(BaseModel):
    item_id: int
    action: str  # "add" or "remove"
    quantity: int

# Delivery Schemas
class DeliveryCreate(BaseModel):
    item_id: int
    destination: str
    rack_id: Optional[int] = None
    pc_no: Optional[str] = None
    location: Optional[str] = None
    phone_number: Optional[str] = None

class QuickDeliveryCreate(BaseModel):
    username: str
    pc_no: str
    item_id: int
    location: str
    rack_id: Optional[int] = None
    phone_number: Optional[str] = None

class DeliveryUpdate(BaseModel):
    status: str

class Delivery(BaseModel):
    id: int
    user_id: int
    rack_id: Optional[int] = None
    item_id: int
    destination: str
    pc_no: Optional[str] = None
    location: Optional[str] = None
    status: str
    otp: Optional[str] = None
    phone_number: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    class Config:
        from_attributes = True

class DeliveryOTPVerify(BaseModel):
    otp: str

# Log Schemas
class LogCreate(BaseModel):
    event_type: str
    description: str
    user_id: Optional[int] = None

class Log(BaseModel):
    id: int
    event_type: str
    user_id: Optional[int] = None
    description: str
    timestamp: datetime
    class Config:
        from_attributes = True

# Analytics Schema
class AnalyticsSummary(BaseModel):
    total_deliveries: int
    active_deliveries: int
    total_inventory_items: int
    total_users: int
    total_logs: int

# SystemConfig Schemas
class SystemConfigBase(BaseModel):
    max_speed: float
    safe_mode: bool
    maintenance_mode: bool
    theme: str
    telemetry_frequency: int
    voice_assistant: bool
    auto_return_to_base: bool
    collision_margin: float
    cargo_temp_target: float

class SystemConfigUpdate(BaseModel):
    max_speed: Optional[float] = None
    safe_mode: Optional[bool] = None
    maintenance_mode: Optional[bool] = None
    theme: Optional[str] = None
    telemetry_frequency: Optional[int] = None
    voice_assistant: Optional[bool] = None
    auto_return_to_base: Optional[bool] = None
    collision_margin: Optional[float] = None
    cargo_temp_target: Optional[float] = None

class SystemConfig(SystemConfigBase):
    id: int
    updated_at: datetime
    class Config:
        from_attributes = True
