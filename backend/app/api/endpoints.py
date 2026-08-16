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
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            
        # Search backwards for the most recently announced tunnel URL
        for line in reversed(lines):
            matches = re.findall(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
            if matches and ("quick Tunnel has been created" in line or "Visit it at" in line or "Registered tunnel" in line or matches[0]):
                return {"url": matches[-1]}
    except Exception as e:
        print(f"Error reading tunnel log: {e}")
        pass
        
    return {"url": None}

# ─── AUTH ────────────────────────────────────────────────────────────────────

@router.post("/auth/token", response_model=schemas.Token)
def login_for_access_token(db: Session = Depends(database.get_db), form_data: OAuth2PasswordRequestForm = Depends()):
    login_id = form_data.username.strip()
    user = db.query(models.User).filter(models.User.username.ilike(login_id)).first()
    if not user:
        profile = db.query(models.Profile).filter(models.Profile.email.ilike(login_id)).first()
        if profile:
            user = profile.user
    if not user and "@" in login_id:
        prefix = login_id.split("@")[0]
        user = db.query(models.User).filter(models.User.username.ilike(prefix)).first()

    if not user or not security.verify_password(form_data.password, user.password_hash):
        create_log(db, "auth", f"Failed login attempt for username: {form_data.username}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password", headers={"WWW-Authenticate": "Bearer"})
    
    # If user logged in with an email address, ensure their profile stores this email
    if "@" in login_id:
        if not user.profile:
            user.profile = models.Profile(user_id=user.id, email=login_id)
            db.add(user.profile)
            db.commit()
        elif not user.profile.email:
            user.profile.email = login_id
            db.commit()

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
            "email": db_delivery.email,
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
        email=delivery.email
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
        email=payload.email
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

# ─── GMAIL API OTP EMAIL ─────────────────────────────────────────────────────

def _build_otp_html(otp: str, item_name: str, rack_id, recipient_name: str) -> str:
    """Returns a premium HTML email body for the OTP notification."""
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Lab Buddy — Your Delivery OTP</title>
</head>
<body style="margin:0;padding:0;background-color:#0f172a;font-family:'Segoe UI',Roboto,Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0f172a;padding:40px 16px;">
  <tr><td align="center">
    <table width="520" cellpadding="0" cellspacing="0" style="background:linear-gradient(160deg,#1e293b 0%,#0f172a 100%);border-radius:20px;overflow:hidden;border:1px solid rgba(6,182,212,0.2);box-shadow:0 25px 60px rgba(0,0,0,0.6);">

      <!-- HEADER -->
      <tr>
        <td style="background:linear-gradient(135deg,#0891b2 0%,#6d28d9 100%);padding:32px 40px;text-align:center;">
          <div style="font-size:40px;margin-bottom:8px;">🤖</div>
          <h1 style="margin:0;color:#ffffff;font-size:22px;font-weight:800;letter-spacing:-0.5px;">Lab Buddy</h1>
          <p style="margin:6px 0 0;color:rgba(255,255,255,0.7);font-size:13px;font-weight:500;">Automated Lab Equipment Delivery System</p>
        </td>
      </tr>

      <!-- STATUS BADGE -->
      <tr>
        <td style="padding:28px 40px 0;text-align:center;">
          <span style="display:inline-block;background:rgba(139,92,246,0.15);border:1px solid rgba(139,92,246,0.35);color:#c4b5fd;padding:6px 18px;border-radius:30px;font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;">
            🔔 &nbsp;DELIVERY ARRIVED
          </span>
        </td>
      </tr>

      <!-- GREETING -->
      <tr>
        <td style="padding:20px 40px 0;">
          <p style="margin:0;color:#e2e8f0;font-size:16px;font-weight:600;">Hi {recipient_name},</p>
          <p style="margin:8px 0 0;color:#94a3b8;font-size:14px;line-height:1.6;">
            Great news! Your lab equipment has arrived and the robot is waiting for you. Use the one-time password below on the robot's touch screen to unlock your compartment.
          </p>
        </td>
      </tr>

      <!-- OTP BOX -->
      <tr>
        <td style="padding:24px 40px;">
          <table width="100%" cellpadding="0" cellspacing="0" style="background:rgba(6,182,212,0.06);border:2px solid rgba(6,182,212,0.35);border-radius:16px;overflow:hidden;">
            <tr>
              <td style="padding:24px;text-align:center;">
                <p style="margin:0 0 10px;font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#22d3ee;font-weight:700;">🔑 &nbsp;Your One-Time Password</p>
                <div style="font-size:52px;font-weight:900;letter-spacing:14px;color:#ffffff;font-family:'Courier New',monospace;text-shadow:0 0 30px rgba(6,182,212,0.5);">{otp}</div>
                <p style="margin:10px 0 0;font-size:12px;color:#64748b;">Valid for this delivery only &nbsp;·&nbsp; Do not share with anyone</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>

      <!-- DELIVERY DETAILS -->
      <tr>
        <td style="padding:0 40px 24px;">
          <table width="100%" cellpadding="0" cellspacing="0" style="background:rgba(0,0,0,0.2);border-radius:12px;overflow:hidden;">
            <tr>
              <td style="padding:14px 20px;border-bottom:1px solid rgba(255,255,255,0.04);">
                <table width="100%" cellpadding="0" cellspacing="0">
                  <tr>
                    <td style="color:#64748b;font-size:13px;">📦 &nbsp;Equipment</td>
                    <td align="right" style="color:#e2e8f0;font-size:13px;font-weight:600;">{item_name}</td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td style="padding:14px 20px;border-bottom:1px solid rgba(255,255,255,0.04);">
                <table width="100%" cellpadding="0" cellspacing="0">
                  <tr>
                    <td style="color:#64748b;font-size:13px;">🗄️ &nbsp;Locker Compartment</td>
                    <td align="right" style="color:#e2e8f0;font-size:13px;font-weight:600;">R-{rack_id}</td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td style="padding:14px 20px;">
                <table width="100%" cellpadding="0" cellspacing="0">
                  <tr>
                    <td style="color:#64748b;font-size:13px;">⚡ &nbsp;What to do</td>
                    <td align="right" style="color:#22d3ee;font-size:13px;font-weight:600;">Walk → Enter OTP → Collect</td>
                  </tr>
                </table>
              </td>
            </tr>
          </table>
        </td>
      </tr>

      <!-- STEPS -->
      <tr>
        <td style="padding:0 40px 28px;">
          <table width="100%" cellpadding="0" cellspacing="0" style="background:rgba(109,40,217,0.08);border:1px solid rgba(109,40,217,0.2);border-radius:12px;">
            <tr>
              <td style="padding:16px 20px;">
                <p style="margin:0 0 12px;color:#a78bfa;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:1px;">📋 &nbsp;Step-by-Step</p>
                <p style="margin:0 0 6px;color:#cbd5e1;font-size:13px;">1️⃣ &nbsp;Walk to the Lab Buddy robot</p>
                <p style="margin:0 0 6px;color:#cbd5e1;font-size:13px;">2️⃣ &nbsp;Tap <strong style="color:#fff;">"Enter OTP"</strong> on the touch screen</p>
                <p style="margin:0 0 6px;color:#cbd5e1;font-size:13px;">3️⃣ &nbsp;Type <strong style="color:#22d3ee;font-family:monospace;font-size:15px;">{otp}</strong> and confirm</p>
                <p style="margin:0;color:#cbd5e1;font-size:13px;">4️⃣ &nbsp;Collect your item from compartment <strong style="color:#fff;">R-{rack_id}</strong></p>
              </td>
            </tr>
          </table>
        </td>
      </tr>

      <!-- FOOTER -->
      <tr>
        <td style="padding:20px 40px;text-align:center;border-top:1px solid rgba(255,255,255,0.05);">
          <p style="margin:0;color:#334155;font-size:12px;line-height:1.6;">
            This is an automated message from <strong style="color:#475569;">Lab Buddy Delivery System</strong><br>
            Please do not reply to this email.
          </p>
        </td>
      </tr>

    </table>
  </td></tr>
</table>
</body>
</html>"""


def send_otp_email(delivery, db: Session):
    """Send OTP to the user's email via Gmail API (Web App OAuth2 — env var credentials).
    Falls back to a console simulation if credentials are not configured."""
    if not delivery.email:
        return

    item      = db.query(models.Inventory).filter(models.Inventory.id == delivery.item_id).first()
    item_name = item.name if item else "Lab Equipment"

    user = db.query(models.User).filter(models.User.id == delivery.user_id).first()
    recipient_name = (
        user.profile.full_name if user and user.profile and user.profile.full_name
        else (user.username.capitalize() if user else "Student")
    )

    subject   = f"🔑 Lab Buddy OTP: {delivery.otp} — Your equipment has arrived!"
    html_body = _build_otp_html(delivery.otp, item_name, delivery.rack_id, recipient_name)

    # ── Attempt real Gmail API send using Web App OAuth2 credentials ──────────
    email_sent = False
    if settings.GMAIL_CLIENT_ID and settings.GMAIL_CLIENT_SECRET and settings.GMAIL_REFRESH_TOKEN:
        try:
            import base64
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            # Build credentials directly from env vars — no JSON files needed.
            # The refresh_token is permanent (never expires unless revoked).
            creds = Credentials(
                token=None,
                refresh_token=settings.GMAIL_REFRESH_TOKEN,
                client_id=settings.GMAIL_CLIENT_ID,
                client_secret=settings.GMAIL_CLIENT_SECRET,
                token_uri="https://oauth2.googleapis.com/token",
            )
            # Exchange refresh_token for a short-lived access_token
            creds.refresh(Request())

            # Build MIME email (table-based HTML for email client compatibility)
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = f"{settings.GMAIL_SENDER_NAME} <{settings.GMAIL_SENDER_ADDRESS}>"
            msg["To"]      = delivery.email
            msg["Reply-To"] = f"no-reply@labbuddy.local"
            msg.attach(MIMEText(html_body, "html"))

            raw     = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            service = build("gmail", "v1", credentials=creds)
            service.users().messages().send(userId="me", body={"raw": raw}).execute()

            email_sent = True
            print(f"\n✅ [GMAIL OTP EMAIL] Sent to {delivery.email} (OTP: {delivery.otp})")
            create_log(db, "system",
                       f"📧 OTP email sent to {delivery.email} — delivery #{delivery.id} (OTP: {delivery.otp})")

            db.add(models.OTPLog(
                delivery_id=delivery.id,
                user_id=delivery.user_id,
                email=delivery.email,
                otp_code=delivery.otp,
                action="send",
            ))
            db.commit()

        except Exception as exc:
            print(f"\n⚠️  [GMAIL API ERROR] {exc}")
            create_log(db, "system", f"⚠️ Email failed for {delivery.email}: {exc}")

    # ── Console simulation fallback ────────────────────────────────────────────
    if not email_sent:
        print(f"\n{'='*70}")
        print(f"📧 [SIMULATED EMAIL] To: {delivery.email}")
        print(f"📬 Subject: {subject}")
        print(f"🔑 OTP CODE: {delivery.otp}   |   Item: {item_name}   |   Locker: R-{delivery.rack_id}")
        print(f"{'='*70}\n")
        create_log(db, "system",
                   f"📧 [Simulated] OTP email to {delivery.email} (OTP: {delivery.otp}) — set GMAIL_* env vars to go live.")

    # ── Real-time WebSocket push to mobile portal (always fires) ─────────────
    from app.main import manager
    import asyncio, json
    ws_payload = {
        "type":        "email_notification",
        "email":       delivery.email,
        "delivery_id": delivery.id,
        "otp":         delivery.otp,
        "message":     f"🤖 Lab Buddy: Your retrieval OTP is {delivery.otp}. Enter it on the robot screen to open Locker 0{delivery.rack_id}."
    }
    broadcast_task = manager.broadcast_to_ui(json.dumps(ws_payload))
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
        send_otp_email(delivery, db)
        
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
