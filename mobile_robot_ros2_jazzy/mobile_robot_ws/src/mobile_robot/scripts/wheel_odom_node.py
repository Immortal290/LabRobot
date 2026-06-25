#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
#  wheel_odom_node.py  —  ROS 2 Jazzy | AURA Rover
#
#  PURPOSE:
#    Converts raw encoder tick counts from /wheel_ticks into a differential-
#    drive odometry estimate published as nav_msgs/Odometry on /wheel_odom.
#
#  SUBSCRIPTIONS:
#    /wheel_ticks  [std_msgs/String]   "left_ticks right_ticks"
#                   Cumulative signed tick counts from the Arduino encoder bridge.
#                   LEFT  encoder = Left Front motor (encoder used per spec)
#                   RIGHT encoder = Right Front motor (encoder used per spec)
#
#  PUBLICATIONS:
#    /wheel_odom   [nav_msgs/Odometry]
#                   child_frame_id = base_footprint
#                   header.frame_id = odom
#                   Contains pose (x, y, yaw) and twist (vx, vyaw)
#
#  TF (optional, disabled by default):
#    odom → base_footprint  (published when publish_tf=True)
#    NOTE: robot_localization EKF publishes the authoritative odom→base_footprint
#          TF, so publish_tf should remain False in production.
#
#  DIFFERENTIAL DRIVE KINEMATICS:
#    For each cycle:
#      d_left  = Δleft_ticks  / ticks_per_rev × 2π × wheel_radius
#      d_right = Δright_ticks / ticks_per_rev × 2π × wheel_radius
#      linear  = (d_left + d_right) / 2
#      angular = (d_right - d_left) / wheel_separation
#
#    Pose integration (arc method):
#      if |angular| > ε:  (arc)
#        x   += (linear/angular) × (sin(θ + angular) - sin(θ))
#        y   += (linear/angular) × (cos(θ)           - cos(θ + angular))
#      else:  (straight line)
#        x   += linear × cos(θ)
#        y   += linear × sin(θ)
#      θ += angular  (normalised to (-π, π])
#
#  PARAMETERS:
#    wheel_radius      : float — wheel radius in metres
#    wheel_separation  : float — centre-to-centre wheel track width in metres
#    ticks_per_rev     : float — encoder ticks per full wheel revolution
#                                x2 mode (Channel-A CHANGE only): 11 PPR × 2 × gear ≈ 720
#                                x4 mode (A & B CHANGE):           11 PPR × 4 × gear ≈ 1440
#    odom_frame        : str   — odometry frame (default 'odom')
#    base_frame        : str   — robot base frame (default 'base_footprint')
#    publish_tf        : bool  — publish odom→base_footprint TF (default False)
#
# ═══════════════════════════════════════════════════════════════════════════════

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

import math

from nav_msgs.msg import Odometry
from std_msgs.msg import String
from geometry_msgs.msg import TransformStamped, Quaternion
import tf2_ros


# ── Default robot parameters ──────────────────────────────────────────────────
# These match the AURA rover with Rhino 100RPM 25Kgcm motors.
# wheel_separation is computed from URDF: base_width(0.6096) + 0.050 = 0.6596 ≈ 0.660 m
WHEEL_RADIUS_DEFAULT    = 0.065    # metres — ADJUST to your actual wheel radius
WHEEL_SEPARATION_DEFAULT = 0.660   # metres — centre-to-centre
TICKS_PER_REV_DEFAULT   = 720.0    # Rhino encoder: 11 PPR × 2 (x2, Channel-A only) × 32.67 gear ratio ≈ 720
                                    # x2 encoding: only Channel-A CHANGE interrupt is used in firmware
                                    # If you switch to x4 (both A & B interrupts), change this back to 1440

# ── Odometry covariances (6×6 row-major) ─────────────────────────────────────
# For a differential drive robot on a flat floor:
#   x, yaw    : low variance (trustworthy from wheels)
#   y, z      : set to large value (non-holonomic constraint)
#   roll, pitch: locked (2D robot)

