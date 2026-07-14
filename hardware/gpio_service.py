import time
import os
import json
import asyncio
import websockets
import serial
from datetime import datetime

# Attempt to import gpiozero for direct Pi GPIO buttons
try:
    from gpiozero import Button
    import gpiozero.devices
    gpiozero.devices.Device.ensure_pin_factory()
    ON_PI = True
except Exception:
    print("Warning: gpiozero not found or not running on Raspberry Pi. Using mock GPIO for buttons.")
    ON_PI = False

WS_URL = os.getenv("WS_URL", "ws://localhost:8000/ws/bridge")
ARDUINO_PORT = os.getenv("ARDUINO_PORT", "/dev/ttyUSB0") # Default serial port for Arduino Nano
ARDUINO_BAUD = 9600

# Mock GPIO Classes for development on Windows
class MockButton:
    def __init__(self, pin):
        self.pin = pin
        self.when_pressed = None

    def press(self):
        if self.when_pressed:
            if asyncio.iscoroutinefunction(self.when_pressed):
                asyncio.create_task(self.when_pressed())
            else:
                self.when_pressed()

# Hardware Configuration
BUTTON_PINS = {
    'btn_rack_1': 17,
    'btn_rack_2': 27,
    'btn_rack_3': 22,
    'btn_rack_4': 23,
    'btn_estop': 24,
    'btn_home': 25,
    'btn_refresh': 5
}

buttons = {}

# Serial connection for Arduino Nano
arduino_serial = None

def init_gpio():
    global arduino_serial
    for name, pin in BUTTON_PINS.items():
        if ON_PI:
            buttons[name] = Button(pin, pull_up=True, bounce_time=0.1)
        else:
            buttons[name] = MockButton(pin)
            
    # Initialize Arduino Serial connection
    try:
        if os.name != 'nt': # Avoid failing instantly on Windows if port not found
            arduino_serial = serial.Serial(ARDUINO_PORT, ARDUINO_BAUD, timeout=1)
            print(f"Connected to Arduino Nano on {ARDUINO_PORT} at {ARDUINO_BAUD} baud.")
        else:
            print("Running on Windows, mocking Arduino Serial connection.")
            arduino_serial = None
    except Exception as e:
        print(f"Failed to connect to Arduino on {ARDUINO_PORT}: {e}")
        arduino_serial = None

async def send_event(websocket, event_type, description):
    try:
        if websocket and websocket.open:
            await websocket.send(json.dumps({
                "type": "hardware_event",
                "event_type": event_type,
                "description": description
            }))
        print(f"Hardware Event: {event_type} - {description}")
    except Exception as e:
        print(f"Error sending event: {e}")

async def send_arduino_command(cmd):
    global arduino_serial
    if arduino_serial and arduino_serial.is_open:
        try:
            # Run blocking serial write in executor
            await asyncio.to_thread(arduino_serial.write, f"{cmd}\n".encode())
            print(f"Sent to Arduino: {cmd}")
        except Exception as e:
            print(f"Failed to send to Arduino: {e}")
    else:
        print(f"[Mock Arduino] Sent command: {cmd}")

async def open_flap(rack_num, websocket=None):
    print(f"Opening flap for Rack {rack_num}...")
    # Send command to Arduino to open the servo for this rack
    await send_arduino_command(f"OPEN:{rack_num}")
    
    if websocket:
        await send_event(websocket, "hardware", f"Rack {rack_num} flap opened")
    
    # Wait 5 seconds
    await asyncio.sleep(5) 
    
    print(f"Closing flap for Rack {rack_num}...")
    # Send command to Arduino to close the servo
    await send_arduino_command(f"CLOSE:{rack_num}")
    
    if websocket:
        await send_event(websocket, "hardware", f"Rack {rack_num} flap closed (auto-lock)")

def setup_callbacks(websocket):
    def create_handler(rack_num):
        return lambda: asyncio.create_task(open_flap(rack_num, websocket))

    buttons['btn_rack_1'].when_pressed = create_handler(1)
    buttons['btn_rack_2'].when_pressed = create_handler(2)
    buttons['btn_rack_3'].when_pressed = create_handler(3)
    buttons['btn_rack_4'].when_pressed = create_handler(4)
    buttons['btn_estop'].when_pressed = lambda: asyncio.create_task(send_event(websocket, "emergency", "Hardware E-Stop activated"))
    buttons['btn_home'].when_pressed = lambda: asyncio.create_task(send_event(websocket, "hardware", "Return to home requested"))
    buttons['btn_refresh'].when_pressed = lambda: asyncio.create_task(send_event(websocket, "hardware", "UI refresh requested"))

async def main():
    print("Initializing Lab Buddy Hardware Service (Arduino Serial Mode)...")
    init_gpio()
    
    while True:
        try:
            print(f"Connecting to backend websocket at {WS_URL}...")
            async with websockets.connect(WS_URL) as websocket:
                print("Connected to backend!")
                setup_callbacks(websocket)
                
                # Mock button press for testing
                if not ON_PI:
                    asyncio.create_task(asyncio.sleep(2)).add_done_callback(lambda _: buttons['btn_rack_2'].press())
                
                # Listen for commands from the backend
                while True:
                    data = await websocket.recv()
                    try:
                        payload = json.loads(data)
                        if payload.get("type") == "command" and payload.get("action") == "unlock_rack":
                            rack_id = payload.get("rack_id")
                            if rack_id:
                                asyncio.create_task(open_flap(rack_id, websocket))
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            print(f"Websocket error: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down Hardware Service...")
        if arduino_serial and arduino_serial.is_open:
            arduino_serial.close()
