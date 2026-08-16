#!/usr/bin/env python3
"""
aura_robot/otp_manager.py
==========================
Handles OTP generation, storage, and verification.

Subscribes:
  /aura/otp_request   (std_msgs/String — JSON OTPRequest)

Publishes:
  /aura/otp_verified  (std_msgs/String — JSON {verified:bool, delivery_id:int})
  /aura/otp_event     (std_msgs/String — JSON for logging / GUI display)

SMS dispatch:
  Primary:   Twilio REST API (if credentials are in env vars)
  Fallback:  Logs OTP to console + database (visible in Admin panel)

PostgreSQL:
  Writes all OTP records to `otp_logs` table for audit trail.
"""

import os
import json
import random
import time
import logging
import requests

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

try:
    import psycopg2
    import psycopg2.pool
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

logger = logging.getLogger("aura.otp_manager")

DB_URL           = os.getenv("DATABASE_URL", "postgresql://robot_user:robot_password@localhost:5435/labrobot")
BACKEND_URL      = os.getenv("BACKEND_API_URL", "http://localhost:8000/api/v1")
OTP_LENGTH       = int(os.getenv("OTP_LENGTH", "4"))
OTP_EXPIRY_S     = int(os.getenv("OTP_EXPIRY_S", "300"))    # 5 minutes
MAX_ATTEMPTS     = int(os.getenv("OTP_MAX_ATTEMPTS", "3"))

# Twilio credentials (optional)
TWILIO_SID   = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM  = os.getenv("TWILIO_FROM_NUMBER", "")


