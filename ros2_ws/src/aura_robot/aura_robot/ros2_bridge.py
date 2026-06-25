#!/usr/bin/env python3
"""
aura_robot/ros2_bridge.py
=========================
Enhanced ROS2 ↔ FastAPI WebSocket bridge for AURA.

Replaces the old mock-only ros2_bridge.py.  Runs as a proper ROS2 node
that simultaneously:
  • Subscribes to all AURA topics and forwards them as JSON to the backend.
  • Receives JSON commands from the backend WebSocket and publishes them
    as ROS2 messages / service calls.

Topic map (ROS2 → WebSocket):
  /aura/robot_status         → type: "telemetry"
  /aura/system_health        → type: "system_health"
  /aura/delivery_task        → type: "delivery_task"
  /aura/inventory_update     → type: "inventory_update"
  /aura/servo_command        → type: "servo_ack"
  /aura/otp_request          → type: "otp_event"

Command map (WebSocket → ROS2):
  action: "return_to_base"   → publishes geometry_msgs/PoseStamped
  action: "estop"            → publishes std_msgs/Bool to /aura/estop
  action: "unlock_rack"      → publishes aura_msgs/ServoCommand
  action: "cancel_task"      → publishes std_msgs/String to /aura/cancel_task
"""

import os
import json
import time
import math
import random
import asyncio
import logging
import threading
from typing import Optional

import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from std_msgs.msg import Bool, String, Float32
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Odometry

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False

# ── Configuration ──────────────────────────────────────────────────────────────
BACKEND_WS_URL = os.getenv("BACKEND_URL", "ws://localhost:8000/ws/bridge")
PUBLISH_HZ     = float(os.getenv("PUBLISH_HZ", "10"))        # 10 Hz default
LOG_LEVEL      = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("aura.ros2_bridge")


# ── Telemetry State (thread-safe snapshot) ─────────────────────────────────────
class TelemetryState:
    """Shared mutable telemetry that ROS callbacks write into."""

    def __init__(self):
        self._lock = threading.Lock()

        # Navigation / pose
        self.x: float            = 0.0
        self.y: float            = 0.0
        self.heading: float      = 0.0
        self.velocity: float     = 0.0

        # Mission state
        self.status: str         = "idle"
        self.mission: str        = "Standby — Awaiting task"
        self.destination: str    = "base"

        # Power
        self.battery: float      = 100.0

        # Hardware health
        self.arduino_ok: bool    = False
        self.lidar_ok: bool      = False
        self.db_ok: bool         = False
        self.nav_ok: bool        = False

        # Performance
        self.cpu_temp: float     = 42.0
        self.cpu_usage: float    = 0.0
        self.ram_usage: float    = 0.0

        # Active delivery
        self.delivery_id: int    = -1
        self.delivery_status: str = ""
        self.rack_id: int        = -1
        self.rack_statuses: list = ["locked", "locked", "locked", "locked"]

        # Time
        self.timestamp: str      = ""

    def update(self, **kwargs):
        with self._lock:
            for k, v in kwargs.items():
                if hasattr(self, k):
                    setattr(self, k, v)

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "type":             "telemetry",
                "x":                round(self.x, 4),
                "y":                round(self.y, 4),
                "heading":          round(self.heading, 4),
                "velocity":         round(self.velocity, 3),
                "status":           self.status,
                "mission":          self.mission,
                "destination":      self.destination,
                "battery":          round(self.battery, 2),
                "arduino_ok":       self.arduino_ok,
                "lidar_ok":         self.lidar_ok,
                "db_ok":            self.db_ok,
                "nav_ok":           self.nav_ok,
                "cpu_temp":         round(self.cpu_temp, 1),
                "cpu_usage":        round(self.cpu_usage, 1),
                "ram_usage":        round(self.ram_usage, 1),
                "delivery_id":      self.delivery_id,
                "delivery_status":  self.delivery_status,
                "rack_id":          self.rack_id,
                "rack_status":      self.rack_statuses,
                "timestamp":        time.strftime("%H:%M:%S"),
            }


