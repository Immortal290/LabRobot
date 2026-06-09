import time
import json
import math
import random
import os
import asyncio

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    print("Warning: websockets not installed. Install with: pip install websockets")

try:
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import Float32
    from nav_msgs.msg import Odometry
    ON_ROS = True
except ImportError:
    ON_ROS = False
    print("Warning: rclpy not found. Running in mock telemetry mode.")

BACKEND_WS_URL = os.getenv("BACKEND_URL", "ws://localhost:8000/ws")

# --- Mock telemetry state ---
class MockTelemetry:
    def __init__(self):
        self.battery = 100.0
        self.cpu_temp = 40.0
        self.x = 0.0
        self.y = 0.0
        self.t = 0.0  # time parameter for lissajous path
        self.status = "Idle"
        self.mission = "Standby"
        self.rack_status = ["locked", "locked", "locked", "locked"]

    def step(self):
        self.t += 0.05
        # Lissajous figure for robot path
        self.x = 3.0 * math.sin(self.t)
        self.y = 2.0 * math.sin(2 * self.t)
        self.battery = max(0.0, self.battery - random.uniform(0.01, 0.05))
        self.cpu_temp = 40.0 + 15.0 * abs(math.sin(self.t / 3)) + random.uniform(-1, 1)

        missions = ["Delivering to Lab 302", "Returning to Base", "Standby", "Charging"]
        if random.random() < 0.02:
            self.mission = random.choice(missions)
            self.status = "Active" if "Delivering" in self.mission else "Idle"

    def to_json(self):
        return {
            "type": "telemetry",
            "battery": round(self.battery, 2),
            "cpu_temp": round(self.cpu_temp, 2),
            "x": round(self.x, 3),
            "y": round(self.y, 3),
            "status": self.status,
            "mission": self.mission,
            "rack_status": self.rack_status,
            "timestamp": time.strftime("%H:%M:%S"),
        }

LOG_EVENTS = [
    "Navigation goal set: Lab 302",
    "Obstacle detected, replanning route",
    "Rack 2 access granted",
    "Battery threshold warning at 20%",
    "SLAM map updated",
    "Hardware Button 3 pressed",
    "Delivery confirmed at Lab 101",
    "Robot returned to base",
]

async def run_mock_bridge():
    telemetry = MockTelemetry()
    log_ticker = 0

    while True:
        try:
            print(f"Connecting to backend WebSocket at {BACKEND_WS_URL}...")
            async with websockets.connect(BACKEND_WS_URL) as ws:
                print("ROS2 Bridge connected to backend WebSocket!")
                while True:
                    telemetry.step()
                    payload = telemetry.to_json()

                    # Every ~5 seconds, also send a log event
                    log_ticker += 1
                    if log_ticker % 10 == 0:
                        payload["log"] = random.choice(LOG_EVENTS)

                    await ws.send(json.dumps(payload))
                    await asyncio.sleep(0.5)

        except Exception as e:
            print(f"WebSocket connection failed: {e}. Retrying in 5s...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    if not HAS_WEBSOCKETS:
        print("ERROR: Please install the websockets library: pip install websockets")
        exit(1)

    print("Starting LabRobot ROS2 Bridge...")
    asyncio.run(run_mock_bridge())
