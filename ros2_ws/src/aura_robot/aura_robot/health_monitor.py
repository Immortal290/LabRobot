#!/usr/bin/env python3
"""
aura_robot/health_monitor.py
============================
Monitors all hardware and software components continuously.

Publishes:
  /aura/system_health  (std_msgs/String — JSON payload)
  /aura/arduino_ok     (std_msgs/Bool)
  /aura/lidar_ok       (std_msgs/Bool)
  /aura/db_ok          (std_msgs/Bool)
  /aura/nav_ok         (std_msgs/Bool)
  /aura/cpu_temp       (std_msgs/Float32)
  /aura/cpu_usage      (std_msgs/Float32)
  /aura/ram_usage      (std_msgs/Float32)

Checks (every 2 s unless stated otherwise):
  ▸ Arduino serial port (serial.Serial)
  ▸ LiDAR USB device presence
  ▸ PostgreSQL connectivity (psycopg2)
  ▸ Nav2 stack nodes (ros2 node list)
  ▸ CPU temperature (thermal_zone0)
  ▸ CPU / RAM usage (psutil)

Auto-recovery:
  ▸ Publishes reconnect commands on /aura/reconnect if a component fails.
"""

import os
import json
import time
import glob
import subprocess
import threading
import logging
from typing import Optional

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, Float32, String

try:
    import serial
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import psycopg2
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

logger = logging.getLogger("aura.health_monitor")

# ── Configuration from environment ────────────────────────────────────────────
ARDUINO_PORT  = os.getenv("ARDUINO_PORT",  "/dev/ttyUSB0")
LIDAR_PORT    = os.getenv("LIDAR_PORT",    "/dev/ttyUSB1")
DB_URL        = os.getenv("DATABASE_URL",  "postgresql://robot_user:robot_password@localhost:5435/labrobot")
CHECK_HZ      = float(os.getenv("HEALTH_CHECK_HZ", "0.5"))   # 0.5 Hz = every 2 s

EXPECTED_NAV_NODES = [
    "/controller_server",
    "/planner_server",
    "/bt_navigator",
    "/map_server",
]


