#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
#  encoder_serial_node.py  —  ROS 2 Jazzy | AURA Rover
#
#  PURPOSE:
#    Bi-directional serial bridge between the Raspberry Pi and the Arduino Nano.
#    Implements standard differential drive kinematics and a unified hardware
#    configuration block to correct any physical wiring inversions/swaps.
#
#  SERIAL PROTOCOL (Arduino side):
#    IN  (Arduino → Pi):  "ENC <left_ticks> <right_ticks>\n"
#    OUT (Pi → Arduino):  "CMD <left_pwm> <right_pwm>\n"
#
#  ROS INTERFACE:
#    Publishes:   /wheel_ticks   [std_msgs/String]  "left_ticks right_ticks"
#    Subscribes:  /cmd_vel       [geometry_msgs/Twist]
# ═══════════════════════════════════════════════════════════════════════════════

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

import serial

from std_msgs.msg import String
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Imu, MagneticField

# ── IMU Covariance matrices ───────────────────────────────────────────────────
ORIENTATION_COV = [
    -1.0, 0.0, 0.0,
     0.0, 0.0, 0.0,
     0.0, 0.0, 0.0,
]
ANGULAR_VEL_COV = [
    2.89e-6, 0.0,     0.0,
    0.0,     2.89e-6, 0.0,
    0.0,     0.0,     2.89e-6,
]
LINEAR_ACCEL_COV = [
    9.0e-6, 0.0,    0.0,
    0.0,    9.0e-6, 0.0,
    0.0,    0.0,    9.0e-6,
]
MAG_COV = [
    9.9e9, 0.0,   0.0,
    0.0,   9.9e9, 0.0,
    0.0,   0.0,   9.9e9,
]


