// ═══════════════════════════════════════════════════════════════════════════════
//  aura_rover_firmware.ino  —  Arduino Nano Firmware
//  AURA Autonomous Rover | ROS 2 Jazzy
//
//  IMU: MPU-6500  (InvenSense)
//    6-DOF: 3-axis accelerometer + 3-axis gyroscope
//    NO magnetometer (use wheel odometry + gyro for heading)
//    I2C address: 0x68  (AD0 → GND)
//    WHO_AM_I: 0x70
//
//  SERIAL PROTOCOL (115200 baud):
//    IN  ← "CMD <left_pwm> <right_pwm>\n"    Pi → Arduino
//    OUT → "ENC <left_ticks> <right_ticks>\n" Arduino → Pi  (50 Hz)
//    OUT → "IMU ax ay az gx gy gz 0 0 0\n"   Arduino → Pi  (50 Hz)
//           ax/ay/az [m/s²] | gx/gy/gz [rad/s] | mx/my/mz always 0 (no mag)
//
//  MPU-6500 SCALE FACTORS (same as MPU-6050):
//    Accel ±2g  → 16384 LSB/g  → × (9.80665 / 16384) for m/s²
//    Gyro  ±250°/s → 131 LSB/(°/s) → × (π / (180 × 131)) for rad/s
//
//  WIRING:
//    MPU-6500  VCC → 3.3V  GND → GND  SDA → A4  SCL → A5  AD0 → GND
//    Left  BTS7960: RPWM=D5  LPWM=D6  R_EN=D8  L_EN=D9
//    Right BTS7960: RPWM=D10 LPWM=D11 R_EN=D12 L_EN=D13
//    Left  Encoder: A=D2(INT0)  B=D4
//    Right Encoder: A=D3(INT1)  B=D7
// ═══════════════════════════════════════════════════════════════════════════════

#include <Wire.h>

// ── Pin assignments ───────────────────────────────────────────────────────────
#define LEFT_RPWM    5
#define LEFT_LPWM    6
#define LEFT_R_EN    7
#define LEFT_L_EN    8
#define RIGHT_RPWM   9
#define RIGHT_LPWM  10
#define RIGHT_R_EN  11
#define RIGHT_L_EN  12

#define LEFT_ENC_A   2    // INT0
#define LEFT_ENC_B   4
#define RIGHT_ENC_A  3    // INT1
#define RIGHT_ENC_B  A0

// ── MPU-6500 registers ────────────────────────────────────────────────────────
#define MPU_ADDR         0x68
#define MPU_WHO_AM_I     0x75
#define MPU_SMPLRT_DIV   0x19
#define MPU_CONFIG       0x1A
#define MPU_GYRO_CONFIG  0x1B
#define MPU_ACCEL_CONFIG 0x1C
#define MPU_PWR_MGMT_1   0x6B
#define MPU_ACCEL_XOUT_H 0x3B

#define MPU6500_WHO_AM_I_VAL 0x70   // expected WHO_AM_I response

// ── Scale factors ─────────────────────────────────────────────────────────────
#define ACCEL_SCALE  (9.80665f / 16384.0f)   // ±2g,  16384 LSB/g  → m/s²
#define GYRO_SCALE   (3.14159265f / (180.0f * 131.0f))  // ±250°/s → rad/s

// ── Timing ────────────────────────────────────────────────────────────────────
#define ENC_PERIOD_MS   20    // 50 Hz
#define IMU_PERIOD_MS   20    // 50 Hz
#define CMD_TIMEOUT_MS 500    // motor watchdog (ms)

// ── Encoder state (volatile — modified in ISRs) ───────────────────────────────
volatile int32_t leftTicks  = 0;
volatile int32_t rightTicks = 0;
volatile int8_t  lastLeftA  = LOW;
volatile int8_t  lastRightA = LOW;

// ── CMD state ─────────────────────────────────────────────────────────────────
int  leftPWM = 0, rightPWM = 0;
unsigned long lastCmdMs = 0;

// ── Timer state ───────────────────────────────────────────────────────────────
unsigned long lastEncMs = 0, lastImuMs = 0;

// ── Serial input buffer ───────────────────────────────────────────────────────
char    inputBuf[64];
uint8_t inputIdx = 0;


// ═══════════════════════════════════════════════════════════════════════════════
//  ENCODER ISRs  (hardware interrupts: INT0=D2, INT1=D3)
// ═══════════════════════════════════════════════════════════════════════════════
void leftEncoderISR() {
  int8_t a = digitalRead(LEFT_ENC_A);
  int8_t b = digitalRead(LEFT_ENC_B);
  if (a != lastLeftA) { leftTicks  += (a == b) ? -1 : 1; lastLeftA  = a; }
}

