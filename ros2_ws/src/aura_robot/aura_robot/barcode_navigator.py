#!/usr/bin/env python3
"""
aura_robot/barcode_navigator.py
================================
Scans barcodes (USB HID barcode scanner or camera-based), looks up the
destination in PostgreSQL, and publishes the navigation goal.

Subscribes:  nothing (reads directly from stdin/tty or camera)
Publishes:
  /aura/barcode_detection  (std_msgs/String — JSON BarcodeDetection payload)
  /aura/mission            (std_msgs/String — human-readable destination)

The barcode value is a simple string like "LAB-302-CHEM" that maps
to a PostgreSQL row in the `barcode_locations` table.

Table schema (auto-created if missing):
  barcode_locations (
    id SERIAL PRIMARY KEY,
    barcode_value TEXT UNIQUE NOT NULL,
    department    TEXT,
    room          TEXT,
    nav_goal_name TEXT,
    goal_x        FLOAT,
    goal_y        FLOAT,
    goal_theta    FLOAT,
    created_at    TIMESTAMP DEFAULT NOW()
  )
"""

import os
import json
import sys
import threading
import logging

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

try:
    import psycopg2
    import psycopg2.pool
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

try:
    import evdev
    HAS_EVDEV = True
except ImportError:
    HAS_EVDEV = False

logger = logging.getLogger("aura.barcode_navigator")

DB_URL    = os.getenv("DATABASE_URL", "postgresql://robot_user:robot_password@localhost:5435/labrobot")
MOCK_MODE = os.getenv("BARCODE_MOCK", "false").lower() == "true"

# Keyboard HID key map for USB barcode scanners
KEY_MAP = {
    2:"1",3:"2",4:"3",5:"4",6:"5",7:"6",8:"7",9:"8",10:"9",11:"0",
    16:"q",17:"w",18:"e",19:"r",20:"t",21:"y",22:"u",23:"i",24:"o",25:"p",
    30:"a",31:"s",32:"d",33:"f",34:"g",35:"h",36:"j",37:"k",38:"l",
    44:"z",45:"x",46:"c",47:"v",48:"b",49:"n",50:"m",
    12:"-",13:"=",26:"[",27:"]",39:";",40:"'",41:"`",43:"\\",51:",",52:".",53:"/",
}


