#!/usr/bin/env python3
"""
aura_robot/delivery_manager.py
==============================
Orchestrates the complete delivery lifecycle as a ROS2 node.

State machine:
  IDLE → PENDING → TASK_ASSIGNED → NAVIGATING → ARRIVED
       → OTP_SENT → OTP_VERIFIED → PANEL_OPEN → PICKUP_CONFIRMED
       → RETURNING → COMPLETED

Subscribes:
  /aura/barcode_detection  — triggers navigation to scanned destination
  /aura/otp_verified       — proceeds to open servo after OTP success
  /aura/servo_ack          — confirms flap opened/closed
  /aura/cancel_task        — abort current delivery

Publishes:
  /aura/delivery_task      — current active delivery state
  /aura/robot_state        — drives GUI emotion/animation
  /aura/mission            — mission description string
  /aura/servo_cmd          — open/close rack flap
  /aura/otp_request        — trigger OTP generation & send
  /goal_pose               — ROS2 nav2 navigation goal
"""

import os
import json
import time
import random
import logging
import requests
from enum import Enum
from typing import Optional

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String
from geometry_msgs.msg import PoseStamped

logger = logging.getLogger("aura.delivery_manager")

# ── Configuration ──────────────────────────────────────────────────────────────
BACKEND_URL  = os.getenv("BACKEND_API_URL", "http://localhost:8000/api/v1")
BACKEND_TOKEN= os.getenv("BACKEND_TOKEN",   "")     # Set in startup script
PICKUP_TIMEOUT = int(os.getenv("PICKUP_TIMEOUT_S", "120"))  # 2 min default


class DeliveryState(str, Enum):
    IDLE              = "idle"
    PENDING           = "pending_approval"
    TASK_ASSIGNED     = "task_assigned"
    NAVIGATING        = "navigating"
    ARRIVED           = "arrived"
    OTP_SENT          = "otp_sent"
    OTP_VERIFIED      = "otp_verified"
    PANEL_OPEN        = "panel_open"
    WAITING_PICKUP    = "waiting_pickup"
    PICKUP_CONFIRMED  = "pickup_confirmed"
    RETURNING         = "returning"
    COMPLETED         = "completed"
    CANCELLED         = "cancelled"
    FAILED            = "failed"