void rightEncoderISR() {
  int8_t a = digitalRead(RIGHT_ENC_A);
  int8_t b = digitalRead(RIGHT_ENC_B);
  if (a != lastRightA) { rightTicks += (a == b) ? -1 : 1; lastRightA = a; }
}


// ═══════════════════════════════════════════════════════════════════════════════
//  I2C HELPERS
// ═══════════════════════════════════════════════════════════════════════════════
void i2cWriteReg(uint8_t dev, uint8_t reg, uint8_t val) {
  Wire.beginTransmission(dev);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission(true);
}

uint8_t i2cReadReg(uint8_t dev, uint8_t reg) {
  Wire.beginTransmission(dev);
  Wire.write(reg);
  Wire.endTransmission(false);
  Wire.requestFrom(dev, (uint8_t)1, (uint8_t)true);
  return Wire.available() ? Wire.read() : 0xFF;
}


// ═══════════════════════════════════════════════════════════════════════════════
//  MPU-6500 INIT
// ═══════════════════════════════════════════════════════════════════════════════
void mpuInit() {
  Wire.begin();
  delay(200);

  // Wake up MPU-6500 (clear sleep bit, use internal 8 MHz clock)
  i2cWriteReg(MPU_ADDR, MPU_PWR_MGMT_1, 0x00);
  delay(100);

  // Verify WHO_AM_I
  uint8_t whoAmI = i2cReadReg(MPU_ADDR, MPU_WHO_AM_I);
  if (whoAmI == MPU6500_WHO_AM_I_VAL) {
    Serial.println("LOG MPU-6500 detected OK (WHO_AM_I=0x70)");
  } else {
    Serial.print("LOG WHO_AM_I=0x");
    Serial.print(whoAmI, HEX);
    Serial.println(" (expected 0x70 for MPU-6500)");
  }

  // Sample rate divider: SMPLRT_DIV=4 → output rate = 1 kHz / (1+4) = 200 Hz
  i2cWriteReg(MPU_ADDR, MPU_SMPLRT_DIV,   0x04);

  // DLPF bandwidth = 41 Hz  (CONFIG register bits[2:0] = 011)
  // Good balance: cuts high-frequency vibration noise, keeps good dynamic response
  i2cWriteReg(MPU_ADDR, MPU_CONFIG,        0x03);

  // Gyro  full-scale: ±250 °/s  (GYRO_CONFIG bits[4:3] = 00)
  i2cWriteReg(MPU_ADDR, MPU_GYRO_CONFIG,   0x00);

  // Accel full-scale: ±2 g      (ACCEL_CONFIG bits[4:3] = 00)
  i2cWriteReg(MPU_ADDR, MPU_ACCEL_CONFIG,  0x00);

  Serial.println("LOG MPU-6500 configured: ±2g accel, ±250°/s gyro, DLPF 41Hz");
}


// ═══════════════════════════════════════════════════════════════════════════════
//  READ MPU-6500 ACCEL + GYRO
//  Reads 14 bytes starting at ACCEL_XOUT_H:
//  AX_H AX_L  AY_H AY_L  AZ_H AZ_L  TEMP_H TEMP_L  GX_H GX_L  GY_H GY_L  GZ_H GZ_L
// ═══════════════════════════════════════════════════════════════════════════════
void readMPU6500(float &ax, float &ay, float &az,
                 float &gx, float &gy, float &gz) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(MPU_ACCEL_XOUT_H);
  Wire.endTransmission(false);
  Wire.requestFrom(MPU_ADDR, (uint8_t)14, (uint8_t)true);

  int16_t rawAx = ((int16_t)Wire.read() << 8) | Wire.read();
  int16_t rawAy = ((int16_t)Wire.read() << 8) | Wire.read();
  int16_t rawAz = ((int16_t)Wire.read() << 8) | Wire.read();
  Wire.read(); Wire.read();  // temperature — discard
  int16_t rawGx = ((int16_t)Wire.read() << 8) | Wire.read();
  int16_t rawGy = ((int16_t)Wire.read() << 8) | Wire.read();
  int16_t rawGz = ((int16_t)Wire.read() << 8) | Wire.read();

  ax = rawAx * ACCEL_SCALE;
  ay = rawAy * ACCEL_SCALE;
  az = rawAz * ACCEL_SCALE;
  gx = rawGx * GYRO_SCALE;
  gy = rawGy * GYRO_SCALE;
  gz = rawGz * GYRO_SCALE;
}


