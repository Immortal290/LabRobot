// ═══════════════════════════════════════════════════════════════════════════
//  AURA Mobile Robot — Arduino/ESP32 Firmware
//  Hardware: Arduino Nano (or ESP32) + MPU9250 (I2C) + 2× Quadrature Encoders
//
//  Serial Protocol (115200 baud):
//    OUT → "ENC left_ticks right_ticks\n"
//    OUT → "IMU ax ay az gx gy gz mx my mz\n"  (ax/ay/az m/s², gx/gy/gz rad/s, mx/my/mz µT)
//    IN  ← "CMD left_pwm right_pwm\n"           (-255..255)
//
//  Wiring (Arduino Nano):
//    LEFT  Encoder A → D2  (INT0)
//    LEFT  Encoder B → D4
//    RIGHT Encoder A → D3  (INT1)
//    RIGHT Encoder B → D5
//    MPU9250 SDA     → A4
//    MPU9250 SCL     → A5
//    Left  Motor PWM → D6  (ENA)
//    Left  Motor DIR1→ D7
//    Left  Motor DIR2→ D8
//    Right Motor PWM → D9  (ENB)
//    Right Motor DIR1→ D10
//    Right Motor DIR2→ D11
// ═══════════════════════════════════════════════════════════════════════════

#include <Wire.h>

// ── ESP32 vs Arduino pin definitions ────────────────────────────────────────
#if defined(ESP32)
  #define ENC_LEFT_A   34   // Input-only GPIOs on ESP32 (interrupt capable)
  #define ENC_LEFT_B   35
  #define ENC_RIGHT_A  32
  #define ENC_RIGHT_B  33
  #define MOTOR_L_PWM  25
  #define MOTOR_L_DIR1 26
  #define MOTOR_L_DIR2 27
  #define MOTOR_R_PWM  14
  #define MOTOR_R_DIR1 12
  #define MOTOR_R_DIR2 13
#else
  // Arduino Nano / Uno
  #define ENC_LEFT_A    2   // INT0 — MUST be interrupt pin
  #define ENC_LEFT_B    4
  #define ENC_RIGHT_A   3   // INT1 — MUST be interrupt pin
  #define ENC_RIGHT_B   5
  #define MOTOR_L_PWM   6
  #define MOTOR_L_DIR1  7
  #define MOTOR_L_DIR2  8
  #define MOTOR_R_PWM   9
  #define MOTOR_R_DIR1 10
  #define MOTOR_R_DIR2 11
#endif

// ── MPU9250 I2C addresses ────────────────────────────────────────────────────
#define MPU9250_ADDR   0x68
#define AK8963_ADDR    0x0C   // Magnetometer (bypass mode)

// ── MPU9250 register map ─────────────────────────────────────────────────────
#define MPU_PWR_MGMT_1   0x6B
#define MPU_USER_CTRL    0x6A
#define MPU_INT_PIN_CFG  0x37
#define MPU_ACCEL_XOUT_H 0x3B
#define MPU_GYRO_XOUT_H  0x43
#define AK_CNTL1         0x0A
#define AK_XOUT_L        0x03

// ── Scaling constants ────────────────────────────────────────────────────────
// Accelerometer: ±2 g  → 16384 LSB/g   → convert to m/s²
static const float ACCEL_SCALE = 9.80665f / 16384.0f;
// Gyroscope: ±250 °/s  → 131 LSB/°/s  → convert to rad/s
static const float GYRO_SCALE  = (1.0f / 131.0f) * (3.14159265f / 180.0f);
// Magnetometer: AK8963 16-bit → 0.15 µT/LSB
static const float MAG_SCALE   = 0.15f;

// ── Timing ───────────────────────────────────────────────────────────────────
static const unsigned long ENC_INTERVAL_MS = 50;   // 20 Hz encoder publish
static const unsigned long IMU_INTERVAL_MS = 20;   // 50 Hz IMU publish

// ── Encoder state (volatile — modified in ISR) ───────────────────────────────
volatile long leftTicks  = 0;
volatile long rightTicks = 0;

// ── Command state ─────────────────────────────────────────────────────────────
int cmdLeftPWM  = 0;
int cmdRightPWM = 0;

// ── Serial command buffer ─────────────────────────────────────────────────────
char cmdBuf[64];
uint8_t cmdIdx = 0;

// ════════════════════════════════════════════════════════════════════════════
//  ENCODER ISRs
// ════════════════════════════════════════════════════════════════════════════
void IRAM_ATTR leftEncoderISR() {
  int a = digitalRead(ENC_LEFT_A);
  int b = digitalRead(ENC_LEFT_B);
  leftTicks += (a == b) ? 1 : -1;
}

