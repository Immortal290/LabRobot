#!/usr/bin/env python3
"""
check_odom_calibration.py
────────────────────────────────────────────────────────────────────────────
Live comparison tool for calibrating wheel odometry.

Prints side-by-side distance and heading reported by /wheel_odom and
/rf2o_odom so you can:
  1. Drive exactly N metres in a straight line and compare reported distance
     to your tape-measured ground truth -> adjust wheel_radius.
  2. Rotate exactly 360 degrees and compare reported heading change to a
     protractor/floor-marked ground truth -> adjust wheel_separation.
  3. Cross-check wheel_odom against rf2o_odom directly -- large persistent
     disagreement between the two usually means wheel slip or a wheel
     calibration error, since rf2o is slip-independent.

USAGE:
    ros2 run mobile_robot_mapping check_odom_calibration.py
────────────────────────────────────────────────────────────────────────────
"""

import math
import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry


def yaw_from_quaternion(q):
    siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny_cosp, cosy_cosp)


class OdomCalibrationChecker(Node):
    def __init__(self):
        super().__init__('check_odom_calibration')

        self.wheel_start = None
        self.rf2o_start = None
        self.wheel_last = None
        self.rf2o_last = None

        self.create_subscription(Odometry, '/wheel_odom', self.wheel_cb, 10)
        self.create_subscription(Odometry, '/rf2o_odom', self.rf2o_cb, 10)
        self.create_timer(1.0, self.report)

        self.get_logger().info(
            'Listening on /wheel_odom and /rf2o_odom. '
            'Drive a known distance or rotate a known angle and compare.'
        )

    def wheel_cb(self, msg):
        pos = msg.pose.pose.position
        yaw = yaw_from_quaternion(msg.pose.pose.orientation)
        self.wheel_last = (pos.x, pos.y, yaw)
        if self.wheel_start is None:
            self.wheel_start = self.wheel_last

    def rf2o_cb(self, msg):
        pos = msg.pose.pose.position
        yaw = yaw_from_quaternion(msg.pose.pose.orientation)
        self.rf2o_last = (pos.x, pos.y, yaw)
        if self.rf2o_start is None:
            self.rf2o_start = self.rf2o_last

    def report(self):
        if not self.wheel_last or not self.rf2o_last:
            self.get_logger().warn('Waiting for both /wheel_odom and /rf2o_odom...')
            return

        wx0, wy0, wyaw0 = self.wheel_start
        wx, wy, wyaw = self.wheel_last
        wheel_dist = math.hypot(wx - wx0, wy - wy0)
        wheel_yaw_deg = math.degrees(wyaw - wyaw0)

        rx0, ry0, ryaw0 = self.rf2o_start
        rx, ry, ryaw = self.rf2o_last
        rf2o_dist = math.hypot(rx - rx0, ry - ry0)
        rf2o_yaw_deg = math.degrees(ryaw - ryaw0)

        print('─' * 60)
        print(f'  wheel_odom : dist={wheel_dist:6.3f} m   yaw={wheel_yaw_deg:7.2f} deg')
        print(f'  rf2o_odom  : dist={rf2o_dist:6.3f} m   yaw={rf2o_yaw_deg:7.2f} deg')
        print(f'  yaw disagreement: {abs(wheel_yaw_deg - rf2o_yaw_deg):.2f} deg')


def main():
    rclpy.init()
    node = OdomCalibrationChecker()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
