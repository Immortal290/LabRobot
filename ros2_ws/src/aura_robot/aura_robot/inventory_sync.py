#!/usr/bin/env python3
"""
aura_robot/inventory_sync.py
============================
Subscribes to delivery completions and automatically:
  ▸ Decrements inventory quantity in PostgreSQL
  ▸ Updates `available` flag when stock hits zero
  ▸ Stores transaction timestamp
  ▸ Publishes an InventoryUpdate event for the GUI

Subscribes:
  /aura/delivery_task  (std_msgs/String — JSON delivery object)

Publishes:
  /aura/inventory_update (std_msgs/String — JSON InventoryUpdate)
"""

import os
import json
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

logger = logging.getLogger("aura.inventory_sync")

DB_URL      = os.getenv("DATABASE_URL", "postgresql://robot_user:robot_password@localhost:5435/labrobot")
BACKEND_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000/api/v1")

DISPENSE_STATUSES = {"pickup_confirmed", "completed"}


class InventorySyncNode(Node):

    def __init__(self):
        super().__init__("aura_inventory_sync")
        self._log = self.get_logger()

        self._db_pool = None
        self._processed: set = set()   # delivery IDs already processed
        self._init_db()

        self._pub_inv = self.create_publisher(String, "/aura/inventory_update", 10)
        self.create_subscription(String, "/aura/delivery_task", self._cb_delivery, 10)

        self._log.info("InventorySync ready.")

    def _init_db(self):
        if not HAS_PSYCOPG2:
            return
        try:
            self._db_pool = psycopg2.pool.SimpleConnectionPool(1, 3, DB_URL)
            self._log.info("InventorySync DB pool ready.")
        except Exception as e:
            self._log.error(f"DB pool init failed: {e}")

    def _cb_delivery(self, msg: String):
        try:
            delivery = json.loads(msg.data)
        except Exception as e:
            self._log.warning(f"Delivery JSON parse error: {e}")
            return

        status      = delivery.get("status", "")
        delivery_id = delivery.get("delivery_id") or delivery.get("id")
        item_id     = delivery.get("item_id")
        rack_id     = delivery.get("rack_id")

        if status not in DISPENSE_STATUSES:
            return
        if not delivery_id or not item_id:
            return
        if delivery_id in self._processed:
            return   # Idempotent — only process each delivery once

        self._processed.add(delivery_id)
        self._update_inventory(delivery_id, item_id, rack_id)

    def _update_inventory(self, delivery_id: int, item_id: int, rack_id: int | None):
        if not self._db_pool:
            self._log.warning("No DB pool — inventory update skipped.")
            return
        conn = None
        try:
            conn = self._db_pool.getconn()
            with conn.cursor() as cur:
                # Fetch current quantity
                cur.execute(
                    "SELECT name, quantity FROM inventory WHERE id = %s FOR UPDATE",
                    (item_id,)
                )
                row = cur.fetchone()
                if not row:
                    self._log.warning(f"Item {item_id} not found in inventory.")
                    return

                name, qty = row
                new_qty   = max(0, qty - 1)
                available = new_qty > 0

                cur.execute(
                    "UPDATE inventory SET quantity=%s, available=%s, last_transaction=NOW() "
                    "WHERE id=%s",
                    (new_qty, available, item_id)
                )

                # If rack assigned, clear its assigned_item
                if rack_id:
                    cur.execute(
                        "UPDATE racks SET delivery_status='idle' WHERE id=%s",
                        (rack_id,)
                    )

                # Log transaction
                cur.execute(
                    "INSERT INTO logs (event_type, description) VALUES (%s, %s)",
                    ("inventory",
                     f"Dispensed 1x '{name}' (Item #{item_id}) via Delivery #{delivery_id}. "
                     f"Stock: {qty} → {new_qty}.")
                )
                conn.commit()

            self._log.info(f"Inventory updated: item {item_id} qty {qty}→{new_qty}")

            # Publish ROS update event
            event = {
                "item_id":        item_id,
                "item_name":      name,
                "quantity_before": qty,
                "quantity_after":  new_qty,
                "action":         "dispense",
                "delivery_id":    delivery_id,
                "rack_id":        rack_id or 0,
                "success":        True,
                "message":        f"1x {name} dispensed. Remaining: {new_qty}",
            }
            pub_msg = String(); pub_msg.data = json.dumps(event)
            self._pub_inv.publish(pub_msg)

        except Exception as e:
            self._log.error(f"Inventory update DB error: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                try:
                    self._db_pool.putconn(conn)
                except Exception:
                    pass


def main(args=None):
    rclpy.init(args=args)
    node = InventorySyncNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
