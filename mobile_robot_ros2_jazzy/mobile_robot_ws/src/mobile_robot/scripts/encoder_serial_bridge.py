#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════
#  encoder_serial_bridge.py — ROS 2 Jazzy
#  Reads ENC packets from serial, publishes /wheel_ticks
#  Subscribes /cmd_vel, sends CMD packets to Arduino
#
#  Serial IN  → "ENC left_ticks right_ticks\n"
#  Serial OUT ← "CMD left_pwm right_pwm\n"
#
#  This is a thin bridge. Heavy kinematics live in wheel_odom_node.py
# ═══════════════════════════════════════════════════════════════════════════

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
import serial
import math
from std_msgs.msg import String
from geometry_msgs.msg import Twist

SERIAL_PORT  = '/dev/arduino'   # permanent symlink — never changes
SERIAL_BAUD  = 115200


class EncoderSerialBridge(Node):
    def __init__(self):
        super().__init__('encoder_serial_bridge')

        # ── Parameters (overridable from launch file) ─────────────────────
        self.declare_parameter('serial_port', SERIAL_PORT)
        self.declare_parameter('serial_baud', SERIAL_BAUD)
        self.declare_parameter('wheel_base',  0.660)   # metres
        self.declare_parameter('max_linear',  0.5)     # m/s → PWM 200
        self.declare_parameter('max_pwm',     200)     # hard cap

        port           = self.get_parameter('serial_port').value
        baud           = self.get_parameter('serial_baud').value
        self.wheel_base = self.get_parameter('wheel_base').value
        self.max_linear = self.get_parameter('max_linear').value
        self.max_pwm    = self.get_parameter('max_pwm').value

        sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )

        self.tick_pub = self.create_publisher(String, '/wheel_ticks', sensor_qos)
        self.cmd_sub  = self.create_subscription(Twist, '/cmd_vel', self.cmd_cb, 10)

        try:
            self.ser = serial.Serial(port, baud, timeout=0.05)
            self.get_logger().info(
                f'[encoder_serial_bridge] {port} @ {baud} | '
                f'wheel_base={self.wheel_base} m | max_pwm={self.max_pwm}'
            )
        except serial.SerialException as e:
            self.get_logger().error(f'Cannot open {port}: {e}')
            raise SystemExit(1)

        self.timer = self.create_timer(0.01, self.read_serial)

    def read_serial(self):
        try:
            if self.ser.in_waiting == 0:
                return
            raw = self.ser.readline()
        except serial.SerialException as e:
            self.get_logger().warning(f'Serial error: {e}')
            return

        try:
            line = raw.decode('ascii', errors='ignore').strip()
        except Exception:
            return

        if line.startswith('ENC '):
            parts = line.split()
            if len(parts) == 3:
                msg = String()
                msg.data = f'{parts[1]} {parts[2]}'
                self.tick_pub.publish(msg)

    def cmd_cb(self, msg: Twist):
        """Convert Twist to left/right PWM and send to Arduino."""
        vx    = msg.linear.x
        omega = msg.angular.z

        # Differential drive wheel speeds (m/s)
        v_left  = vx - (omega * self.wheel_base / 2.0)
        v_right = vx + (omega * self.wheel_base / 2.0)

        # Normalise to PWM range — guard against division by zero when stopped
        max_v = max(abs(v_left), abs(v_right), self.max_linear, 1e-6)
        scale = self.max_pwm / max_v
        l_pwm = int(max(-self.max_pwm, min(self.max_pwm, v_left  * scale)))
        r_pwm = int(max(-self.max_pwm, min(self.max_pwm, v_right * scale)))

        cmd_str = f'CMD {l_pwm} {r_pwm}\n'
        try:
            self.ser.write(cmd_str.encode('ascii'))
        except serial.SerialException as e:
            self.get_logger().warning(f'Serial write error: {e}')

    def destroy_node(self):
        if hasattr(self, 'ser') and self.ser.is_open:
            try:
                self.ser.write(b'CMD 0 0\n')
            except Exception:
                pass
            self.ser.close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = EncoderSerialBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