void IRAM_ATTR rightEncoderISR() {
  int a = digitalRead(ENC_RIGHT_A);
  int b = digitalRead(ENC_RIGHT_B);
  rightTicks += (a == b) ? -1 : 1;  // invert if motor spins opposite
}

// ════════════════════════════════════════════════════════════════════════════
//  MPU9250 HELPERS
// ════════════════════════════════════════════════════════════════════════════
static void mpuWriteByte(uint8_t addr, uint8_t reg, uint8_t data) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  Wire.write(data);
  Wire.endTransmission();
}

static int16_t mpuRead16(uint8_t addr, uint8_t reg) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  Wire.endTransmission(false);
  Wire.requestFrom(addr, (uint8_t)2);
  int16_t val = ((int16_t)Wire.read() << 8) | Wire.read();
  return val;
}

static void mpuReadBurst(uint8_t addr, uint8_t startReg, uint8_t count, uint8_t* buf) {
  Wire.beginTransmission(addr);
  Wire.write(startReg);
  Wire.endTransmission(false);
  Wire.requestFrom(addr, count);
  for (uint8_t i = 0; i < count; i++) buf[i] = Wire.read();
}

static void mpuInit() {
  // Wake MPU9250, use best clock source
  mpuWriteByte(MPU9250_ADDR, MPU_PWR_MGMT_1, 0x01);
  delay(100);

  // DLPF ~92 Hz bandwidth (register 0x1A, DLPF_CFG=2)
  mpuWriteByte(MPU9250_ADDR, 0x1A, 0x02);
  // Gyro ±250°/s
  mpuWriteByte(MPU9250_ADDR, 0x1B, 0x00);
  // Accel ±2g
  mpuWriteByte(MPU9250_ADDR, 0x1C, 0x00);
  // Sample rate divider → 1kHz / (1+9) = 100 Hz
  mpuWriteByte(MPU9250_ADDR, 0x19, 0x09);

  // Disable I2C master interface on MPU9250 to allow I2C bypass
  mpuWriteByte(MPU9250_ADDR, MPU_USER_CTRL, 0x00);
  delay(10);

  // Enable I2C bypass so master can talk to AK8963
  mpuWriteByte(MPU9250_ADDR, MPU_INT_PIN_CFG, 0x02);
  delay(10);

  // Init AK8963 magnetometer — continuous mode 2 (100 Hz), 16-bit
  mpuWriteByte(AK8963_ADDR, AK_CNTL1, 0x16);
  delay(20);
}

// ════════════════════════════════════════════════════════════════════════════
//  MOTOR DRIVER
// ════════════════════════════════════════════════════════════════════════════
static void setMotor(int pwmPin, int dir1, int dir2, int speed) {
  if (speed > 0) {
    digitalWrite(dir1, HIGH);
    digitalWrite(dir2, LOW);
    analogWrite(pwmPin, constrain(speed, 0, 255));
  } else if (speed < 0) {
    digitalWrite(dir1, LOW);
    digitalWrite(dir2, HIGH);
    analogWrite(pwmPin, constrain(-speed, 0, 255));
  } else {
    digitalWrite(dir1, LOW);
    digitalWrite(dir2, LOW);
    analogWrite(pwmPin, 0);
  }
}

// ════════════════════════════════════════════════════════════════════════════
//  SERIAL COMMAND PARSER
// ════════════════════════════════════════════════════════════════════════════
static void parseSerial() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (cmdIdx > 0) {
        cmdBuf[cmdIdx] = '\0';
        // Parse "CMD left_pwm right_pwm"
        if (strncmp(cmdBuf, "CMD ", 4) == 0) {
          int l = 0, r = 0;
          sscanf(cmdBuf + 4, "%d %d", &l, &r);
          cmdLeftPWM  = constrain(l, -255, 255);
          cmdRightPWM = constrain(r, -255, 255);
        }
        cmdIdx = 0;
      }
    } else if (cmdIdx < sizeof(cmdBuf) - 1) {
      cmdBuf[cmdIdx++] = c;
    }
  }
}