class DeliveryManagerNode(Node):
    """ROS2 node that drives the full delivery state machine."""

    def __init__(self):
        super().__init__("aura_delivery_manager")
        self._log = self.get_logger()

        # ── State ──────────────────────────────────────────────────────────
        self._state: DeliveryState = DeliveryState.IDLE
        self._delivery: Optional[dict] = None
        self._pickup_deadline: float  = 0.0
        self._nav_start: float        = 0.0

        # ── Subscriptions ───────────────────────────────────────────────────
        self.create_subscription(String, "/aura/barcode_detection",  self._cb_barcode,        10)
        self.create_subscription(String, "/aura/otp_verified",       self._cb_otp_verified,   10)
        self.create_subscription(String, "/aura/servo_ack",          self._cb_servo_ack,      10)
        self.create_subscription(String, "/aura/cancel_task",        self._cb_cancel,         10)
        self.create_subscription(String, "/aura/delivery_approved",  self._cb_approved,       10)
        self.create_subscription(Bool,   "/aura/arrived_at_goal",    self._cb_arrived,        10)

        # ── Publishers ─────────────────────────────────────────────────────
        self._pub_task    = self.create_publisher(String, "/aura/delivery_task", 10)
        self._pub_state   = self.create_publisher(String, "/aura/robot_state",   10)
        self._pub_mission = self.create_publisher(String, "/aura/mission",       10)
        self._pub_servo   = self.create_publisher(String, "/aura/servo_cmd",     10)
        self._pub_otp     = self.create_publisher(String, "/aura/otp_request",   10)
        self._pub_goal    = self.create_publisher(PoseStamped, "/goal_pose",     10)

        # ── Polling timer (5 Hz) — check for approved deliveries ───────────
        self.create_timer(0.2, self._poll_pending)

        # ── Watchdog timer (1 Hz) — detect pickup timeouts ─────────────────
        self.create_timer(1.0, self._watchdog)

        self._log.info("DeliveryManager ready.")

    # ── API helpers ───────────────────────────────────────────────────────────
    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if BACKEND_TOKEN:
            h["Authorization"] = f"Bearer {BACKEND_TOKEN}"
        return h

    def _api_get(self, path: str) -> Optional[dict]:
        try:
            r = requests.get(f"{BACKEND_URL}{path}", headers=self._headers(), timeout=3)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            self._log.warning(f"API GET {path} failed: {e}")
            return None

    def _api_put(self, path: str, data: dict) -> Optional[dict]:
        try:
            r = requests.put(f"{BACKEND_URL}{path}", json=data, headers=self._headers(), timeout=3)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            self._log.warning(f"API PUT {path} failed: {e}")
            return None

    # ── State machine helpers ─────────────────────────────────────────────────
    def _transition(self, new_state: DeliveryState, mission: str = ""):
        self._state = new_state
        # Publish ROS state string
        msg = String(); msg.data = new_state.value
        self._pub_state.publish(msg)
        if mission:
            m = String(); m.data = mission; self._pub_mission.publish(m)
        self._log.info(f"State → {new_state.value}  ({mission})")

    def _publish_task(self):
        if self._delivery:
            msg = String()
            msg.data = json.dumps(self._delivery)
            self._pub_task.publish(msg)

    def _send_servo(self, rack_id: int, action: str):
        cmd = json.dumps({"action": action, "rack": rack_id})
        msg = String(); msg.data = cmd; self._pub_servo.publish(msg)

    def _send_nav_goal(self, x: float, y: float, theta: float = 0.0):
        goal = PoseStamped()
        goal.header.frame_id = "map"
        goal.header.stamp = self.get_clock().now().to_msg()
        goal.pose.position.x = x
        goal.pose.position.y = y
        # Heading → quaternion (z-axis rotation only)
        import math
        goal.pose.orientation.z = math.sin(theta / 2)
        goal.pose.orientation.w = math.cos(theta / 2)
        self._pub_goal.publish(goal)

    # ── Callbacks ─────────────────────────────────────────────────────────────
    def _cb_barcode(self, msg: String):
        if self._state != DeliveryState.IDLE:
            self._log.info("Barcode received but delivery already active — ignored.")
            return
        try:
            bc = json.loads(msg.data)
            if not bc.get("valid"):
                self._log.warning(f"Invalid barcode: {bc.get('error_message')}")
                return
            self._log.info(f"Barcode → {bc['department']} / {bc['room']}")
            # Store for use when delivery is assigned
            self._pending_barcode = bc
        except Exception as e:
            self._log.error(f"Barcode parse error: {e}")

    def _cb_approved(self, msg: String):
        """Fired when admin approves a pending delivery."""
        if self._state not in (DeliveryState.IDLE, DeliveryState.PENDING):
            return
        try:
            delivery = json.loads(msg.data)
            self._delivery = delivery
            self._start_navigation(delivery)
        except Exception as e:
            self._log.error(f"Approved delivery parse error: {e}")

    def _cb_arrived(self, msg: Bool):
        if msg.data and self._state == DeliveryState.NAVIGATING:
            self._on_arrived()

    def _cb_otp_verified(self, msg: String):
        try:
            data = json.loads(msg.data)
            if data.get("verified") and self._delivery:
                self._log.info("OTP verified — opening flap.")
                self._open_flap()
        except Exception as e:
            self._log.error(f"OTP verified parse error: {e}")

    def _cb_servo_ack(self, msg: String):
        try:
            ack = json.loads(msg.data)
            if ack.get("action") == "open" and ack.get("acknowledged"):
                rack_id = ack.get("rack")
                self._log.info(f"Flap {rack_id} confirmed open — waiting for pickup.")
                self._transition(DeliveryState.WAITING_PICKUP,
                                 f"Waiting for item retrieval — Locker {rack_id:02d}")
                self._pickup_deadline = time.time() + PICKUP_TIMEOUT
                if self._delivery:
                    self._api_put(f"/deliveries/{self._delivery['id']}",
                                  {"status": "waiting_pickup"})
                self._publish_task()

            elif ack.get("action") == "close":
                self._log.info("Flap closed — confirming pickup.")
                self._on_pickup_confirmed()
        except Exception as e:
            self._log.error(f"Servo ACK parse error: {e}")

    def _cb_cancel(self, msg: String):
        if self._state not in (DeliveryState.COMPLETED, DeliveryState.IDLE):
            self._log.info("Delivery cancelled via ROS command.")
            if self._delivery:
                self._api_put(f"/deliveries/{self._delivery['id']}",
                              {"status": "cancelled"})
            self._reset()

    # ── Polling ───────────────────────────────────────────────────────────────
    def _poll_pending(self):
        """Poll backend for newly approved deliveries when idle."""
        if self._state != DeliveryState.IDLE:
            return
        deliveries = self._api_get("/deliveries")
        if not deliveries:
            return
        for d in deliveries:
            if d.get("status") == "task_assigned":
                self._delivery = d
                self._start_navigation(d)
                break

    # ── Lifecycle methods ─────────────────────────────────────────────────────
    def _start_navigation(self, delivery: dict):
        self._transition(DeliveryState.TASK_ASSIGNED,
                         f"Task assigned — preparing to dispatch")
        self._api_put(f"/deliveries/{delivery['id']}",
                      {"status": "navigating"})
        # Issue nav goal (use coords from barcode if available, else default)
        bc = getattr(self, "_pending_barcode", None)
        if bc:
            self._send_nav_goal(bc["goal_x"], bc["goal_y"], bc.get("goal_theta", 0.0))
        else:
            # Fallback: navigate to destination string looked up from DB
            self._send_nav_goal(0.0, 0.0)

        self._nav_start = time.time()
        self._transition(DeliveryState.NAVIGATING,
                         f"Navigating → {delivery.get('destination', '?')}")
        self._publish_task()

    def _on_arrived(self):
        self._transition(DeliveryState.ARRIVED,
                         f"Arrived at destination — initiating OTP")
        if self._delivery:
            self._api_put(f"/deliveries/{self._delivery['id']}",
                          {"status": "arrived"})
            # Request OTP send
            otp_req = json.dumps({
                "delivery_id":  self._delivery["id"],
                "user_id":      self._delivery.get("user_id"),
                "phone_number": self._delivery.get("phone_number", ""),
                "action":       "send",
            })
            msg = String(); msg.data = otp_req; self._pub_otp.publish(msg)
            self._transition(DeliveryState.OTP_SENT, "OTP sent — awaiting verification")
        self._publish_task()

    def _open_flap(self):
        if not self._delivery:
            return
        rack_id = self._delivery.get("rack_id", 1)
        self._transition(DeliveryState.PANEL_OPEN,
                         f"Panel open — Locker {rack_id:02d}")
        self._api_put(f"/deliveries/{self._delivery['id']}",
                      {"status": "panel_open"})
        self._send_servo(rack_id, "open")
        self._publish_task()

    def _on_pickup_confirmed(self):
        if not self._delivery:
            return
        self._transition(DeliveryState.PICKUP_CONFIRMED, "Pickup confirmed — returning to base")
        self._api_put(f"/deliveries/{self._delivery['id']}",
                      {"status": "completed"})
        # Navigate back to base
        self._send_nav_goal(0.0, 0.0)
        self._transition(DeliveryState.RETURNING, "Returning to base")
        self._publish_task()

    def _reset(self):
        self._delivery = None
        self._pickup_deadline = 0.0
        self._nav_start = 0.0
        self._transition(DeliveryState.IDLE, "Standby — Awaiting next task")

    # ── Watchdog ──────────────────────────────────────────────────────────────
    def _watchdog(self):
        if self._state == DeliveryState.WAITING_PICKUP:
            if time.time() > self._pickup_deadline:
                self._log.warning("Pickup timeout — closing flap and marking failed.")
                if self._delivery:
                    rack_id = self._delivery.get("rack_id", 1)
                    self._send_servo(rack_id, "close")
                    self._api_put(f"/deliveries/{self._delivery['id']}",
                                  {"status": "pickup_timeout"})
                self._reset()


def main(args=None):
    rclpy.init(args=args)
    node = DeliveryManagerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
