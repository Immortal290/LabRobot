// ═══════════════════════════════════════════════════════════════════════════════
//  bts7960_encoder_only.ino  —  AURA Rover | Arduino Nano
//  BTS7960 Motor Driver + Quadrature Encoders
//  NO IMU — flash this until MPU wiring is ready
//
//  SERIAL PROTOCOL (115200 baud):
//    OUT → "ENC <left_ticks> <right_ticks>\n"   (20 Hz)
//    IN  ← "CMD <left_pwm> <right_pwm>\n"       (-255 to 255)
//    OUT → "ROVER_READY\n"                       (once on boot)
//
//  PIN LAYOUT — BTS7960 Dual H-Bridge:
//    Left  BTS7960 : RPWM=D5  LPWM=D6  R_EN=D8  L_EN=D9
//    Right BTS7960 : RPWM=D10 LPWM=D11 R_EN=D12 L_EN=D13
//
//  ENCODER PINS (quadrature, hardware interrupts):
//    Left  Encoder : A=D2 (INT0)  B=D4
//    Right Encoder : A=D3 (INT1)  B=D7
//
//  MOTOR WATCHDOG:
//    If no CMD received within 500 ms → motors stop automatically
// ═══════════════════════════════════════════════════════════════════════════════

// ── BTS7960 pin assignments ───────────────────────────────────────────────────
#define LEFT_RPWM    5    // Forward PWM  — left side
#define LEFT_LPWM    6    // Reverse PWM  — left side
#define LEFT_R_EN    7    // Right-side enable (set HIGH)
#define LEFT_L_EN    8    // Left-side  enable (set HIGH)

#define RIGHT_RPWM   9    // Forward PWM  — right side
#define RIGHT_LPWM  10    // Reverse PWM  — right side
#define RIGHT_R_EN  11    // Right-side enable (set HIGH)
#define RIGHT_L_EN  12    // Left-side  enable (set HIGH)

// ── Encoder pins ─────────────────────────────────────────────────────────────
#define LEFT_ENC_A   2    // INT0 — must be hardware interrupt pin
#define LEFT_ENC_B   4
#define RIGHT_ENC_A  3    // INT1 — must be hardware interrupt pin
#define RIGHT_ENC_B  A0

// ── Timing ────────────────────────────────────────────────────────────────────
#define ENC_PERIOD_MS   50    // 20 Hz encoder publish
#define CMD_TIMEOUT_MS 500    // motor watchdog — stop if no CMD for 500 ms

// ── Encoder state (volatile — modified in ISRs) ───────────────────────────────
volatile int32_t leftTicks  = 0;
volatile int32_t rightTicks = 0;
volatile int8_t  lastLeftA  = LOW;
volatile int8_t  lastRightA = LOW;

// ── CMD state ─────────────────────────────────────────────────────────────────
int  leftPWM  = 0;
int  rightPWM = 0;
unsigned long lastCmdMs = 0;

// ── Serial buffer ─────────────────────────────────────────────────────────────
char    inputBuf[64];
uint8_t inputIdx = 0;

// ── Timer ────────────────────────────────────────────────────────────────────
unsigned long lastEncMs = 0;


// ═══════════════════════════════════════════════════════════════════════════════
//  ENCODER ISRs
// ═══════════════════════════════════════════════════════════════════════════════
void leftEncoderISR() {
  int8_t a = digitalRead(LEFT_ENC_A);
  int8_t b = digitalRead(LEFT_ENC_B);
  if (a != lastLeftA) {
    leftTicks += (a == b) ? -1 : 1;
    lastLeftA = a;
  }
}

void rightEncoderISR() {
  int8_t a = digitalRead(RIGHT_ENC_A);
  int8_t b = digitalRead(RIGHT_ENC_B);
  if (a != lastRightA) {
    rightTicks += (a == b) ? 1 : -1;
    lastRightA = a;
  }
}


