import time
import os
import requests
import json
from datetime import datetime

# Attempt to import gpiozero, fallback to mock if not on Raspberry Pi
try:
    from gpiozero import Button, OutputDevice
    ON_PI = True
except (ImportError, NotImplementedError):
    print("Warning: gpiozero not found or not running on Raspberry Pi. Using mock GPIO.")
    ON_PI = False

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000/api/v1")

# Mock GPIO Classes for development on Windows
class MockButton:
    def __init__(self, pin):
        self.pin = pin
        self.when_pressed = None

    def press(self):
        if self.when_pressed:
            self.when_pressed()

class MockOutput:
    def __init__(self, pin):
        self.pin = pin
        self.is_active = False

    def on(self):
        self.is_active = True
        print(f"Mock Pin {self.pin} ON")

    def off(self):
        self.is_active = False
        print(f"Mock Pin {self.pin} OFF")

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

LOCK_PINS = {
    'lock_1': 6,
    'lock_2': 13,
    'lock_3': 19,
    'lock_4': 26
}

buttons = {}
locks = {}

def init_gpio():
    for name, pin in BUTTON_PINS.items():
        if ON_PI:
            buttons[name] = Button(pin, pull_up=True, bounce_time=0.1)
        else:
            buttons[name] = MockButton(pin)
            
    for name, pin in LOCK_PINS.items():
        if ON_PI:
            locks[name] = OutputDevice(pin, active_high=False, initial_value=False)
        else:
            locks[name] = MockOutput(pin)

def send_event(event_type, description, user_id=None):
    try:
        # In a real scenario, you'd use a dedicated hardware endpoint
        print(f"Hardware Event: {event_type} - {description}")
    except Exception as e:
        print(f"Error sending event: {e}")

def handle_rack_button(rack_num):
    print(f"Button for Rack {rack_num} pressed!")
    # Open the lock
    lock_name = f"lock_{rack_num}"
    if lock_name in locks:
        locks[lock_name].on()
        send_event("hardware", f"Rack {rack_num} unlocked via hardware button")
        # Auto-lock after 5 seconds
        time.sleep(5)
        locks[lock_name].off()
        send_event("hardware", f"Rack {rack_num} auto-locked")

def handle_estop():
    print("EMERGENCY STOP BUTTON PRESSED!")
    send_event("emergency", "Hardware E-Stop activated")

def handle_home():
    print("HOME BUTTON PRESSED!")
    send_event("hardware", "Return to home requested")

def handle_refresh():
    print("REFRESH BUTTON PRESSED!")
    send_event("hardware", "UI refresh requested")

def setup_callbacks():
    buttons['btn_rack_1'].when_pressed = lambda: handle_rack_button(1)
    buttons['btn_rack_2'].when_pressed = lambda: handle_rack_button(2)
    buttons['btn_rack_3'].when_pressed = lambda: handle_rack_button(3)
    buttons['btn_rack_4'].when_pressed = lambda: handle_rack_button(4)
    buttons['btn_estop'].when_pressed = handle_estop
    buttons['btn_home'].when_pressed = handle_home
    buttons['btn_refresh'].when_pressed = handle_refresh

if __name__ == "__main__":
    print("Initializing LabRobot Hardware Service...")
    init_gpio()
    setup_callbacks()
    
    print("Hardware Service Running. Press Ctrl+C to exit.")
    if not ON_PI:
        print("Running in mock mode. Simulating button presses...")
        time.sleep(2)
        buttons['btn_rack_2'].press()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down Hardware Service...")