class EncoderSerialNode(Node):
    """
    Serial bridge node for AURA rover Arduino Nano.
    """

    def __init__(self):
        super().__init__('encoder_serial_node')

        # ── Declare parameters ────────────────────────────────────────────────
        self.declare_parameter('serial_port',    '/dev/ttyUSB0')
        self.declare_parameter('serial_baud',    115200)
        self.declare_parameter('wheel_base',     0.660)   # metres
        self.declare_parameter('max_linear_vel', 0.5)     # m/s → MAX_PWM
        self.declare_parameter('max_pwm',        200)     # PWM ceiling
        self.declare_parameter('min_pwm',        60)      # PWM deadband for heavy wheels

        port                = self.get_parameter('serial_port').value
        baud                = self.get_parameter('serial_baud').value
        self.wheel_base     = self.get_parameter('wheel_base').value
        self.max_linear_vel = self.get_parameter('max_linear_vel').value
        self.max_pwm        = self.get_parameter('max_pwm').value
        self.min_pwm        = self.get_parameter('min_pwm').value

        # Whether to publish IMU data (set False if imu_filter_madgwick is not running)
        self.declare_parameter('use_imu', False)
        self.use_imu = self.get_parameter('use_imu').value

        # =====================================================================
        # HARDWARE CONFIGURATION BLOCK
        # Based on observed behavior, BOTH motors are physically wired with
        # reverse polarity. The encoders, however, are wired correctly.
        # =====================================================================
        # Motor configurations (affects outgoing CMD)
        self.invert_left_motor  = True
        self.invert_right_motor = True
        self.swap_left_right_motors = False

        # Encoder configurations (affects incoming ENC)
        self.invert_left_encoder  = True
        self.invert_right_encoder = True
        self.swap_left_right_encoders = False
        # =====================================================================

        # ── QoS for sensor data ───────────────────────────────────────────────
        sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )

        # ── Publishers and Subscribers ────────────────────────────────────────
        self.tick_pub = self.create_publisher(String, '/wheel_ticks', sensor_qos)
        self.cmd_sub = self.create_subscription(
            Twist, '/cmd_vel', self._cmd_vel_callback, 10
        )

        self.imu_pub = self.create_publisher(Imu, '/imu/data_raw', sensor_qos)
        self.mag_pub = self.create_publisher(MagneticField, '/imu/mag', sensor_qos)
        self.imu_frame_id = 'imu_link'

        # ── Open serial port ──────────────────────────────────────────────────
        try:
            self.ser = serial.Serial(port, baud, timeout=0.1)
            self.get_logger().info(
                f'[encoder_serial_node] Serial port {port} @ {baud} baud opened'
            )
        except serial.SerialException as exc:
            self.get_logger().fatal(
                f'[encoder_serial_node] Cannot open {port}: {exc}'
            )
            raise SystemExit(1)

        # ── Serial read timer (20 ms polling — matches Arduino 20ms ENC period) ──
        self.create_timer(0.02, self._read_serial)

        # ── Watchdog timer for auto-stop (hold-to-move) ───────────────────────
        self.cmd_timeout = 0.4  # 400ms timeout
        self.last_cmd_time = self.get_clock().now()
        self.create_timer(0.1, self._check_watchdog)

        self.get_logger().info(
            f'[encoder_serial_node] Ready | wheel_base={self.wheel_base} m | max_pwm={self.max_pwm}'
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Serial reader
    # ─────────────────────────────────────────────────────────────────────────
    def _read_serial(self):
        """Read all available lines from serial and dispatch to handlers."""
        while True:
            try:
                if self.ser.in_waiting == 0:
                    break
                raw = self.ser.readline()
            except serial.SerialException as exc:
                self.get_logger().warning(f'Serial read error: {exc}')
                break

            try:
                line = raw.decode('ascii', errors='ignore').strip()
            except Exception:
                continue

            if line.startswith('ENC'):
                self._handle_enc(line)
            elif line.startswith('IMU ') and self.use_imu:
                self._handle_imu(line)
            elif line.startswith('IMU '):
                pass  # discard IMU data when use_imu=False to avoid buffer flood
            elif line.startswith('ROVER_READY') or line.startswith('DBG ') or line.startswith('LOG '):
                self.get_logger().info(f'[Arduino] {line}')

    def _handle_enc(self, line: str):
        """
        Parse encoder packet and publish to /wheel_ticks.
        Applies unified hardware inversions/swaps to the incoming ticks.
        """
        normalised = line.replace(',', ' ')
        parts = normalised.split()
        if len(parts) != 3:
            return

        try:
            left_raw  = int(parts[1])
            right_raw = int(parts[2])
        except ValueError:
            return

        # Apply unified hardware config to encoders
        if self.invert_left_encoder:
            left_raw = -left_raw
        if self.invert_right_encoder:
            right_raw = -right_raw
        
        if self.swap_left_right_encoders:
            left_raw, right_raw = right_raw, left_raw

        msg = String()
        msg.data = f'{left_raw} {right_raw}'
        self.tick_pub.publish(msg)

    # ─────────────────────────────────────────────────────────────────────────
    def _handle_imu(self, line: str):
        """Parse and publish IMU packet."""
        parts = line.split()
        
        if len(parts) == 10:
            try:
                ax = float(parts[1]); ay = float(parts[2]); az = float(parts[3])
                gx = float(parts[4]); gy = float(parts[5]); gz = float(parts[6])
                mx = float(parts[7]); my = float(parts[8]); mz = float(parts[9])
            except ValueError as e:
                self.get_logger().warning(f'IMU float parse error: {e} | line: {repr(line)}')
                return
        elif len(parts) == 7:
            try:
                ax = float(parts[1]); ay = float(parts[2]); az = float(parts[3])
                gx = float(parts[4]); gy = float(parts[5]); gz = float(parts[6])
                mx = 0.0; my = 0.0; mz = 0.0
            except ValueError as e:
                self.get_logger().warning(f'IMU float parse error: {e} | line: {repr(line)}')
                return
        else:
            self.get_logger().warning(f'IMU parse error (len={len(parts)}): {repr(line)}')
            return

        stamp = self.get_clock().now().to_msg()
        imu_msg = Imu()
        imu_msg.header.stamp    = stamp
        imu_msg.header.frame_id = self.imu_frame_id
        imu_msg.orientation_covariance = ORIENTATION_COV
        imu_msg.angular_velocity.x = gx
        imu_msg.angular_velocity.y = gy
        imu_msg.angular_velocity.z = gz
        imu_msg.angular_velocity_covariance = ANGULAR_VEL_COV
        imu_msg.linear_acceleration.x = ax
        imu_msg.linear_acceleration.y = ay
        imu_msg.linear_acceleration.z = az
        imu_msg.linear_acceleration_covariance = LINEAR_ACCEL_COV
        self.imu_pub.publish(imu_msg)

        mag_msg = MagneticField()
        mag_msg.header.stamp    = stamp
        mag_msg.header.frame_id = self.imu_frame_id
        mag_msg.magnetic_field.x = mx * 1.0e-6
        mag_msg.magnetic_field.y = my * 1.0e-6
        mag_msg.magnetic_field.z = mz * 1.0e-6
        mag_msg.magnetic_field_covariance = MAG_COV
        self.mag_pub.publish(mag_msg)

    # ─────────────────────────────────────────────────────────────────────────
    # cmd_vel → PWM
    # ─────────────────────────────────────────────────────────────────────────
    def _cmd_vel_callback(self, msg: Twist):
        """
        Convert Twist (linear.x, angular.z) to left/right PWM values using
        standard differential drive equations, applies dynamic scaling,
        and applies the unified hardware config.
        """
        vx    = float(msg.linear.x)
        omega = float(msg.angular.z)

        # Reset watchdog timer on every received command
        self.last_cmd_time = self.get_clock().now()

        # 1. Standard Differential Drive Kinematics
        v_left  = vx - (omega * self.wheel_base / 2.0)
        v_right = vx + (omega * self.wheel_base / 2.0)

        # 2. Dynamic PWM scaling with deadband compensation for heavy wheels
        max_v = max(abs(v_left), abs(v_right), self.max_linear_vel, 1e-6)
        
        def scale_pwm(v):
            if abs(v) < 1e-5:
                return 0
            sign = 1 if v > 0 else -1
            ratio = abs(v) / max_v
            # Interpolate between min_pwm and max_pwm
            pwm = self.min_pwm + (self.max_pwm - self.min_pwm) * ratio
            return int(sign * pwm)

        l_pwm = scale_pwm(v_left)
        r_pwm = scale_pwm(v_right)

        # 3. Unified Hardware Configuration application
        if self.swap_left_right_motors:
            l_pwm, r_pwm = r_pwm, l_pwm
        
        if self.invert_left_motor:
            l_pwm = -l_pwm
            
        if self.invert_right_motor:
            r_pwm = -r_pwm

        # 4. Clamp to absolute max_pwm bounds
        l_pwm = max(-self.max_pwm, min(self.max_pwm, l_pwm))
        r_pwm = max(-self.max_pwm, min(self.max_pwm, r_pwm))

        # 5. Send pure, unmodified command to serial
        cmd = f'CMD {l_pwm} {r_pwm}\n'
        try:
            self.ser.write(cmd.encode('ascii'))
        except serial.SerialException as exc:
            self.get_logger().warning(f'Serial write error: {exc}')

    def _check_watchdog(self):
        """Auto-stop the robot if no cmd_vel is received for the timeout period."""
        if (self.get_clock().now() - self.last_cmd_time).nanoseconds * 1e-9 > self.cmd_timeout:
            if hasattr(self, 'ser') and self.ser.is_open:
                try:
                    self.ser.write(b'CMD 0 0\n')
                except serial.SerialException:
                    pass

    # ─────────────────────────────────────────────────────────────────────────
    def destroy_node(self):
        """Send stop command to Arduino before shutting down."""
        if hasattr(self, 'ser') and self.ser.is_open:
            try:
                self.ser.write(b'CMD 0 0\n')
                self.get_logger().info('[encoder_serial_node] Sent stop CMD to Arduino')
            except Exception:
                pass
            self.ser.close()
        super().destroy_node()


# ─────────────────────────────────────────────────────────────────────────────
def main(args=None):
    rclpy.init(args=args)
    node = EncoderSerialNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        try:
            if rclpy.ok():
                rclpy.shutdown()
        except Exception:
            pass


if __name__ == '__main__':
    main()