# ── ROS2 Node ──────────────────────────────────────────────────────────────────
class AuraBridgeNode(Node):
    """ROS2 node that subscribes to all AURA topics."""

    def __init__(self, state: TelemetryState):
        super().__init__("aura_ros2_bridge")
        self._state = state
        self._log = self.get_logger()

        # ── Subscriptions ───────────────────────────────────────────────────
        self.create_subscription(Odometry,   "/odom",           self._cb_odom,    10)
        self.create_subscription(Float32,    "/battery_percent",self._cb_battery, 10)
        self.create_subscription(String,     "/aura/robot_state", self._cb_state, 10)
        self.create_subscription(String,     "/aura/mission",   self._cb_mission, 10)
        self.create_subscription(Bool,       "/aura/arduino_ok",self._cb_arduino, 10)
        self.create_subscription(Bool,       "/aura/lidar_ok",  self._cb_lidar,   10)
        self.create_subscription(Bool,       "/aura/db_ok",     self._cb_db,      10)
        self.create_subscription(Bool,       "/aura/nav_ok",    self._cb_nav,     10)
        self.create_subscription(Float32,    "/aura/cpu_temp",  self._cb_cpu_temp,10)
        self.create_subscription(Float32,    "/aura/cpu_usage", self._cb_cpu_use, 10)
        self.create_subscription(Float32,    "/aura/ram_usage", self._cb_ram,     10)
        self.create_subscription(String,     "/aura/rack_states",self._cb_racks,  10)

        # ── Publishers ─────────────────────────────────────────────────────
        self.estop_pub    = self.create_publisher(Bool,         "/aura/estop",       10)
        self.cancel_pub   = self.create_publisher(String,       "/aura/cancel_task", 10)
        self.goal_pub     = self.create_publisher(PoseStamped,  "/goal_pose",        10)
        self.servo_pub    = self.create_publisher(String,       "/aura/servo_cmd",   10)

        self._log.info("AuraBridgeNode initialised — all topics subscribed.")

    # ── Callbacks ─────────────────────────────────────────────────────────────
    def _cb_odom(self, msg: Odometry):
        p = msg.pose.pose
        # Convert quaternion to yaw
        q = p.orientation
        yaw = math.atan2(2*(q.w*q.z + q.x*q.y), 1 - 2*(q.y*q.y + q.z*q.z))
        # Approximate forward velocity
        v = math.hypot(msg.twist.twist.linear.x, msg.twist.twist.linear.y)
        self._state.update(x=p.position.x, y=p.position.y, heading=yaw, velocity=v)

    def _cb_battery(self, msg: Float32):
        self._state.update(battery=msg.data)

    def _cb_state(self, msg: String):
        self._state.update(status=msg.data)

    def _cb_mission(self, msg: String):
        self._state.update(mission=msg.data)

    def _cb_arduino(self, msg: Bool):
        self._state.update(arduino_ok=msg.data)

    def _cb_lidar(self, msg: Bool):
        self._state.update(lidar_ok=msg.data)

    def _cb_db(self, msg: Bool):
        self._state.update(db_ok=msg.data)

    def _cb_nav(self, msg: Bool):
        self._state.update(nav_ok=msg.data)

    def _cb_cpu_temp(self, msg: Float32):
        self._state.update(cpu_temp=msg.data)

    def _cb_cpu_use(self, msg: Float32):
        self._state.update(cpu_usage=msg.data)

    def _cb_ram(self, msg: Float32):
        self._state.update(ram_usage=msg.data)

    def _cb_racks(self, msg: String):
        try:
            racks = json.loads(msg.data)  # expects ["locked","locked","unlocked","locked"]
            self._state.update(rack_statuses=racks)
        except Exception:
            pass

    # ── Command handlers (called from async context via run_in_executor) ──────
    def handle_command(self, payload: dict):
        action = payload.get("action", "")
        try:
            if action == "estop":
                msg = Bool()
                msg.data = bool(payload.get("param", True))
                self.estop_pub.publish(msg)
                self._log.info(f"E-stop: {msg.data}")

            elif action == "return_to_base":
                goal = PoseStamped()
                goal.header.frame_id = "map"
                goal.pose.position.x = 0.0
                goal.pose.position.y = 0.0
                goal.pose.orientation.w = 1.0
                self.goal_pub.publish(goal)
                self._state.update(status="returning", mission="Returning to Base")
                self._log.info("Return to base goal published.")

            elif action in ("unlock_rack", "open_rack"):
                rack_id = payload.get("rack_id", 1)
                cmd = json.dumps({"action": "open", "rack": rack_id})
                msg = String()
                msg.data = cmd
                self.servo_pub.publish(msg)
                self._log.info(f"Servo open command published for rack {rack_id}")

            elif action == "cancel_task":
                msg = String()
                msg.data = "cancel"
                self.cancel_pub.publish(msg)
                self._log.info("Cancel task published.")

            elif action == "force_complete":
                msg = String()
                msg.data = "force_complete"
                self.cancel_pub.publish(msg)

        except Exception as exc:
            self._log.error(f"Command handler error ({action}): {exc}")


