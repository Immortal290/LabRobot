import asyncio
import json
import uuid
import datetime
import random
import aiomqtt
import argparse

BROKER = "localhost"
PORT = 1883
ROBOT_ID = "ROBOT_01"

async def simulate_robot():
    print(f"[{ROBOT_ID}] Connecting to MQTT broker at {BROKER}:{PORT}")
    try:
        async with aiomqtt.Client(hostname=BROKER, port=PORT) as client:
            print(f"[{ROBOT_ID}] Connected! Starting heartbeat task...")
            
            # Start heartbeat loop
            async def heartbeat():
                while True:
                    payload = {
                        "robot_id": ROBOT_ID,
                        "status": "ONLINE",
                        "battery": round(random.uniform(70.0, 100.0), 1),
                        "timestamp": datetime.datetime.utcnow().isoformat()
                    }
                    await client.publish(f"robot/{ROBOT_ID}/heartbeat", json.dumps(payload))
                    await asyncio.sleep(5)
            
            asyncio.create_task(heartbeat())
            
            # Subscribe to commands
            topic = f"robot/{ROBOT_ID}/command"
            await client.subscribe(topic)
            print(f"[{ROBOT_ID}] Listening for commands on {topic}")
            
            async for message in client.messages:
                payload = message.payload.decode()
                try:
                    data = json.loads(payload)
                    cmd = data.get("command")
                    order_id = data.get("order_id", "UNKNOWN")
                    print(f"\n[{ROBOT_ID}] Received COMMAND: {cmd} for Order: {order_id}")
                    
                    if cmd == "DELIVER":
                        print(f"[{ROBOT_ID}] -> Simulating NAVIGATING...")
                        await asyncio.sleep(1)
                        await client.publish(f"robot/{ROBOT_ID}/status", json.dumps({
                            "robot_id": ROBOT_ID, "order_id": order_id, "status": "NAVIGATING"
                        }))
                        
                        print(f"[{ROBOT_ID}] -> Simulating travel time (5 seconds)...")
                        await asyncio.sleep(5)
                        
                        print(f"[{ROBOT_ID}] -> Simulating ARRIVED...")
                        await client.publish(f"robot/{ROBOT_ID}/status", json.dumps({
                            "robot_id": ROBOT_ID, "order_id": order_id, "status": "ARRIVED"
                        }))
                        
                    elif cmd == "UNLOCK_COMPARTMENT":
                        print(f"[{ROBOT_ID}] -> Unlocking compartment...")
                        await asyncio.sleep(1)
                        await client.publish(f"robot/{ROBOT_ID}/status", json.dumps({
                            "robot_id": ROBOT_ID, "order_id": order_id, "status": "COMPARTMENT_OPEN"
                        }))
                        
                        print(f"[{ROBOT_ID}] -> Simulating user taking item (5 seconds)...")
                        await asyncio.sleep(5)
                        await client.publish(f"robot/{ROBOT_ID}/status", json.dumps({
                            "robot_id": ROBOT_ID, "order_id": order_id, "status": "ITEM_COLLECTED"
                        }))
                        
                        print(f"[{ROBOT_ID}] -> Simulating return to base...")
                        await asyncio.sleep(1)
                        await client.publish(f"robot/{ROBOT_ID}/status", json.dumps({
                            "robot_id": ROBOT_ID, "order_id": order_id, "status": "DELIVERY_COMPLETED"
                        }))
                        
                except json.JSONDecodeError:
                    print(f"[{ROBOT_ID}] Invalid JSON payload: {payload}")
                
    except Exception as e:
        print(f"[{ROBOT_ID}] MQTT Error: {e}")

if __name__ == "__main__":
    asyncio.run(simulate_robot())