// ═══════════════════════════════════════════════════════════════════════════════
//  MOTOR CONTROL  (BTS7960)
// ═══════════════════════════════════════════════════════════════════════════════
void setMotors(int l, int r) {
  l = constrain(l, -255, 255);
  r = constrain(r, -255, 255);
  analogWrite(LEFT_RPWM,  l >= 0 ?  l : 0);
  analogWrite(LEFT_LPWM,  l <  0 ? -l : 0);
  analogWrite(RIGHT_RPWM, r >= 0 ?  r : 0);
  analogWrite(RIGHT_LPWM, r <  0 ? -r : 0);
}

void stopMotors() {
  analogWrite(LEFT_RPWM, 0); analogWrite(LEFT_LPWM, 0);
  analogWrite(RIGHT_RPWM, 0); analogWrite(RIGHT_LPWM, 0);
}


// ═══════════════════════════════════════════════════════════════════════════════
//  SERIAL CMD PARSER  →  "CMD left_pwm right_pwm\n"
// ═══════════════════════════════════════════════════════════════════════════════
void processCommand(const char *buf) {
  if (strncmp(buf, "CMD ", 4) == 0) {
    int l = 0, r = 0;
    if (sscanf(buf + 4, "%d %d", &l, &r) == 2) {
      leftPWM  = constrain(l, -255, 255);
      rightPWM = constrain(r, -255, 255);
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

  // Motor enable + PWM pins
  uint8_t enPins[]  = {LEFT_R_EN, LEFT_L_EN, RIGHT_R_EN, RIGHT_L_EN};
  uint8_t pwmPins[] = {LEFT_RPWM, LEFT_LPWM, RIGHT_RPWM, RIGHT_LPWM};
  for (uint8_t p : enPins)  { pinMode(p, OUTPUT); digitalWrite(p, HIGH); }
  for (uint8_t p : pwmPins)   pinMode(p, OUTPUT);
  stopMotors();

  // Encoder pins + hardware interrupts
  pinMode(LEFT_ENC_A,  INPUT_PULLUP);
  pinMode(LEFT_ENC_B,  INPUT_PULLUP);
  pinMode(RIGHT_ENC_A, INPUT_PULLUP);
  pinMode(RIGHT_ENC_B, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(LEFT_ENC_A),  leftEncoderISR,  CHANGE);
  attachInterrupt(digitalPinToInterrupt(RIGHT_ENC_A), rightEncoderISR, CHANGE);

  // MPU-6500 (accel + gyro only — no magnetometer)
  mpuInit();

  Serial.println("LOG AURA Rover MPU-6500 firmware ready");
}


// ═══════════════════════════════════════════════════════════════════════════════
//  MAIN LOOP
// ═══════════════════════════════════════════════════════════════════════════════
void loop() {
  unsigned long now = millis();

  // ── 1. Parse serial input (non-blocking) ─────────────────────────────────
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

  // ── 2. Motor watchdog — stop if no CMD in 500 ms ─────────────────────────
  if ((now - lastCmdMs) > CMD_TIMEOUT_MS) {
    stopMotors();
    leftPWM = rightPWM = 0;
  }

  // ── 3. Publish encoder ticks @ 50 Hz ─────────────────────────────────────
  if ((now - lastEncMs) >= ENC_PERIOD_MS) {
    lastEncMs = now;
    noInterrupts();
    int32_t l = leftTicks, r = rightTicks;
    interrupts();
    Serial.print("ENC "); Serial.print(l); Serial.print(' '); Serial.println(r);
  }

  // ── 4. Publish IMU data @ 50 Hz ───────────────────────────────────────────
  //  MPU-6500 has NO magnetometer → mx = my = mz = 0.0
  //  The ROS imu_filter_madgwick runs in 6-DOF mode (use_mag=false),
  //  estimating orientation from accel + gyro only.
  //  Yaw will drift over time without a compass reference.
  //  The EKF fuses only gyro angular rate (vyaw), not absolute yaw orientation.
  if ((now - lastImuMs) >= IMU_PERIOD_MS) {
    lastImuMs = now;
    float ax, ay, az, gx, gy, gz;
    readMPU6500(ax, ay, az, gx, gy, gz);

    Serial.print("IMU ");
    Serial.print(ax, 4); Serial.print(' ');
    Serial.print(ay, 4); Serial.print(' ');
    Serial.print(az, 4); Serial.print(' ');
    Serial.print(gx, 5); Serial.print(' ');
    Serial.print(gy, 5); Serial.print(' ');
    Serial.print(gz, 5); Serial.print(' ');
    Serial.print("0.00 0.00 0.00");  // no magnetometer
    Serial.println();
  }
}
