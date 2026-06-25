#include <Servo.h>

// Initialize the 4 servos
Servo servo1;
Servo servo2;
Servo servo3;
Servo servo4;

// Configurable angles for your CAD mounts
const int OPEN_ANGLE = 180; // Adjust this value to get exactly 90 degree flap open based on mount
const int CLOSE_ANGLE = 0;  // Adjust this value to close the flap

void setup() {
  // Start serial communication with Raspberry Pi at 9600 baud rate
  Serial.begin(9600);
  
  // Attach servos to PWM enabled pins on Arduino Nano
  servo1.attach(3);
  servo2.attach(5);
  servo3.attach(6);
  servo4.attach(9);
  
  // Initialize all to closed position
  servo1.write(CLOSE_ANGLE);
  servo2.write(CLOSE_ANGLE);
  servo3.write(CLOSE_ANGLE);
  servo4.write(CLOSE_ANGLE);
}

void loop() {
  if (Serial.available() > 0) {
    // Read command until newline character
    String command = Serial.readStringUntil('\n');
    command.trim(); // Remove any whitespace/carriage returns
    
    // Parse commands like "OPEN:1" or "CLOSE:2"
    if (command.startsWith("OPEN:")) {
      int rack = command.substring(5).toInt();
      openRack(rack);
    } else if (command.startsWith("CLOSE:")) {
      int rack = command.substring(6).toInt();
      closeRack(rack);
    }
  }
}

void openRack(int rack) {
  switch(rack) {
    case 1: servo1.write(OPEN_ANGLE); break;
    case 2: servo2.write(OPEN_ANGLE); break;
    case 3: servo3.write(OPEN_ANGLE); break;
    case 4: servo4.write(OPEN_ANGLE); break;
  }
  Serial.print("ACK:OPEN:");
  Serial.println(rack);
}

void closeRack(int rack) {
  switch(rack) {
    case 1: servo1.write(CLOSE_ANGLE); break;
    case 2: servo2.write(CLOSE_ANGLE); break;
    case 3: servo3.write(CLOSE_ANGLE); break;
    case 4: servo4.write(CLOSE_ANGLE); break;
  }
  Serial.print("ACK:CLOSE:");
  Serial.println(rack);
}