POSE_COVARIANCE = [
    5.0e-4, 0.0,    0.0,    0.0,    0.0,    0.0,
    0.0,    5.0e-4, 0.0,    0.0,    0.0,    0.0,
    0.0,    0.0,    1.0e-9, 0.0,    0.0,    0.0,   # z locked (2D)
    0.0,    0.0,    0.0,    1.0e-9, 0.0,    0.0,   # roll locked
    0.0,    0.0,    0.0,    0.0,    1.0e-9, 0.0,   # pitch locked
    0.0,    0.0,    0.0,    0.0,    0.0,    1.0e-3, # yaw
]

TWIST_COVARIANCE = [
    1.0e-3, 0.0,    0.0,    0.0,    0.0,    0.0,
    0.0,    1.0e-9, 0.0,    0.0,    0.0,    0.0,   # vy = 0 (non-holonomic)
    0.0,    0.0,    1.0e-9, 0.0,    0.0,    0.0,
    0.0,    0.0,    0.0,    1.0e-9, 0.0,    0.0,
    0.0,    0.0,    0.0,    0.0,    1.0e-9, 0.0,
    0.0,    0.0,    0.0,    0.0,    0.0,    1.0e-3,
]


def euler_to_quaternion(roll: float, pitch: float, yaw: float) -> Quaternion:
    """Convert Euler angles (radians) to geometry_msgs/Quaternion."""
    cy = math.cos(yaw   * 0.5)
    sy = math.sin(yaw   * 0.5)
    cp = math.cos(pitch * 0.5)
    sp = math.sin(pitch * 0.5)
    cr = math.cos(roll  * 0.5)
    sr = math.sin(roll  * 0.5)
    q = Quaternion()
    q.w = cr * cp * cy + sr * sp * sy
    q.x = sr * cp * cy - cr * sp * sy
    q.y = cr * sp * cy + sr * cp * sy
    q.z = cr * cp * sy - sr * sp * cy
    return q


