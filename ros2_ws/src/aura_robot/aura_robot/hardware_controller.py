#!/usr/bin/env python3
"""
aura_robot/hardware_controller.py
==================================
Manages all physical hardware via ROS2:
  ▸ Arduino Nano serial connection (servo commands)
  ▸ Flap open/close lifecycle with auto-close timeout
  ▸ Serial reconnection on disconnect
  ▸ Publishes acknowledgments back to ROS2

Subscribes:
  /aura/servo_cmd      (std_msgs/String  JSON {"action":"open"|"close","rack":N})
  /aura/reconnect      (std_msgs/String  JSON {"component":"arduino"})

Publishes:
  /aura/servo_ack      (std_msgs/String  JSON {"action":…,"rack":N,"acknowledged":T/F})
  /aura/arduino_ok     (std_msgs/Bool)
"""

import os
import json
import time
import threading
import logging

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String

try:
    import serial
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False

logger = logging.getLogger("aura.hardware_controller")

ARDUINO_PORT       = os.getenv("ARDUINO_PORT", "/dev/ttyUSB0")
ARDUINO_BAUD       = int(os.getenv("ARDUINO_BAUD", "9600"))
FLAP_AUTO_CLOSE_S  = float(os.getenv("FLAP_AUTO_CLOSE_S", "30.0"))
MAX_RETRY_ATTEMPTS = 5


class HardwareControllerNode(Node):

    def __init__(self):
        super().__init__("aura_hardware_controller")
        self._log = self.get_logger()

        self._serial: serial.Serial | None = None
        self._serial_lock = threading.Lock()
        self._open_flaps: dict[int, float] = {}  # rack_id → close-at timestamp

        # ── Publishers ─────────────────────────────────────────────────────
        self._pub_ack     = self.create_publisher(String, "/aura/servo_ack",  10)
        self._pub_arduino = self.create_publisher(Bool,   "/aura/arduino_ok", 10)

        # ── Subscriptions ───────────────────────────────────────────────────
        self.create_subscription(String, "/aura/servo_cmd",  self._cb_servo_cmd,  10)
        self.create_subscription(String, "/aura/reconnect",  self._cb_reconnect,  10)

        # ── Timers ──────────────────────────────────────────────────────────
        self.create_timer(5.0,  self._ensure_connected)   # Reconnect watchdog
        self.create_timer(1.0,  self._auto_close_check)   # Flap auto-close

        # Initial connect
        self._connect()
        self._log.info("HardwareController ready.")

    # ── Serial connection ─────────────────────────────────────────────────────
    def _connect(self) -> bool:
        if not HAS_SERIAL:
            self._log.warning("pyserial not installed — running in mock mode.")
            return False

        # Try configured port and common alternatives
        ports_to_try = [ARDUINO_PORT, "/dev/ttyACM0", "/dev/ttyACM1", "/dev/ttyUSB0", "/dev/ttyUSB1"]
        for port in ports_to_try:
            if not os.path.exists(port):
                continue
            try:
                with self._serial_lock:
                    if self._serial and self._serial.is_open:
                        self._serial.close()
                    self._serial = serial.Serial(port, ARDUINO_BAUD, timeout=1.0)
                    time.sleep(2.0)  # Allow Arduino to reset
                self._log.info(f"✓ Arduino connected on {port}")
                self._publish_arduino_ok(True)
                return True
            except Exception as e:
                self._log.warning(f"Could not connect on {port}: {e}")

        self._log.error("Arduino not found on any port — running in mock mode.")
        self._publish_arduino_ok(False)
        return False

    def _ensure_connected(self):
        connected = False
        with self._serial_lock:
            if self._serial:
                try:
                    connected = self._serial.is_open
                except Exception:
                    connected = False
        if not connected:
            self._connect()

    # ── Command handling ──────────────────────────────────────────────────────
    def _cb_servo_cmd(self, msg: String):
        try:
            cmd = json.loads(msg.data)
            action  = cmd.get("action", "").lower()
            rack_id = int(cmd.get("rack", 1))

            if action == "open":
                self._open_rack(rack_id)
            elif action == "close":
                self._close_rack(rack_id)
            else:
                self._log.warning(f"Unknown servo action: {action}")
        except Exception as e:
            self._log.error(f"Servo command parse error: {e}")

    def _cb_reconnect(self, msg: String):
        try:
            data = json.loads(msg.data)
            if data.get("component") == "arduino":
                self._log.info("Arduino reconnect requested via /aura/reconnect")
                self._connect()
        except Exception:
            pass

    # ── Flap control ──────────────────────────────────────────────────────────
    def _send_serial(self, command: str) -> bool:
        """Send a raw command string to Arduino. Returns True on success."""
        with self._serial_lock:
            if self._serial and self._serial.is_open:
                try:
                    self._serial.write(f"{command}\n".encode())
                    self._serial.flush()
                    # Wait for ACK (non-blocking with timeout)
                    deadline = time.time() + 2.0
                    while time.time() < deadline:
                        if self._serial.in_waiting:
                            line = self._serial.readline().decode("utf-8", errors="ignore").strip()
                            if line.startswith("ACK"):
                                return True
                    return True   # Assume success even without ACK
                except Exception as e:
                    self._log.error(f"Serial write failed: {e}")
                    self._publish_arduino_ok(False)
                    return False
            else:
                # Mock mode
                self._log.info(f"[MOCK Arduino] {command}")
                return True

    def _open_rack(self, rack_id: int):
        """Open a single rack flap. Refuse if another flap is already open."""
        if self._open_flaps:
            currently_open = list(self._open_flaps.keys())
            self._log.warning(f"Refusing to open rack {rack_id}: flap(s) {currently_open} already open.")
            self._publish_ack(rack_id, "open", acknowledged=False,
                              error=f"Flap {currently_open[0]} already open")
            return

        success = self._send_serial(f"OPEN:{rack_id}")
        if success:
            self._open_flaps[rack_id] = time.time() + FLAP_AUTO_CLOSE_S
            self._log.info(f"✓ Rack {rack_id} flap opened (auto-close in {FLAP_AUTO_CLOSE_S:.0f}s)")
        self._publish_ack(rack_id, "open", acknowledged=success)

    def _close_rack(self, rack_id: int):
        success = self._send_serial(f"CLOSE:{rack_id}")
        self._open_flaps.pop(rack_id, None)
        if success:
            self._log.info(f"✓ Rack {rack_id} flap closed.")
        self._publish_ack(rack_id, "close", acknowledged=success)

    def _auto_close_check(self):
        """Auto-close any flap that has exceeded its timeout."""
        now = time.time()
        to_close = [rid for rid, deadline in self._open_flaps.items() if now >= deadline]
        for rack_id in to_close:
            self._log.info(f"Auto-closing rack {rack_id} (timeout).")
            self._close_rack(rack_id)

    # ── Publishers ────────────────────────────────────────────────────────────
    def _publish_ack(self, rack_id: int, action: str, acknowledged: bool, error: str = ""):
        payload = {
            "action":       action,
            "rack":         rack_id,
            "acknowledged": acknowledged,
            "error":        error,
        }
        msg = String()
        msg.data = json.dumps(payload)
        self._pub_ack.publish(msg)

    def _publish_arduino_ok(self, ok: bool):
        msg = Bool(); msg.data = ok; self._pub_arduino.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = HardwareControllerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
