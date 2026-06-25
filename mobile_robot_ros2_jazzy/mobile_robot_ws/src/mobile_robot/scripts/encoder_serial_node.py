#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
#  encoder_serial_node.py  —  ROS 2 Jazzy | AURA Rover
#
#  PURPOSE:
#    Bi-directional serial bridge between the Raspberry Pi and the Arduino Nano.
#
#  SERIAL PROTOCOL (Arduino side):
#    IN  (Arduino → Pi):  "ENC <left_ticks> <right_ticks>\n"
#    OUT (Pi → Arduino):  "CMD <left_pwm> <right_pwm>\n"
#
#  ROS INTERFACE:
#    Publishes:   /wheel_ticks   [std_msgs/String]  "left_ticks right_ticks"
#    Subscribes:  /cmd_vel       [geometry_msgs/Twist]
#
#  ARCHITECTURE:
#    ┌──────────────────────────────────────────────────────────────────────────┐
#    │  Arduino Nano                                                            │
#    │    BTS7960 Left  → Left Front + Left Rear motors (parallel)             │
#    │    BTS7960 Right → Right Front + Right Rear motors (parallel)           │
#    │    Encoder LEFT  → Left Front quadrature encoder                        │
#    │    Encoder RIGHT → Right Front quadrature encoder                       │
#    │                                                                          │
#    │    Publishes: "ENC left_ticks right_ticks\n"                            │
#    │    Receives:  "CMD left_pwm right_pwm\n"   (PWM range: -255 to 255)     │
#    └──────────────────────────────────────────────────────────────────────────┘
#                         ↕  USB Serial /dev/ttyUSB0
#    ┌──────────────────────────────────────────────────────────────────────────┐
#    │  encoder_serial_node (this file)                                        │
#    │    Reads ENC packets → publishes /wheel_ticks                           │
#    │    Subscribes /cmd_vel → computes PWM → sends CMD packets               │
#    └──────────────────────────────────────────────────────────────────────────┘
#
#  PARAMETERS (set via launch file or ros2 param):
#    serial_port    : string  — default '/dev/ttyUSB0'
#    serial_baud    : int     — default 115200
#    wheel_base     : float   — metres, centre-to-centre wheel separation
#    max_linear_vel : float   — m/s that maps to MAX_PWM
#    max_pwm        : int     — PWM ceiling (< 255 to protect motors)
#
# ═══════════════════════════════════════════════════════════════════════════════

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

import serial

from std_msgs.msg import String
from geometry_msgs.msg import Twist


class EncoderSerialNode(Node):
    """
    Serial bridge node for AURA rover Arduino Nano.

    Reads ENC packets from Arduino and publishes cumulative tick counts on
    /wheel_ticks.  Converts incoming /cmd_vel Twist messages into PWM
    commands sent back to the Arduino.
    """

    def __init__(self):
        super().__init__('encoder_serial_node')

        # ── Declare parameters ────────────────────────────────────────────────
        self.declare_parameter('serial_port',    '/dev/ttyUSB0')
        self.declare_parameter('serial_baud',    115200)
        self.declare_parameter('wheel_base',     0.660)   # metres
        self.declare_parameter('max_linear_vel', 0.5)     # m/s → MAX_PWM
        self.declare_parameter('max_pwm',        200)     # PWM ceiling

        port                = self.get_parameter('serial_port').value
        baud                = self.get_parameter('serial_baud').value
        self.wheel_base     = self.get_parameter('wheel_base').value
        self.max_linear_vel = self.get_parameter('max_linear_vel').value
        self.max_pwm        = self.get_parameter('max_pwm').value

        # ── QoS for sensor data ───────────────────────────────────────────────
        sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )

        # ── Publisher: /wheel_ticks ───────────────────────────────────────────
        # Message format: "left_ticks right_ticks"  (cumulative, signed integers)
        self.tick_pub = self.create_publisher(String, '/wheel_ticks', sensor_qos)

        # ── Subscriber: /cmd_vel ──────────────────────────────────────────────
        self.cmd_sub = self.create_subscription(
            Twist, '/cmd_vel', self._cmd_vel_callback, 10
        )

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

        # ── Serial read timer (10 ms polling) ─────────────────────────────────
        self.create_timer(0.01, self._read_serial)

        self.get_logger().info(
            f'[encoder_serial_node] Ready | wheel_base={self.wheel_base} m | '
            f'max_pwm={self.max_pwm}'
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Serial reader
    # ─────────────────────────────────────────────────────────────────────────
    def _read_serial(self):
        """Read one line from serial and parse ENC packets."""
        try:
            if self.ser.in_waiting == 0:
                return
            raw = self.ser.readline()
        except serial.SerialException as exc:
            self.get_logger().warning(f'Serial read error: {exc}')
            return

        try:
            line = raw.decode('ascii', errors='ignore').strip()
        except Exception:
            return

        if line.startswith('ENC'):
            self._handle_enc(line)
        elif line.startswith('ROVER_READY') or line.startswith('DBG ') or line.startswith('LOG '):
            # Pass-through Arduino startup / debug messages to ROS log
            self.get_logger().info(f'[Arduino] {line}')

    def _handle_enc(self, line: str):
        """
        Parse encoder packet and publish to /wheel_ticks.

        Supports both formats sent by Arduino firmware:
          Space-separated:  "ENC left_ticks right_ticks"
          Comma-separated:  "ENC,left_ticks,right_ticks"  (actual flashed firmware)
        """
        # Normalise: replace commas with spaces, then split
        normalised = line.replace(',', ' ')
        parts = normalised.split()
        # parts[0] = 'ENC', parts[1] = left, parts[2] = right
        if len(parts) != 3:
            self.get_logger().debug(f'Malformed ENC packet: {repr(line)}')
            return

        try:
            left  = int(parts[1])
            right = int(parts[2])
        except ValueError:
            self.get_logger().debug(f'ENC parse error: {repr(line)}')
            return

        msg = String()
        msg.data = f'{left} {right}'
        self.tick_pub.publish(msg)
        self.get_logger().debug(f'Ticks L={left} R={right}')

    # ─────────────────────────────────────────────────────────────────────────
    # cmd_vel → PWM
    # ─────────────────────────────────────────────────────────────────────────
    def _cmd_vel_callback(self, msg: Twist):
        """
        Convert Twist (linear.x, angular.z) to left/right PWM values.

        Differential drive kinematics:
          v_left  = linear_x - (angular_z * wheel_base / 2)
          v_right = linear_x + (angular_z * wheel_base / 2)

        Both are normalised to [-max_pwm, +max_pwm].
        """
        vx    = float(msg.linear.x)
        omega = float(msg.angular.z)

        v_left  = vx - (omega * self.wheel_base / 2.0)
        v_right = vx + (omega * self.wheel_base / 2.0)

        # Scale so that max_linear_vel → max_pwm
        scale  = self.max_pwm / self.max_linear_vel
        l_pwm  = int(v_left  * scale)
        r_pwm  = int(v_right * scale)

        # Clamp to ±max_pwm
        l_pwm = max(-self.max_pwm, min(self.max_pwm, l_pwm))
        r_pwm = max(-self.max_pwm, min(self.max_pwm, r_pwm))

        cmd = f'CMD {l_pwm} {r_pwm}\n'
        try:
            self.ser.write(cmd.encode('ascii'))
        except serial.SerialException as exc:
            self.get_logger().warning(f'Serial write error: {exc}')

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
        rclpy.shutdown()


if __name__ == '__main__':
    main()