class OTPManagerNode(Node):

    def __init__(self):
        super().__init__("aura_otp_manager")
        self._log = self.get_logger()

        # active_otps: delivery_id → {otp, expires_at, attempts}
        self._active_otps: dict = {}
        self._db_pool = None
        self._init_db()

        self._pub_verified = self.create_publisher(String, "/aura/otp_verified", 10)
        self._pub_event    = self.create_publisher(String, "/aura/otp_event",    10)

        self.create_subscription(String, "/aura/otp_request", self._cb_otp_request, 10)

        # Expiry cleanup timer (every 60 s)
        self.create_timer(60.0, self._cleanup_expired)

        self._log.info("OTPManager ready.")

    def _init_db(self):
        if not HAS_PSYCOPG2:
            return
        try:
            self._db_pool = psycopg2.pool.SimpleConnectionPool(1, 3, DB_URL)
            conn = self._db_pool.getconn()
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS otp_logs (
                        id           SERIAL PRIMARY KEY,
                        delivery_id  INT NOT NULL,
                        user_id      INT,
                        phone_number TEXT,
                        otp_code     TEXT NOT NULL,
                        action       TEXT,
                        verified     BOOLEAN DEFAULT FALSE,
                        attempts     INT DEFAULT 0,
                        created_at   TIMESTAMP DEFAULT NOW(),
                        verified_at  TIMESTAMP
                    );
                """)
                conn.commit()
            self._db_pool.putconn(conn)
        except Exception as e:
            self._log.error(f"OTP DB init error: {e}")
            self._db_pool = None

    # ── OTP Request ───────────────────────────────────────────────────────────
    def _cb_otp_request(self, msg: String):
        try:
            req = json.loads(msg.data)
            action = req.get("action", "send")

            if action == "send":
                self._generate_and_send(req)
            elif action == "verify":
                self._verify_otp(req)
            elif action == "expire":
                self._expire_otp(req.get("delivery_id"))

        except Exception as e:
            self._log.error(f"OTP request error: {e}")

    def _generate_and_send(self, req: dict):
        delivery_id  = req.get("delivery_id")
        phone_number = req.get("phone_number", "")
        user_id      = req.get("user_id")

        otp_code = "".join([str(random.randint(0, 9)) for _ in range(OTP_LENGTH)])
        expires_at = time.time() + OTP_EXPIRY_S

        self._active_otps[delivery_id] = {
            "otp":        otp_code,
            "expires_at": expires_at,
            "attempts":   0,
            "phone":      phone_number,
        }

        # Send SMS
        sent = self._send_sms(phone_number, otp_code, delivery_id)

        # Notify backend via REST so it can broadcast to UI
        try:
            requests.put(
                f"{BACKEND_URL}/deliveries/{delivery_id}",
                json={"status": "otp_sent"},
                timeout=3
            )
        except Exception:
            pass

        # Log to DB
        self._log_otp(delivery_id, user_id, phone_number, otp_code, "send")

        # Publish event
        event = {
            "type":        "otp_sent",
            "delivery_id": delivery_id,
            "phone":       phone_number[-4:] if phone_number else "",
            "sms_sent":    sent,
        }
        self._publish_event(event)
        self._log.info(f"OTP {otp_code} generated for delivery {delivery_id} (SMS sent={sent})")

    def _verify_otp(self, req: dict):
        delivery_id = req.get("delivery_id")
        submitted   = req.get("otp_code", "").strip()

        record = self._active_otps.get(delivery_id)
        if not record:
            self._publish_verified(delivery_id, False, "No active OTP for this delivery")
            return

        if time.time() > record["expires_at"]:
            self._expire_otp(delivery_id)
            self._publish_verified(delivery_id, False, "OTP expired")
            return

        record["attempts"] += 1
        if record["attempts"] > MAX_ATTEMPTS:
            self._publish_verified(delivery_id, False, "Maximum attempts exceeded")
            return

        if submitted == record["otp"]:
            self._active_otps.pop(delivery_id, None)
            self._log_otp(delivery_id, None, record["phone"], record["otp"], "verified")
            self._publish_verified(delivery_id, True, "OTP verified successfully")
            self._log.info(f"OTP verified for delivery {delivery_id}")
        else:
            remaining = MAX_ATTEMPTS - record["attempts"]
            self._publish_verified(delivery_id, False,
                                   f"Incorrect OTP. {remaining} attempt(s) remaining.")

    def _expire_otp(self, delivery_id: int):
        self._active_otps.pop(delivery_id, None)
        self._log.info(f"OTP expired for delivery {delivery_id}")

    def _cleanup_expired(self):
        now = time.time()
        expired = [did for did, r in self._active_otps.items() if now > r["expires_at"]]
        for did in expired:
            self._expire_otp(did)

    # ── SMS ───────────────────────────────────────────────────────────────────
    def _send_sms(self, phone: str, otp: str, delivery_id: int) -> bool:
        """Send via Twilio if credentials are set, else log to console."""
        message = f"🤖 AURA Lab Robot: Your retrieval code is {otp}. Valid 5 minutes. Delivery #{delivery_id}."

        if TWILIO_SID and TWILIO_TOKEN and TWILIO_FROM and phone:
            try:
                resp = requests.post(
                    f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json",
                    data={"From": TWILIO_FROM, "To": phone, "Body": message},
                    auth=(TWILIO_SID, TWILIO_TOKEN),
                    timeout=5,
                )
                if resp.status_code in (200, 201):
                    self._log.info(f"SMS dispatched via Twilio to {phone[-4:]}")
                    return True
                self._log.warning(f"Twilio error {resp.status_code}: {resp.text[:100]}")
            except Exception as e:
                self._log.warning(f"Twilio request failed: {e}")

        # Fallback: prominent console display
        print("\n" + "=" * 60)
        print(f"📱 OTP DISPATCH  |  Delivery #{delivery_id}")
        print(f"   Phone:  {phone or '(not set)'}")
        print(f"   Code:   {otp}")
        print(f"   MSG:    {message}")
        print("=" * 60 + "\n")
        return False

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _log_otp(self, delivery_id, user_id, phone, otp_code, action):
        if not self._db_pool:
            return
        try:
            conn = self._db_pool.getconn()
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO otp_logs (delivery_id,user_id,phone_number,otp_code,action) "
                    "VALUES (%s,%s,%s,%s,%s)",
                    (delivery_id, user_id, phone, otp_code, action)
                )
                conn.commit()
            self._db_pool.putconn(conn)
        except Exception as e:
            self._log.warning(f"OTP log DB error: {e}")

    def _publish_verified(self, delivery_id: int, verified: bool, message: str = ""):
        payload = {"delivery_id": delivery_id, "verified": verified, "message": message}
        msg = String(); msg.data = json.dumps(payload)
        self._pub_verified.publish(msg)

    def _publish_event(self, event: dict):
        msg = String(); msg.data = json.dumps(event)
        self._pub_event.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = OTPManagerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