// ════════════════════════════════════════════════════════════════════════════
//  SETUP
// ════════════════════════════════════════════════════════════════════════════
void setup() {
  Serial.begin(115200);
  Wire.begin();
  Wire.setClock(400000);  // 400 kHz fast-mode

  // Encoder pins
  pinMode(ENC_LEFT_A,  INPUT_PULLUP);
  pinMode(ENC_LEFT_B,  INPUT_PULLUP);
  pinMode(ENC_RIGHT_A, INPUT_PULLUP);
  pinMode(ENC_RIGHT_B, INPUT_PULLUP);

  attachInterrupt(digitalPinToInterrupt(ENC_LEFT_A),  leftEncoderISR,  CHANGE);
  attachInterrupt(digitalPinToInterrupt(ENC_RIGHT_A), rightEncoderISR, CHANGE);

  // Motor pins
  pinMode(MOTOR_L_PWM,  OUTPUT);
  pinMode(MOTOR_L_DIR1, OUTPUT);
  pinMode(MOTOR_L_DIR2, OUTPUT);
  pinMode(MOTOR_R_PWM,  OUTPUT);
  pinMode(MOTOR_R_DIR1, OUTPUT);
  pinMode(MOTOR_R_DIR2, OUTPUT);

  mpuInit();

  Serial.println("# AURA firmware ready");
}

// ════════════════════════════════════════════════════════════════════════════
//  LOOP
// ════════════════════════════════════════════════════════════════════════════
void loop() {
  static unsigned long lastEnc = 0;
  static unsigned long lastImu = 0;
  unsigned long now = millis();

  parseSerial();

  // ── Apply motor commands ──────────────────────────────────────────────────
  setMotor(MOTOR_L_PWM, MOTOR_L_DIR1, MOTOR_L_DIR2, cmdLeftPWM);
  setMotor(MOTOR_R_PWM, MOTOR_R_DIR1, MOTOR_R_DIR2, cmdRightPWM);

  // ── Publish encoder ticks ─────────────────────────────────────────────────
  if (now - lastEnc >= ENC_INTERVAL_MS) {
    lastEnc = now;
    noInterrupts();
    long l = leftTicks;
    long r = rightTicks;
    interrupts();
    Serial.print("ENC ");
    Serial.print(l);
    Serial.print(" ");
    Serial.println(r);
  }

  // ── Publish IMU data ──────────────────────────────────────────────────────
  if (now - lastImu >= IMU_INTERVAL_MS) {
    lastImu = now;

    // Read accel (6 bytes starting at 0x3B)
    uint8_t rawBuf[14];
    mpuReadBurst(MPU9250_ADDR, MPU_ACCEL_XOUT_H, 14, rawBuf);

    int16_t rawAx = ((int16_t)rawBuf[0]  << 8) | rawBuf[1];
    int16_t rawAy = ((int16_t)rawBuf[2]  << 8) | rawBuf[3];
    int16_t rawAz = ((int16_t)rawBuf[4]  << 8) | rawBuf[5];
    // bytes 6-7 = temperature (skip)
    int16_t rawGx = ((int16_t)rawBuf[8]  << 8) | rawBuf[9];
    int16_t rawGy = ((int16_t)rawBuf[10] << 8) | rawBuf[11];
    int16_t rawGz = ((int16_t)rawBuf[12] << 8) | rawBuf[13];

    float ax = rawAx * ACCEL_SCALE;
    float ay = rawAy * ACCEL_SCALE;
    float az = rawAz * ACCEL_SCALE;
    float gx = rawGx * GYRO_SCALE;
    float gy = rawGy * GYRO_SCALE;
    float gz = rawGz * GYRO_SCALE;

    // Read magnetometer (AK8963)
    uint8_t magBuf[7];
    mpuReadBurst(AK8963_ADDR, AK_XOUT_L, 7, magBuf);

    // AK8963 little-endian
    int16_t rawMx = ((int16_t)magBuf[1] << 8) | magBuf[0];
    int16_t rawMy = ((int16_t)magBuf[3] << 8) | magBuf[2];
    int16_t rawMz = ((int16_t)magBuf[5] << 8) | magBuf[4];

    float mx = rawMx * MAG_SCALE;
    float my = rawMy * MAG_SCALE;
    float mz = rawMz * MAG_SCALE;

    // Print with 4 decimal places
    Serial.print("IMU ");
    Serial.print(ax, 4); Serial.print(" ");
    Serial.print(ay, 4); Serial.print(" ");
    Serial.print(az, 4); Serial.print(" ");
    Serial.print(gx, 4); Serial.print(" ");
    Serial.print(gy, 4); Serial.print(" ");
    Serial.print(gz, 4); Serial.print(" ");
    Serial.print(mx, 2); Serial.print(" ");
    Serial.print(my, 2); Serial.print(" ");
    Serial.println(mz, 2);
  }
}