// ═══════════════════════════════════════════════════════════════════════════════
//  MOTOR CONTROL — BTS7960
//  Positive PWM = forward, Negative PWM = reverse
// ═══════════════════════════════════════════════════════════════════════════════
void setMotors(int l, int r) {
  l = constrain(l, -255, 255);
  r = constrain(r, -255, 255);

  // Left side
  analogWrite(LEFT_RPWM,  l >= 0 ?  l : 0);
  analogWrite(LEFT_LPWM,  l <  0 ? -l : 0);

  // Right side
  analogWrite(RIGHT_RPWM, r >= 0 ?  r : 0);
  analogWrite(RIGHT_LPWM, r <  0 ? -r : 0);
}

void stopMotors() {
  analogWrite(LEFT_RPWM,  0); analogWrite(LEFT_LPWM,  0);
  analogWrite(RIGHT_RPWM, 0); analogWrite(RIGHT_LPWM, 0);
}


// ═══════════════════════════════════════════════════════════════════════════════
//  SERIAL CMD PARSER  →  "CMD left_pwm right_pwm\n"
// ═══════════════════════════════════════════════════════════════════════════════
void processCommand(const char *buf) {
  if (strncmp(buf, "CMD ", 4) == 0) {
    int l = 0, r = 0;
    if (sscanf(buf + 4, "%d %d", &l, &r) == 2) {
      leftPWM   = constrain(l, -255, 255);
      rightPWM  = constrain(r, -255, 255);
      lastCmdMs = millis();
      setMotors(leftPWM, rightPWM);
    }
  }
}


// ═══════════════════════════════════════════════════════════════════════════════
//  SETUP
// ═══════════════════════════════════════════════════════════════════════════════
void setup() {
  Serial.begin(115200);

  // ── BTS7960 enable pins (must be HIGH to allow PWM to drive motor) ──────────
  uint8_t enPins[] = { LEFT_R_EN, LEFT_L_EN, RIGHT_R_EN, RIGHT_L_EN };
  for (uint8_t p : enPins) {
    pinMode(p, OUTPUT);
    digitalWrite(p, HIGH);   // enable both sides of each H-bridge
  }

  // ── PWM output pins ──────────────────────────────────────────────────────────
  uint8_t pwmPins[] = { LEFT_RPWM, LEFT_LPWM, RIGHT_RPWM, RIGHT_LPWM };
  for (uint8_t p : pwmPins) pinMode(p, OUTPUT);
  stopMotors();

  // ── Encoder input pins + hardware interrupts ─────────────────────────────────
  pinMode(LEFT_ENC_A,  INPUT_PULLUP);
  pinMode(LEFT_ENC_B,  INPUT_PULLUP);
  pinMode(RIGHT_ENC_A, INPUT_PULLUP);
  pinMode(RIGHT_ENC_B, INPUT_PULLUP);

  attachInterrupt(digitalPinToInterrupt(LEFT_ENC_A),  leftEncoderISR,  CHANGE);
  attachInterrupt(digitalPinToInterrupt(RIGHT_ENC_A), rightEncoderISR, CHANGE);

  lastCmdMs = millis();
  Serial.println("ROVER_READY");
}


// ═══════════════════════════════════════════════════════════════════════════════
//  MAIN LOOP
// ═══════════════════════════════════════════════════════════════════════════════
void loop() {
  unsigned long now = millis();

  // ── 1. Parse incoming serial commands ────────────────────────────────────────
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (inputIdx > 0) {
        inputBuf[inputIdx] = '\0';
        processCommand(inputBuf);
        inputIdx = 0;
      }
    } else if (inputIdx < 63) {
      inputBuf[inputIdx++] = c;
    }
  }

  // ── 2. Motor watchdog — stop if no CMD for 500 ms ────────────────────────────
  if ((now - lastCmdMs) > CMD_TIMEOUT_MS) {
    stopMotors();
    leftPWM = rightPWM = 0;
  }

  // ── 3. Publish encoder ticks at 20 Hz ────────────────────────────────────────
  if ((now - lastEncMs) >= ENC_PERIOD_MS) {
    lastEncMs = now;

    noInterrupts();
    int32_t l = leftTicks;
    int32_t r = rightTicks;
    interrupts();

    // Format: "ENC <left> <right>"  — space-separated, matches encoder_serial_node.py
    Serial.print("ENC ");
    Serial.print(l);
    Serial.print(' ');
    Serial.println(r);
  }
}