class BarcodeNavigatorNode(Node):

    def __init__(self):
        super().__init__("aura_barcode_navigator")
        self._log = self.get_logger()

        self._pub_barcode = self.create_publisher(String, "/aura/barcode_detection", 10)
        self._pub_mission = self.create_publisher(String, "/aura/mission", 10)

        # Database pool
        self._db_pool = None
        self._init_db()

        if MOCK_MODE:
            self._log.info("Barcode scanner running in MOCK mode.")
            self.create_timer(15.0, self._mock_scan)
        elif HAS_EVDEV:
            self._start_evdev_reader()
        else:
            self._log.warning("evdev not available — using stdin barcode input.")
            threading.Thread(target=self._stdin_reader, daemon=True).start()

        self._log.info("BarcodeNavigator ready.")

    # ── Database ──────────────────────────────────────────────────────────────
    def _init_db(self):
        if not HAS_PSYCOPG2:
            self._log.warning("psycopg2 not available — barcode DB lookups disabled.")
            return
        try:
            self._db_pool = psycopg2.pool.SimpleConnectionPool(1, 3, DB_URL)
            # Ensure barcode_locations table exists
            conn = self._db_pool.getconn()
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS barcode_locations (
                        id            SERIAL PRIMARY KEY,
                        barcode_value TEXT UNIQUE NOT NULL,
                        department    TEXT,
                        room          TEXT,
                        nav_goal_name TEXT,
                        goal_x        FLOAT DEFAULT 0.0,
                        goal_y        FLOAT DEFAULT 0.0,
                        goal_theta    FLOAT DEFAULT 0.0,
                        created_at    TIMESTAMP DEFAULT NOW()
                    );
                    -- Seed demo locations if empty
                    INSERT INTO barcode_locations (barcode_value, department, room, nav_goal_name, goal_x, goal_y)
                    VALUES
                      ('LAB-101-PHYS', 'Physics',    'Lab 101', 'lab_101', 3.5, 1.2),
                      ('LAB-202-CHEM', 'Chemistry',  'Lab 202', 'lab_202', 5.1, 4.8),
                      ('LAB-302-BIO',  'Biology',    'Lab 302', 'lab_302', 2.3, 7.6),
                      ('LAB-401-CS',   'Comp. Sci.', 'Lab 401', 'lab_401', 8.0, 3.0)
                    ON CONFLICT (barcode_value) DO NOTHING;
                """)
                conn.commit()
            self._db_pool.putconn(conn)
            self._log.info("Barcode DB initialised.")
        except Exception as e:
            self._log.error(f"DB init error: {e}")
            self._db_pool = None

    def _lookup_barcode(self, value: str) -> dict:
        if not self._db_pool:
            return {"valid": False, "error_message": "DB unavailable"}
        try:
            conn = self._db_pool.getconn()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT department,room,nav_goal_name,goal_x,goal_y,goal_theta "
                    "FROM barcode_locations WHERE barcode_value=%s", (value,)
                )
                row = cur.fetchone()
            self._db_pool.putconn(conn)
            if row:
                return {
                    "barcode_value": value,
                    "department":    row[0],
                    "room":          row[1],
                    "nav_goal_name": row[2],
                    "goal_x":        row[3],
                    "goal_y":        row[4],
                    "goal_theta":    row[5],
                    "valid":         True,
                    "error_message": "",
                }
            return {"barcode_value": value, "valid": False, "error_message": "Unknown barcode"}
        except Exception as e:
            return {"valid": False, "error_message": str(e)}

    # ── Publish ───────────────────────────────────────────────────────────────
    def _on_barcode(self, raw: str):
        raw = raw.strip()
        if not raw:
            return
        self._log.info(f"Barcode scanned: {raw}")
        result = self._lookup_barcode(raw)
        msg = String()
        msg.data = json.dumps(result)
        self._pub_barcode.publish(msg)

        if result.get("valid"):
            m = String()
            m.data = f"Destination: {result['department']} — {result['room']}"
            self._pub_mission.publish(m)
            self._log.info(f"Published navigation destination: {result['room']}")

    # ── Input drivers ─────────────────────────────────────────────────────────
    def _start_evdev_reader(self):
        """Read from USB HID barcode scanner via evdev (Linux only)."""
        def reader():
            try:
                devices = [evdev.InputDevice(p) for p in evdev.list_devices()]
                scanner = None
                for d in devices:
                    if "barcode" in d.name.lower() or "scanner" in d.name.lower():
                        scanner = d
                        break
                if not scanner:
                    scanner = devices[0] if devices else None

                if not scanner:
                    self._log.warning("No HID scanner found — falling back to stdin.")
                    self._stdin_reader()
                    return

                self._log.info(f"HID scanner: {scanner.name}")
                buf = ""
                for event in scanner.read_loop():
                    if event.type == evdev.ecodes.EV_KEY and event.value == 1:
                        if event.code == 28:  # ENTER
                            self._on_barcode(buf)
                            buf = ""
                        else:
                            buf += KEY_MAP.get(event.code, "")
            except Exception as e:
                self._log.error(f"evdev reader failed: {e} — falling back to stdin.")
                self._stdin_reader()

        threading.Thread(target=reader, daemon=True).start()

    def _stdin_reader(self):
        """Read barcodes line-by-line from stdin (useful for testing)."""
        for line in sys.stdin:
            self._on_barcode(line.strip())

    def _mock_scan(self):
        """Periodically fire a mock barcode scan (for demo/development)."""
        import random
        codes = ["LAB-101-PHYS", "LAB-202-CHEM", "LAB-302-BIO", "LAB-401-CS"]
        self._on_barcode(random.choice(codes))


def main(args=None):
    rclpy.init(args=args)
    node = BarcodeNavigatorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
