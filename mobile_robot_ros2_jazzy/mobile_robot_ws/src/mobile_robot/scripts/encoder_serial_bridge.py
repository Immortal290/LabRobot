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

SERIAL_PORT = '/dev/ttyUSB0'
SERIAL_BAUD = 115200

# Motor mapping: cmd_vel → PWM
# Adjust WHEEL_BASE and MAX_LINEAR to match your robot
WHEEL_BASE   = 0.660   # m
MAX_LINEAR   = 0.5     # m/s  → maps to PWM 255
MAX_ANGULAR  = 1.5     # rad/s → maps to each motor ± MAX_LINEAR
MAX_PWM      = 200     # limit to avoid excessive current (< 255)


class EncoderSerialBridge(Node):
    def __init__(self):
        super().__init__('encoder_serial_bridge')

        self.declare_parameter('serial_port', SERIAL_PORT)
        self.declare_parameter('serial_baud', SERIAL_BAUD)
        port = self.get_parameter('serial_port').value
        baud = self.get_parameter('serial_baud').value

        sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )

        self.tick_pub = self.create_publisher(String, '/wheel_ticks', sensor_qos)
        self.cmd_sub  = self.create_subscription(Twist, '/cmd_vel', self.cmd_cb, 10)

        try:
            self.ser = serial.Serial(port, baud, timeout=0.05)
            self.get_logger().info(f'Serial bridge: {port} @ {baud}')
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
        v_left  = vx - (omega * WHEEL_BASE / 2.0)
        v_right = vx + (omega * WHEEL_BASE / 2.0)

        # Normalise to PWM range
        scale    = MAX_PWM / max(abs(v_left), abs(v_right), MAX_LINEAR)
        l_pwm    = int(v_left  * scale)
        r_pwm    = int(v_right * scale)
        l_pwm    = max(-MAX_PWM, min(MAX_PWM, l_pwm))
        r_pwm    = max(-MAX_PWM, min(MAX_PWM, r_pwm))

        cmd_str  = f'CMD {l_pwm} {r_pwm}\n'
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