# ── Mock Telemetry (fallback when not running on real ROS2 hardware) ───────────
class MockTelemetrySimulator:
    """Simulates realistic robot telemetry for development / CI."""

    def __init__(self, state: TelemetryState):
        self._state = state
        self._t = 0.0
        self._missions = [
            "Delivering to Lab 302 — Chemistry",
            "Delivering to Lab 104 — Physics",
            "Returning to Base",
            "Standby — Awaiting next task",
            "Charging at Dock A",
        ]

    def step(self):
        self._t += 0.05
        x = 3.0 * math.sin(self._t)
        y = 2.0 * math.sin(2 * self._t)
        battery = max(0.0, 100 - self._t * 0.05)
        cpu_temp = 42.0 + 10.0 * abs(math.sin(self._t / 3)) + random.uniform(-1, 1)

        updates = dict(
            x=x, y=y,
            battery=battery,
            cpu_temp=cpu_temp,
            cpu_usage=random.uniform(15, 45),
            ram_usage=random.uniform(30, 55),
            arduino_ok=True,
            lidar_ok=True,
            db_ok=True,
            nav_ok=True,
        )

        if random.random() < 0.008:
            mission = random.choice(self._missions)
            status = "navigating" if "Delivering" in mission else (
                "charging" if "Charging" in mission else "idle"
            )
            updates["mission"] = mission
            updates["status"] = status

        self._state.update(**updates)


# ── WebSocket client ───────────────────────────────────────────────────────────
async def ws_client_loop(state: TelemetryState, ros_node: Optional[AuraBridgeNode]):
    """Main async loop: connect → stream telemetry → handle commands."""
    interval = 1.0 / PUBLISH_HZ

    while True:
        try:
            logger.info(f"Connecting to backend at {BACKEND_WS_URL} …")
            async with websockets.connect(
                BACKEND_WS_URL,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=10,
            ) as ws:
                logger.info("✓ Connected to backend WebSocket.")

                async def sender():
                    """Continuously stream telemetry to backend."""
                    while True:
                        payload = state.to_dict()
                        await ws.send(json.dumps(payload))
                        await asyncio.sleep(interval)

                async def receiver():
                    """Receive commands from backend and dispatch to ROS2."""
                    async for raw in ws:
                        try:
                            cmd = json.loads(raw)
                            if cmd.get("type") == "command" and ros_node:
                                loop = asyncio.get_event_loop()
                                await loop.run_in_executor(
                                    None, ros_node.handle_command, cmd
                                )
                        except Exception as e:
                            logger.warning(f"Command parse error: {e}")

                # Run both concurrently; if either raises, reconnect
                await asyncio.gather(sender(), receiver())

        except Exception as exc:
            logger.warning(f"WebSocket disconnected: {exc}. Retrying in 5 s …")
            await asyncio.sleep(5)


# ── Entry point ────────────────────────────────────────────────────────────────
def main(args=None):
    if not HAS_WEBSOCKETS:
        logger.error("websockets not installed. Run: pip install websockets")
        return

    state = TelemetryState()

    # Try to initialise ROS2
    ros_node: Optional[AuraBridgeNode] = None
    executor: Optional[MultiThreadedExecutor] = None

    try:
        rclpy.init(args=args)
        ros_node = AuraBridgeNode(state)
        executor = MultiThreadedExecutor(num_threads=4)
        executor.add_node(ros_node)

        # Spin ROS2 in a background thread
        ros_thread = threading.Thread(target=executor.spin, daemon=True)
        ros_thread.start()
        logger.info("ROS2 executor started in background thread.")

    except Exception as e:
        logger.warning(f"ROS2 init failed ({e}) — running in mock/telemetry mode.")
        mock_sim = MockTelemetrySimulator(state)

        async def mock_stepper():
            while True:
                mock_sim.step()
                await asyncio.sleep(0.1)

        # Will be started inside the asyncio loop below
        asyncio.get_event_loop().create_task(mock_stepper()) if False else None

    async def run():
        # Start mock stepper if no ROS2
        if ros_node is None:
            mock_sim = MockTelemetrySimulator(state)
            asyncio.create_task(async_mock_step(mock_sim))

        await ws_client_loop(state, ros_node)

    async def async_mock_step(sim: MockTelemetrySimulator):
        while True:
            sim.step()
            await asyncio.sleep(0.1)

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Bridge shutting down …")
    finally:
        if ros_node:
            ros_node.destroy_node()
        if executor:
            executor.shutdown()
        try:
            rclpy.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    main()
