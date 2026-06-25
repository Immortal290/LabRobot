from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta, datetime
from typing import List, Optional
from sqlalchemy import text

from app.core import security
from app.core.config import settings
from app.db import models, database
from app.schemas import schemas
from app.api import dependencies

router = APIRouter()

def create_log(db, event_type, description, user_id=None):
    db.add(models.Log(event_type=event_type, user_id=user_id, description=description))
    db.commit()

# ─── NETWORK UTILS ───────────────────────────────────────────────────────────

@router.get("/network/ip")
def get_local_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return {"ip": ip}
    except Exception:
        return {"ip": "127.0.0.1"}

@router.get("/network/tunnel")
def get_tunnel_url():
    import os, re
    log_path = "/logs/cloudflared.log"
    if not os.path.exists(log_path):
        return {"url": None}
    
    try:
        with open(log_path, "r") as f:
            content = f.read()
            # Match https://*.trycloudflare.com
            matches = re.findall(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", content)
            if matches:
                # Return the latest match
                return {"url": matches[-1]}
    except Exception as e:
        print(f"Error reading tunnel log: {e}")
        pass
        
    return {"url": None}

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

@router.put("/users/me/profile", response_model=schemas.Profile)
def update_profile(profile_update: schemas.ProfileUpdate, db: Session = Depends(database.get_db), current_user: models.User = Depends(dependencies.get_current_active_user)):
    profile = db.query(models.Profile).filter(models.Profile.user_id == current_user.id).first()
    if not profile:
        profile = models.Profile(user_id=current_user.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
        
    for field, value in profile_update.model_dump(exclude_none=True).items():
        setattr(profile, field, value)
    
    db.commit()
    db.refresh(profile)
    return profile

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
    db.commit()
    db.refresh(db_user)
    
    # Create empty profile
    db_profile = models.Profile(user_id=db_user.id)
    db.add(db_profile)
    
    create_log(db, "admin", f"Created user: {user.username}", user_id=current_user.id)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.put("/users/{user_id}", response_model=schemas.User)
def update_user(user_id: int, update: schemas.UserUpdate, db: Session = Depends(database.get_db), current_user: models.User = Depends(dependencies.get_admin_user)):
    if user_id == current_user.id and (update.role is not None or update.is_active is not None):
        raise HTTPException(status_code=400, detail="Cannot modify your own role or active status")
        
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
def delete_user(user_id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(dependencies.get_admin_user)):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
        
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Delete related profile
    if hasattr(db_user, "profile") and db_user.profile:
        db.delete(db_user.profile)
        
    # Nullify deliveries
    db.execute(text(f"UPDATE deliveries SET user_id = NULL WHERE user_id = {user_id}"))
    db.execute(text(f"UPDATE logs SET user_id = NULL WHERE user_id = {user_id}"))
    db.execute(text(f"UPDATE racks SET assigned_user = NULL WHERE assigned_user = {user_id}"))
    
    db.delete(db_user)
    db.commit()
    return {"ok": True}

# ─── INVENTORY ────────────────────────────────────────────────────────────────

@router.get("/inventory", response_model=List[schemas.Inventory])
def list_inventory(db: Session = Depends(database.get_db)):
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

def broadcast_delivery_update(db_delivery, db):
    from app.main import manager
    import asyncio, json
    
    # Get user
    user = db.query(models.User).filter(models.User.id == db_delivery.user_id).first()
    username = user.username if user else "Unknown"
    
    # Get item
    item = db.query(models.Inventory).filter(models.Inventory.id == db_delivery.item_id).first()
    item_name = item.name if item else "Unknown"
    
    delivery_dict = {
        "type": "delivery_update",
        "delivery": {
            "id": db_delivery.id,
            "user_id": db_delivery.user_id,
            "username": username,
            "item_id": db_delivery.item_id,
            "item_name": item_name,
            "rack_id": db_delivery.rack_id,
            "destination": db_delivery.destination,
            "pc_no": db_delivery.pc_no,
            "location": db_delivery.location,
            "status": db_delivery.status,
            "otp": db_delivery.otp,
            "phone_number": db_delivery.phone_number,
            "created_at": db_delivery.created_at.isoformat() if db_delivery.created_at else None,
            "completed_at": db_delivery.completed_at.isoformat() if db_delivery.completed_at else None
        }
    }
    
    broadcast_task = manager.broadcast_to_ui(json.dumps(delivery_dict))
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(broadcast_task)
    except RuntimeError:
        pass

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
    
    db_delivery = models.Delivery(
        user_id=current_user.id, 
        item_id=delivery.item_id, 
        destination=delivery.destination, 
        pc_no=delivery.pc_no,
        location=delivery.location,
        rack_id=delivery.rack_id, 
        status="pending_approval",
        otp=None,
        phone_number=delivery.phone_number
    )
    item.quantity -= 1
    if item.quantity == 0:
        item.available = False
    item.last_transaction = datetime.utcnow()
    db.add(db_delivery)
    create_log(db, "delivery", f"Delivery requested for item '{item.name}' to {delivery.destination} (Awaiting Admin Approval)", user_id=current_user.id)
    db.commit()
    db.refresh(db_delivery)
    
    broadcast_delivery_update(db_delivery, db)
    return db_delivery

@router.get("/quick-deliveries", response_model=List[schemas.Delivery])
def list_quick_deliveries(username: str, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        return []
    return db.query(models.Delivery).filter(models.Delivery.user_id == user.id).order_by(models.Delivery.created_at.desc()).all()

@router.post("/quick-delivery", response_model=schemas.Delivery)
def create_quick_delivery(payload: schemas.QuickDeliveryCreate, db: Session = Depends(database.get_db)):
    # Look up user or create new student account if they don't exist
    user = db.query(models.User).filter(models.User.username == payload.username).first()
    if not user:
        user = models.User(
            username=payload.username,
            password_hash=security.get_password_hash("123456"), # default password
            role="Student"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Create empty profile
        db_profile = models.Profile(user_id=user.id)
        db.add(db_profile)
        db.commit()

    item = db.query(models.Inventory).filter(models.Inventory.id == payload.item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.quantity <= 0:
        raise HTTPException(status_code=400, detail="Item out of stock")
        
    db_delivery = models.Delivery(
        user_id=user.id,
        item_id=payload.item_id,
        destination=f"PC {payload.pc_no} @ {payload.location}",
        pc_no=payload.pc_no,
        location=payload.location,
        rack_id=payload.rack_id,
        status="pending_approval",
        otp=None,
        phone_number=payload.phone_number
    )
    item.quantity -= 1
    if item.quantity == 0:
        item.available = False
    item.last_transaction = datetime.utcnow()
    db.add(db_delivery)
    create_log(db, "delivery", f"Quick mobile request by {payload.username} (PC {payload.pc_no}) for '{item.name}' to {payload.location} (Awaiting Admin Approval)", user_id=user.id)
    db.commit()
    db.refresh(db_delivery)
    
    broadcast_delivery_update(db_delivery, db)
    return db_delivery

def trigger_sms_notification(delivery, db: Session):
    if delivery.phone_number:
        # Get item name
        item = db.query(models.Inventory).filter(models.Inventory.id == delivery.item_id).first()
        item_name = item.name if item else "Equipment"
        
        # 1. Print a large, highlighted console box (visible in docker compose terminal)
        print(f"\n======================================================================")
        print(f"📱 [REALTIME SMS DISPATCH] To: {delivery.phone_number}")
        print(f"💬 MESSAGE: 🤖 Lab Buddy: Your retrieval OTP is {delivery.otp} for item '{item_name}'.")
        print(f"======================================================================\n")
        
        # 2. Add to logs database so it appears in the Admin logs
        create_log(db, "system", f"📱 Realtime SMS sent to {delivery.phone_number} (OTP: {delivery.otp})")
        
        # 3. Broadcast SMS event to all UI clients via WebSocket in real-time
        from app.main import manager
        import asyncio, json
        
        sms_dict = {
            "type": "sms_notification",
            "phone_number": delivery.phone_number,
            "delivery_id": delivery.id,
            "message": f"🤖 Lab Buddy: Your retrieval OTP is {delivery.otp}. Enter it on the robot screen to unlock Locker 0{delivery.rack_id}."
        }
        
        broadcast_task = manager.broadcast_to_ui(json.dumps(sms_dict))
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(broadcast_task)
        except RuntimeError:
            pass

@router.put("/deliveries/{delivery_id}", response_model=schemas.Delivery)
def update_delivery_status(delivery_id: int, update: schemas.DeliveryUpdate, db: Session = Depends(database.get_db), current_user: models.User = Depends(dependencies.get_current_active_user)):
    delivery = db.query(models.Delivery).filter(models.Delivery.id == delivery_id).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")
    
    old_status = delivery.status
    delivery.status = update.status
    
    if update.status == "task_assigned" and old_status == "pending_approval":
        import random
        delivery.otp = f"{random.randint(1000, 9999)}"
        create_log(db, "delivery", f"Delivery {delivery_id} approved. OTP generated.", user_id=current_user.id)

    if update.status == "completed":
        delivery.completed_at = datetime.utcnow()
        
    create_log(db, "delivery", f"Delivery {delivery_id} status → {update.status}", user_id=current_user.id)
    db.commit()
    db.refresh(delivery)
    
    # Trigger SMS notification if it has arrived
    if update.status == "arrived" and old_status != "arrived":
        trigger_sms_notification(delivery, db)
        
    broadcast_delivery_update(delivery, db)
    return delivery


@router.delete("/deliveries/{delivery_id}/cancel", response_model=schemas.DeliveryCancelResponse)
def cancel_delivery(delivery_id: int, db: Session = Depends(database.get_db)):
    """User cancels a delivery before the robot has been dispatched (navigating)."""
    delivery = db.query(models.Delivery).filter(models.Delivery.id == delivery_id).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")

    cancellable_statuses = ["pending", "validating", "assigned"]
    if delivery.status not in cancellable_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel delivery in status '{delivery.status}'. Robot may already be en route."
        )

    item = db.query(models.Inventory).filter(models.Inventory.id == delivery.item_id).first()
    if item:
        item.quantity += 1
        item.available = True
        item.last_transaction = datetime.utcnow()

    delivery.status = "cancelled"
    delivery.cancelled_at = datetime.utcnow()
    create_log(db, "delivery", f"Delivery {delivery_id} cancelled by user")
    db.commit()
    db.refresh(delivery)
    broadcast_delivery_update(delivery, db)
    return {"ok": True, "message": "Delivery cancelled successfully. Inventory restored."}


@router.post("/deliveries/{delivery_id}/confirm-pickup", response_model=schemas.PickupConfirmResponse)
def confirm_pickup(delivery_id: int, db: Session = Depends(database.get_db)):
    """User confirms they have collected their item from the open panel."""
    delivery = db.query(models.Delivery).filter(models.Delivery.id == delivery_id).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")

    if delivery.status not in ["panel_open", "arrived", "waiting_pickup"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot confirm pickup for delivery in status '{delivery.status}'."
        )

    delivery.status = "completed"
    delivery.completed_at = datetime.utcnow()
    create_log(db, "delivery", f"Pickup confirmed by user for delivery {delivery_id}")
    db.commit()
    db.refresh(delivery)
    broadcast_delivery_update(delivery, db)

    from app.main import manager
    import asyncio, json as _json
    cmd = _json.dumps({"type": "command", "action": "pickup_confirmed", "delivery_id": delivery_id})
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(manager.send_to_bridge(cmd))
    except RuntimeError:
        pass

    return {"ok": True, "delivery_id": delivery_id, "status": "completed"}


@router.post("/deliveries/{delivery_id}/verify-otp")
async def verify_delivery_otp(delivery_id: int, payload: schemas.DeliveryOTPVerify, db: Session = Depends(database.get_db)):
    delivery = db.query(models.Delivery).filter(models.Delivery.id == delivery_id).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")
    
    if delivery.otp != payload.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP code")
    
    # Update delivery status to panel_open
    delivery.status = "panel_open"
    
    # Unlock the rack associated with the delivery
    if delivery.rack_id:
        rack = db.query(models.Rack).filter(models.Rack.id == delivery.rack_id).first()
        if rack:
            rack.lock_status = "unlocked"
            
        # Send WebSocket command to hardware to physically open the servo
        from app.main import manager
        import json
        await manager.send_to_bridge(json.dumps({
            "type": "command", 
            "action": "unlock_rack", 
            "rack_id": delivery.rack_id
        }))
            
    create_log(db, "delivery", f"Delivery {delivery_id} OTP verified. Panel open.", user_id=delivery.user_id)
    db.commit()
    db.refresh(delivery)
    
    # Broadcast status change to WebSocket clients
    broadcast_delivery_update(delivery, db)
    
    return {"ok": True, "message": "OTP verified successfully. Locker unlocked."}


@router.post("/robot/command")
def send_robot_command(cmd: schemas.RobotCommand, db: Session = Depends(database.get_db), current_user: models.User = Depends(dependencies.get_admin_user)):
    """Admin sends a direct command to the robot (return to base, unlock panel, emergency stop)."""
    from app.main import manager
    import asyncio, json as _json

    valid_actions = ["return_to_base", "unlock_panel", "emergency_stop", "lock_panel"]
    if cmd.action not in valid_actions:
        raise HTTPException(status_code=400, detail=f"Unknown action: {cmd.action}")

    payload = _json.dumps({"type": "command", "action": cmd.action, "panel_id": cmd.panel_id})
    create_log(db, "system", f"Admin command sent: {cmd.action} (panel={cmd.panel_id})", user_id=current_user.id)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(manager.send_to_bridge(payload))
    except RuntimeError:
        pass

    return {"ok": True, "action": cmd.action, "sent": True}

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


# ─── BARCODE LOCATIONS ────────────────────────────────────────────────────────

class BarcodeLocationSchema(schemas.BaseModel):
    barcode_value: str
    department:    Optional[str] = None
    room:          Optional[str] = None
    nav_goal_name: Optional[str] = None
    goal_x:        Optional[float] = 0.0
    goal_y:        Optional[float] = 0.0
    goal_theta:    Optional[float] = 0.0
    description:   Optional[str] = None

    class Config:
        from_attributes = True

# Import BaseModel for inline schema
from pydantic import BaseModel as PydanticBaseModel

class BarcodeIn(PydanticBaseModel):
    barcode_value: str
    department:    Optional[str] = None
    room:          Optional[str] = None
    nav_goal_name: Optional[str] = None
    goal_x:        float = 0.0
    goal_y:        float = 0.0
    goal_theta:    float = 0.0
    description:   Optional[str] = None

@router.get("/barcodes")
def list_barcodes(db: Session = Depends(database.get_db),
                  _=Depends(dependencies.get_current_active_user)):
    return db.query(models.BarcodeLocation).all()

@router.get("/barcodes/lookup")
def lookup_barcode(value: str, db: Session = Depends(database.get_db)):
    """Look up a barcode — called by the kiosk when a barcode is scanned."""
    bc = db.query(models.BarcodeLocation).filter(
        models.BarcodeLocation.barcode_value == value
    ).first()
    if not bc:
        raise HTTPException(status_code=404, detail=f"Barcode '{value}' not registered")
    return bc

@router.post("/barcodes")
def create_barcode(data: BarcodeIn, db: Session = Depends(database.get_db),
                   _=Depends(dependencies.get_admin_user)):
    if db.query(models.BarcodeLocation).filter(
            models.BarcodeLocation.barcode_value == data.barcode_value).first():
        raise HTTPException(status_code=400, detail="Barcode already exists")
    bc = models.BarcodeLocation(**data.model_dump())
    db.add(bc)
    db.commit()
    db.refresh(bc)
    create_log(db, "system", f"Barcode registered: {data.barcode_value} → {data.room}")
    return bc

@router.put("/barcodes/{barcode_id}")
def update_barcode(barcode_id: int, data: BarcodeIn,
                   db: Session = Depends(database.get_db),
                   _=Depends(dependencies.get_admin_user)):
    bc = db.query(models.BarcodeLocation).filter(
        models.BarcodeLocation.id == barcode_id).first()
    if not bc:
        raise HTTPException(status_code=404, detail="Barcode not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(bc, k, v)
    db.commit()
    db.refresh(bc)
    return bc

@router.delete("/barcodes/{barcode_id}")
def delete_barcode(barcode_id: int, db: Session = Depends(database.get_db),
                   _=Depends(dependencies.get_admin_user)):
    bc = db.query(models.BarcodeLocation).filter(
        models.BarcodeLocation.id == barcode_id).first()
    if not bc:
        raise HTTPException(status_code=404, detail="Barcode not found")
    db.delete(bc)
    db.commit()
    return {"ok": True}


# ─── OTP AUDIT LOGS ───────────────────────────────────────────────────────────

@router.get("/otp-logs")
def list_otp_logs(limit: int = 50, db: Session = Depends(database.get_db),
                  _=Depends(dependencies.get_admin_user)):
    return db.query(models.OTPLog)\
             .order_by(models.OTPLog.created_at.desc())\
             .limit(limit).all()


# ─── ROBOT STATUS SNAPSHOT ────────────────────────────────────────────────────

class TelemetrySnapshotIn(PydanticBaseModel):
    state:           Optional[str]   = "idle"
    mission:         Optional[str]   = None
    pos_x:           Optional[float] = 0.0
    pos_y:           Optional[float] = 0.0
    heading:         Optional[float] = 0.0
    battery_percent: Optional[float] = 100.0
    cpu_temp:        Optional[float] = 0.0
    cpu_usage:       Optional[float] = 0.0
    ram_usage:       Optional[float] = 0.0
    arduino_ok:      Optional[bool]  = False
    lidar_ok:        Optional[bool]  = False
    active_delivery: Optional[int]   = None

@router.post("/robot/snapshot")
def save_robot_snapshot(data: TelemetrySnapshotIn,
                        db: Session = Depends(database.get_db)):
    """Persist a telemetry snapshot — called by the ROS2 bridge periodically."""
    snap = models.RobotStatusSnapshot(**data.model_dump())
    db.add(snap)
    db.commit()
    return {"ok": True}

@router.get("/robot/history")
def robot_history(limit: int = 100, db: Session = Depends(database.get_db),
                  _=Depends(dependencies.get_admin_user)):
    return db.query(models.RobotStatusSnapshot)\
             .order_by(models.RobotStatusSnapshot.timestamp.desc())\
             .limit(limit).all()


# ─── NAVIGATION LOG CREATE ────────────────────────────────────────────────────

class NavLogIn(PydanticBaseModel):
    start_pos_x:          float
    start_pos_y:          float
    dest_pos_x:           float
    dest_pos_y:           float
    route_taken:          Optional[str] = "[]"
    travel_time:          float = 0.0
    obstacles_encountered: int = 0
    status:               str = "success"

@router.post("/navigation-logs")
def create_nav_log(data: NavLogIn, db: Session = Depends(database.get_db)):
    """Persist a navigation run — called by the ROS2 delivery manager."""
    log = models.NavigationLog(**data.model_dump())
    db.add(log)
    db.commit()
    return {"ok": True}

@router.get("/navigation-logs")
def list_nav_logs(limit: int = 50, db: Session = Depends(database.get_db),
                  _=Depends(dependencies.get_admin_user)):
    return db.query(models.NavigationLog)\
             .order_by(models.NavigationLog.timestamp.desc())\
             .limit(limit).all()