class WheelOdomNode(Node):
    """
    Differential-drive wheel odometry node for AURA rover.

    Consumes encoder tick counts and outputs nav_msgs/Odometry.
    The robot_localization EKF fuses this with IMU data to produce
    the authoritative /odometry/filtered estimate.
    """

    def __init__(self):
        super().__init__('wheel_odom_node')

        # ── Parameters ────────────────────────────────────────────────────────
        self.declare_parameter('wheel_radius',     WHEEL_RADIUS_DEFAULT)
        self.declare_parameter('wheel_separation', WHEEL_SEPARATION_DEFAULT)
        self.declare_parameter('ticks_per_rev',    TICKS_PER_REV_DEFAULT)
        self.declare_parameter('odom_frame',       'odom')
        self.declare_parameter('base_frame',       'base_footprint')
        self.declare_parameter('publish_tf',       False)

        self.wheel_radius     = self.get_parameter('wheel_radius').value
        self.wheel_separation = self.get_parameter('wheel_separation').value
        self.ticks_per_rev    = self.get_parameter('ticks_per_rev').value
        self.odom_frame       = self.get_parameter('odom_frame').value
        self.base_frame       = self.get_parameter('base_frame').value
        self.publish_tf       = self.get_parameter('publish_tf').value

        # metres of travel per encoder tick
        self.meters_per_tick = (2.0 * math.pi * self.wheel_radius) / self.ticks_per_rev

        # ── Odometry state ────────────────────────────────────────────────────
        self.x          = 0.0
        self.y          = 0.0
        self.yaw        = 0.0
        self.prev_left  = None   # last received left tick count
        self.prev_right = None   # last received right tick count
        self.prev_time  = None   # rclpy.time.Time

        # ── QoS ───────────────────────────────────────────────────────────────
        sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )

        # ── Subscriber: /wheel_ticks ──────────────────────────────────────────
        self.tick_sub = self.create_subscription(
            String, '/wheel_ticks', self._tick_callback, sensor_qos
        )

        # ── Publisher: /wheel_odom ────────────────────────────────────────────
        self.odom_pub = self.create_publisher(Odometry, '/wheel_odom', 10)

        # ── Optional TF broadcaster ───────────────────────────────────────────
        if self.publish_tf:
            self.tf_broadcaster = tf2_ros.TransformBroadcaster(self)

        self.get_logger().info(
            f'[wheel_odom_node] Started | '
            f'r={self.wheel_radius:.4f} m | '
            f'sep={self.wheel_separation:.4f} m | '
            f'ticks/rev={self.ticks_per_rev:.0f} | '
            f'publish_tf={self.publish_tf}'
        )

    # ─────────────────────────────────────────────────────────────────────────
    def _tick_callback(self, msg: String):
        """
        Process incoming tick message and update odometry.

        Message format: "left_ticks right_ticks"  (cumulative signed ints)
        """
        parts = msg.data.strip().split()
        if len(parts) != 2:
            self.get_logger().debug(f'Malformed /wheel_ticks: {repr(msg.data)}')
            return
        try:
            left_ticks  = int(parts[0])
            right_ticks = int(parts[1])
        except ValueError:
            return

        now = self.get_clock().now()

        # ── Initialise on first message ───────────────────────────────────────
        if self.prev_left is None:
            self.prev_left  = left_ticks
            self.prev_right = right_ticks
            self.prev_time  = now
            return

        dt = (now - self.prev_time).nanoseconds * 1.0e-9
        if dt <= 0.0:
            return

        # ── Δticks → distances ────────────────────────────────────────────────
        d_left  = (left_ticks  - self.prev_left)  * self.meters_per_tick
        d_right = (right_ticks - self.prev_right) * self.meters_per_tick

        self.prev_left  = left_ticks
        self.prev_right = right_ticks
        self.prev_time  = now

        # ── Differential-drive kinematics ─────────────────────────────────────
        linear  = (d_left + d_right) / 2.0
        angular = (d_right - d_left) / self.wheel_separation

        # Arc integration for more accurate pose
        if abs(angular) > 1.0e-9:
            radius = linear / angular
            self.x   += radius * (math.sin(self.yaw + angular) - math.sin(self.yaw))
            self.y   += radius * (math.cos(self.yaw)           - math.cos(self.yaw + angular))
        else:
            # Degenerate case: straight line
            self.x += linear * math.cos(self.yaw)
            self.y += linear * math.sin(self.yaw)

        self.yaw += angular
        # Normalise yaw to (-π, π]
        self.yaw = math.atan2(math.sin(self.yaw), math.cos(self.yaw))

        # ── Velocities ────────────────────────────────────────────────────────
        vx    = linear  / dt
        v_yaw = angular / dt

        # ── Build and publish Odometry message ────────────────────────────────
        q = euler_to_quaternion(0.0, 0.0, self.yaw)

        odom = Odometry()
        odom.header.stamp    = now.to_msg()
        odom.header.frame_id = self.odom_frame
        odom.child_frame_id  = self.base_frame

        odom.pose.pose.position.x  = self.x
        odom.pose.pose.position.y  = self.y
        odom.pose.pose.position.z  = 0.0
        odom.pose.pose.orientation = q
        odom.pose.covariance       = POSE_COVARIANCE

        odom.twist.twist.linear.x  = vx
        odom.twist.twist.linear.y  = 0.0
        odom.twist.twist.angular.z = v_yaw
        odom.twist.covariance      = TWIST_COVARIANCE

        self.odom_pub.publish(odom)

        # ── Optional TF broadcast (disabled when EKF provides TF) ─────────────
        if self.publish_tf:
            t = TransformStamped()
            t.header.stamp    = now.to_msg()
            t.header.frame_id = self.odom_frame
            t.child_frame_id  = self.base_frame
            t.transform.translation.x = self.x
            t.transform.translation.y = self.y
            t.transform.translation.z = 0.0
            t.transform.rotation      = q
            self.tf_broadcaster.sendTransform(t)


# ─────────────────────────────────────────────────────────────────────────────
def main(args=None):
    rclpy.init(args=args)
    node = WheelOdomNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        # Guard: rclpy.shutdown() is already invoked by the executor on SIGINT.
        # Calling it again raises RCLError: rcl_shutdown already called.
        try:
            if rclpy.ok():
                rclpy.shutdown()
        except Exception:
            pass


if __name__ == '__main__':
    main()