class HealthMonitorNode(Node):
    """ROS2 node that continuously probes system health and publishes results."""

    def __init__(self):
        super().__init__("aura_health_monitor")
        self._log = self.get_logger()

        # ── Publishers ─────────────────────────────────────────────────────
        self._pub_arduino  = self.create_publisher(Bool,   "/aura/arduino_ok", 10)
        self._pub_lidar    = self.create_publisher(Bool,   "/aura/lidar_ok",   10)
        self._pub_db       = self.create_publisher(Bool,   "/aura/db_ok",      10)
        self._pub_nav      = self.create_publisher(Bool,   "/aura/nav_ok",     10)
        self._pub_cpu_temp = self.create_publisher(Float32,"/aura/cpu_temp",   10)
        self._pub_cpu_use  = self.create_publisher(Float32,"/aura/cpu_usage",  10)
        self._pub_ram      = self.create_publisher(Float32,"/aura/ram_usage",  10)
        self._pub_health   = self.create_publisher(String, "/aura/system_health", 10)
        self._pub_reconnect= self.create_publisher(String, "/aura/reconnect",  10)

        # ── State ──────────────────────────────────────────────────────────
        self._status = {
            "arduino": False, "lidar": False,
            "db": False,      "nav": False,
        }
        self._consecutive_failures: dict = {k: 0 for k in self._status}

        # ── Timer ──────────────────────────────────────────────────────────
        self.create_timer(1.0 / CHECK_HZ, self._check_all)
        self._log.info("HealthMonitor ready — checks every %.1f s." % (1.0 / CHECK_HZ))

    # ─────────────────────────────────────────────────────────────────────────
    def _check_all(self):
        results = {}
        results["arduino"] = self._check_arduino()
        results["lidar"]   = self._check_lidar()
        results["db"]      = self._check_db()
        results["nav"]     = self._check_nav_stack()

        cpu_temp = self._read_cpu_temp()
        cpu_use  = self._read_cpu_usage()
        ram_use  = self._read_ram_usage()

        # Publish Bool topics
        def pub_bool(pub, ok: bool):
            m = Bool(); m.data = ok; pub.publish(m)

        pub_bool(self._pub_arduino, results["arduino"])
        pub_bool(self._pub_lidar,   results["lidar"])
        pub_bool(self._pub_db,      results["db"])
        pub_bool(self._pub_nav,     results["nav"])

        def pub_f32(pub, val: float):
            m = Float32(); m.data = float(val); pub.publish(m)

        pub_f32(self._pub_cpu_temp, cpu_temp)
        pub_f32(self._pub_cpu_use,  cpu_use)
        pub_f32(self._pub_ram,      ram_use)

        # Determine overall status
        critical_ok  = results["db"] and results["arduino"]
        all_ok       = all(results.values())
        overall      = "healthy" if all_ok else ("degraded" if critical_ok else "critical")

        # Attempt auto-recovery on repeated failures
        for component, ok in results.items():
            if not ok:
                self._consecutive_failures[component] += 1
                if self._consecutive_failures[component] >= 3:
                    self._trigger_reconnect(component)
            else:
                self._consecutive_failures[component] = 0

        self._status = results

        # Publish health summary
        health = {
            "arduino_ok":   results["arduino"],
            "lidar_ok":     results["lidar"],
            "db_ok":        results["db"],
            "nav_ok":       results["nav"],
            "cpu_temp":     round(cpu_temp, 1),
            "cpu_usage":    round(cpu_use, 1),
            "ram_usage":    round(ram_use, 1),
            "overall":      overall,
        }
        m = String(); m.data = json.dumps(health); self._pub_health.publish(m)

    # ── Individual checks ─────────────────────────────────────────────────────
    def _check_arduino(self) -> bool:
        """Check if the Arduino serial port is accessible."""
        if not HAS_SERIAL:
            return os.path.exists(ARDUINO_PORT)
        try:
            with serial.Serial(ARDUINO_PORT, 9600, timeout=0.5) as s:
                return s.is_open
        except Exception:
            # Try alternate ports
            for alt in ["/dev/ttyACM0", "/dev/ttyACM1", "/dev/ttyUSB0"]:
                if alt != ARDUINO_PORT and os.path.exists(alt):
                    try:
                        with serial.Serial(alt, 9600, timeout=0.5) as s:
                            if s.is_open:
                                self._log.warning(f"Arduino found on {alt} (not {ARDUINO_PORT})")
                                return True
                    except Exception:
                        pass
            return False

    def _check_lidar(self) -> bool:
        """Check if LiDAR USB device is present."""
        if os.path.exists(LIDAR_PORT):
            return True
        # Scan for YDLIDAR device patterns
        candidates = glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")
        # Exclude the one reserved for Arduino
        arduino_path = ARDUINO_PORT
        for c in candidates:
            if c != arduino_path:
                return True   # Found a second serial device → likely the LiDAR
        return False

    def _check_db(self) -> bool:
        """Ping the PostgreSQL database."""
        if not HAS_PSYCOPG2:
            return False
        try:
            conn = psycopg2.connect(DB_URL, connect_timeout=2)
            conn.close()
            return True
        except Exception:
            return False

    def _check_nav_stack(self) -> bool:
        """Check if Nav2 nodes are alive via ros2 node list."""
        try:
            result = subprocess.run(
                ["ros2", "node", "list"],
                capture_output=True, text=True, timeout=3
            )
            active = result.stdout
            return any(n in active for n in EXPECTED_NAV_NODES)
        except Exception:
            return False

    def _read_cpu_temp(self) -> float:
        """Read CPU temperature from Raspberry Pi thermal zone."""
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                return int(f.read().strip()) / 1000.0
        except Exception:
            if HAS_PSUTIL:
                temps = psutil.sensors_temperatures()
                for zone in temps.values():
                    if zone:
                        return zone[0].current
            return 45.0

    def _read_cpu_usage(self) -> float:
        if HAS_PSUTIL:
            return psutil.cpu_percent(interval=None)
        return 0.0

    def _read_ram_usage(self) -> float:
        if HAS_PSUTIL:
            return psutil.virtual_memory().percent
        return 0.0

    def _trigger_reconnect(self, component: str):
        """Publish a reconnect request for a failed component."""
        msg = String()
        msg.data = json.dumps({"component": component, "action": "reconnect"})
        self._pub_reconnect.publish(msg)
        self._log.warning(f"Auto-reconnect triggered for: {component}")
        self._consecutive_failures[component] = 0  # Reset to avoid spam


def main(args=None):
    rclpy.init(args=args)
    node = HealthMonitorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
