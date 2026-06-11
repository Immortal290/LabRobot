from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta, datetime
from typing import List, Optional

from app.core import security
from app.core.config import settings
from app.db import models, database
from app.schemas import schemas
from app.api import dependencies

router = APIRouter()

def create_log(db, event_type, description, user_id=None):
    db.add(models.Log(event_type=event_type, user_id=user_id, description=description))
    db.commit()

# ─── AUTH ────────────────────────────────────────────────────────────────────

@router.post("/auth/token", response_model=schemas.Token)
def login_for_access_token(db: Session = Depends(database.get_db), form_data: OAuth2PasswordRequestForm = Depends()):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not security.verify_password(form_data.password, user.password_hash):
        create_log(db, "auth", f"Failed login attempt for username: {form_data.username}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password", headers={"WWW-Authenticate": "Bearer"})
    create_log(db, "auth", f"Successful login: {user.username}", user_id=user.id)
    access_token = security.create_access_token(data={"sub": user.username, "role": user.role}, expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/users/me", response_model=schemas.User)
def read_users_me(current_user: models.User = Depends(dependencies.get_current_active_user)):
    return current_user

# ─── USERS ───────────────────────────────────────────────────────────────────

@router.get("/users", response_model=List[schemas.User])
def list_users(db: Session = Depends(database.get_db), _=Depends(dependencies.get_admin_user)):
    return db.query(models.User).all()

@router.post("/users", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(dependencies.get_admin_user)):
    if db.query(models.User).filter(models.User.username == user.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    db_user = models.User(username=user.username, password_hash=security.get_password_hash(user.password), role=user.role)
    db.add(db_user)
    create_log(db, "admin", f"Created user: {user.username}", user_id=current_user.id)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.put("/users/{user_id}", response_model=schemas.User)
def update_user(user_id: int, update: schemas.UserUpdate, db: Session = Depends(database.get_db), current_user: models.User = Depends(dependencies.get_admin_user)):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    for field, value in update.model_dump(exclude_none=True).items():
        setattr(db_user, field, value)
    create_log(db, "admin", f"Updated user ID {user_id}", user_id=current_user.id)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(database.get_db), _=Depends(dependencies.get_admin_user)):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(db_user)
    db.commit()
    return {"ok": True}

# ─── INVENTORY ────────────────────────────────────────────────────────────────

@router.get("/inventory", response_model=List[schemas.Inventory])
def list_inventory(db: Session = Depends(database.get_db), _=Depends(dependencies.get_current_active_user)):
    return db.query(models.Inventory).all()

@router.post("/inventory", response_model=schemas.Inventory)
def create_inventory(item: schemas.InventoryCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(dependencies.get_admin_user)):
    db_item = models.Inventory(**item.model_dump())
    db.add(db_item)
    create_log(db, "inventory", f"Added item: {item.name}", user_id=current_user.id)
    db.commit()
    db.refresh(db_item)
    return db_item

@router.put("/inventory/{item_id}", response_model=schemas.Inventory)
def update_inventory(item_id: int, update: schemas.InventoryUpdate, db: Session = Depends(database.get_db), current_user: models.User = Depends(dependencies.get_admin_user)):
    item = db.query(models.Inventory).filter(models.Inventory.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    for field, value in update.model_dump(exclude_none=True).items():
        setattr(item, field, value)
    item.last_transaction = datetime.utcnow()
    create_log(db, "inventory", f"Updated item ID {item_id}", user_id=current_user.id)
    db.commit()
    db.refresh(item)
    return item

@router.delete("/inventory/{item_id}")
def delete_inventory(item_id: int, db: Session = Depends(database.get_db), _=Depends(dependencies.get_admin_user)):
    item = db.query(models.Inventory).filter(models.Inventory.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(item)
    db.commit()
    return {"ok": True}

# ─── RACKS ───────────────────────────────────────────────────────────────────

@router.get("/racks", response_model=List[schemas.Rack])
def list_racks(db: Session = Depends(database.get_db), _=Depends(dependencies.get_current_active_user)):
    return db.query(models.Rack).all()

@router.put("/racks/{rack_id}/unlock")
def unlock_rack(rack_id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(dependencies.get_current_active_user)):
    rack = db.query(models.Rack).filter(models.Rack.id == rack_id).first()
    if not rack:
        raise HTTPException(status_code=404, detail="Rack not found")
    if rack.assigned_user and rack.assigned_user != current_user.id and current_user.role not in ["Admin", "Lab Staff"]:
        raise HTTPException(status_code=403, detail="Not authorized to access this rack")
    rack.lock_status = "unlocked"
    create_log(db, "rack", f"Rack {rack_id} unlocked", user_id=current_user.id)
    db.commit()
    return {"rack_id": rack_id, "status": "unlocked"}

@router.put("/racks/{rack_id}/lock")
def lock_rack(rack_id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(dependencies.get_current_active_user)):
    rack = db.query(models.Rack).filter(models.Rack.id == rack_id).first()
    if not rack:
        raise HTTPException(status_code=404, detail="Rack not found")
    rack.lock_status = "locked"
    create_log(db, "rack", f"Rack {rack_id} locked", user_id=current_user.id)
    db.commit()
    return {"rack_id": rack_id, "status": "locked"}

@router.post("/racks/{rack_id}/verify")
def verify_rack_access(rack_id: int, payload: schemas.RackVerify, db: Session = Depends(database.get_db), current_user: models.User = Depends(dependencies.get_current_active_user)):
    if not security.verify_password(payload.password, current_user.password_hash):
        create_log(db, "rack_auth", f"Failed authentication for Rack {rack_id}", user_id=current_user.id)
        raise HTTPException(status_code=401, detail="Invalid password for rack access")
    
    rack = db.query(models.Rack).filter(models.Rack.id == rack_id).first()
    if not rack:
        raise HTTPException(status_code=404, detail="Rack not found")
    
    create_log(db, "rack_auth", f"Successful authentication for Rack {rack_id}", user_id=current_user.id)
    return {"ok": True}

@router.post("/racks/{rack_id}/transaction")
def process_rack_transaction(rack_id: int, payload: schemas.RackTransaction, db: Session = Depends(database.get_db), current_user: models.User = Depends(dependencies.get_current_active_user)):
    item = db.query(models.Inventory).filter(models.Inventory.id == payload.item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if payload.action == "add":
        item.quantity += payload.quantity
        item.available = True
        create_log(db, "inventory", f"Added {payload.quantity} {item.name}(s) to Rack {rack_id}", user_id=current_user.id)
    elif payload.action == "remove":
        if item.quantity < payload.quantity:
            raise HTTPException(status_code=400, detail="Not enough quantity in inventory")
        item.quantity -= payload.quantity
        if item.quantity == 0:
            item.available = False
        create_log(db, "inventory", f"Removed {payload.quantity} {item.name}(s) from Rack {rack_id}", user_id=current_user.id)
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
    
    item.last_transaction = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return item

@router.put("/racks/{rack_id}", response_model=schemas.Rack)
def update_rack(rack_id: int, update: schemas.RackUpdate, db: Session = Depends(database.get_db), _=Depends(dependencies.get_admin_user)):
    rack = db.query(models.Rack).filter(models.Rack.id == rack_id).first()
    if not rack:
        raise HTTPException(status_code=404, detail="Rack not found")
    for field, value in update.model_dump(exclude_none=True).items():
        setattr(rack, field, value)
    db.commit()
    db.refresh(rack)
    return rack

# ─── DELIVERIES ──────────────────────────────────────────────────────────────

@router.get("/deliveries", response_model=List[schemas.Delivery])
def list_deliveries(db: Session = Depends(database.get_db), current_user: models.User = Depends(dependencies.get_current_active_user)):
    if current_user.role in ["Admin", "Lab Staff"]:
        return db.query(models.Delivery).order_by(models.Delivery.created_at.desc()).all()
    return db.query(models.Delivery).filter(models.Delivery.user_id == current_user.id).order_by(models.Delivery.created_at.desc()).all()

@router.post("/deliveries", response_model=schemas.Delivery)
def create_delivery(delivery: schemas.DeliveryCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(dependencies.get_current_active_user)):
    item = db.query(models.Inventory).filter(models.Inventory.id == delivery.item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.quantity <= 0:
        raise HTTPException(status_code=400, detail="Item out of stock")
    db_delivery = models.Delivery(user_id=current_user.id, item_id=delivery.item_id, destination=delivery.destination, rack_id=delivery.rack_id, status="pending")
    item.quantity -= 1
    if item.quantity == 0:
        item.available = False
    item.last_transaction = datetime.utcnow()
    db.add(db_delivery)
    create_log(db, "delivery", f"Delivery requested for item '{item.name}' to {delivery.destination}", user_id=current_user.id)
    db.commit()
    db.refresh(db_delivery)
    return db_delivery

@router.put("/deliveries/{delivery_id}", response_model=schemas.Delivery)
def update_delivery_status(delivery_id: int, update: schemas.DeliveryUpdate, db: Session = Depends(database.get_db), current_user: models.User = Depends(dependencies.get_current_active_user)):
    delivery = db.query(models.Delivery).filter(models.Delivery.id == delivery_id).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")
    delivery.status = update.status
    if update.status == "completed":
        delivery.completed_at = datetime.utcnow()
    create_log(db, "delivery", f"Delivery {delivery_id} status → {update.status}", user_id=current_user.id)
    db.commit()
    db.refresh(delivery)
    return delivery

# ─── LOGS ────────────────────────────────────────────────────────────────────

@router.get("/logs", response_model=List[schemas.Log])
def get_logs(limit: int = 100, event_type: Optional[str] = None, db: Session = Depends(database.get_db), _=Depends(dependencies.get_admin_user)):
    q = db.query(models.Log)
    if event_type:
        q = q.filter(models.Log.event_type == event_type)
    return q.order_by(models.Log.timestamp.desc()).limit(limit).all()

@router.post("/logs/hardware")
def create_hardware_log(log: schemas.LogCreate, db: Session = Depends(database.get_db)):
    db.add(models.Log(**log.model_dump()))
    db.commit()
    return {"ok": True}

# ─── ANALYTICS ───────────────────────────────────────────────────────────────

@router.get("/analytics", response_model=schemas.AnalyticsSummary)
def get_analytics(db: Session = Depends(database.get_db), _=Depends(dependencies.get_admin_user)):
    return schemas.AnalyticsSummary(
        total_deliveries=db.query(models.Delivery).count(),
        active_deliveries=db.query(models.Delivery).filter(models.Delivery.status.in_(["pending", "in_progress"])).count(),
        total_inventory_items=db.query(models.Inventory).count(),
        total_users=db.query(models.User).count(),
        total_logs=db.query(models.Log).count(),
    )

# ─── SYSTEM CONFIG ───────────────────────────────────────────────────────────

@router.get("/config", response_model=schemas.SystemConfig)
def get_system_config(db: Session = Depends(database.get_db), _=Depends(dependencies.get_current_active_user)):
    config = db.query(models.SystemConfig).first()
    if not config:
        raise HTTPException(status_code=404, detail="System configuration not found")
    return config

@router.put("/config", response_model=schemas.SystemConfig)
def update_system_config(update: schemas.SystemConfigUpdate, db: Session = Depends(database.get_db), current_user: models.User = Depends(dependencies.get_admin_user)):
    config = db.query(models.SystemConfig).first()
    if not config:
        raise HTTPException(status_code=404, detail="System configuration not found")
    
    for field, value in update.model_dump(exclude_none=True).items():
        setattr(config, field, value)
    
    config.updated_at = datetime.utcnow()
    create_log(db, "system", "System configuration updated", user_id=current_user.id)
    db.commit()
    db.refresh(config)
    
    # Broadcast to websocket clients will be triggered from main.py via dependency injection or simple import
    from app.main import manager
    import asyncio, json
    
    config_dict = schemas.SystemConfig.model_validate(config).model_dump()
    # Convert datetime for JSON serialization
    config_dict["updated_at"] = config_dict["updated_at"].isoformat()
    
    broadcast_task = manager.broadcast_to_ui(json.dumps({
        "type": "config_update",
        "config": config_dict
    }))
    
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(broadcast_task)
    except RuntimeError:
        pass # No event loop running (e.g. in test or sync context)

    return config
