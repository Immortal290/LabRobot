#!/usr/bin/env python3
"""
cmd_vel_to_joints.py
─────────────────────────────────────────────────────────────
Converts /cmd_vel (Twist) messages to joint state commands AND
publishes odometry so the robot moves in RViz.

Shows robot wheel movement + position translation in RViz.

Usage:
    ros2 run mobile_robot cmd_vel_to_joints
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, TransformStamped, Quaternion
from sensor_msgs.msg import JointState
from nav_msgs.msg import Odometry
from tf2_ros import TransformBroadcaster
import math
from builtin_interfaces.msg import Time


class CmdVelToJoints(Node):
    def __init__(self):
        super().__init__('cmd_vel_to_joints')
        
        # Parameters from URDF
        self.wheel_separation = 0.66      # distance between left/right wheels (m)
        self.wheel_radius = 0.075         # wheel radius (m)
        self.max_linear = 0.8             # max linear velocity (m/s)
        self.max_angular = 1.5            # max angular velocity (rad/s)
        
        # Wheel joint names (from URDF)
        self.left_wheels = [
            "front_left_wheel_joint",
            "rear_left_wheel_joint"
        ]
        self.right_wheels = [
            "front_right_wheel_joint",
            "rear_right_wheel_joint"
        ]
        
        # Subscribe to /cmd_vel
        self.cmd_vel_sub = self.create_subscription(
            Twist,
            '/cmd_vel',
            self.cmd_vel_callback,
            10
        )
        
        # Publish joint states
        self.joint_state_pub = self.create_publisher(
            JointState,
            '/joint_states',
            10
        )
        
        # Publish odometry
        self.odom_pub = self.create_publisher(
            Odometry,
            '/odom',
            10
        )
        
        # TF broadcaster for odom -> base_link
        self.tf_broadcaster = TransformBroadcaster(self)
        
        # Current wheel velocities (rad/s)
        self.left_vel = 0.0
        self.right_vel = 0.0
        self.joint_angles = {name: 0.0 for name in self.left_wheels + self.right_wheels}
        
        # Robot pose in world (odom frame)
        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0
        
        # Timer to publish at 50 Hz
        self.timer = self.create_timer(0.02, self.publish_states)
        
        self.get_logger().info('cmd_vel_to_joints node started. Listening to /cmd_vel...')

    def cmd_vel_callback(self, msg):
        """Convert Twist message to wheel velocities using differential drive kinematics."""
        linear_x = msg.linear.x   # m/s
        angular_z = msg.angular.z # rad/s
        
        # Clamp values
        linear_x = max(-self.max_linear, min(self.max_linear, linear_x))
        angular_z = max(-self.max_angular, min(self.max_angular, angular_z))
        
        # Differential drive kinematics:
        # v_left  = (v_linear - (w_angular * wheel_separation / 2)) / wheel_radius
        # v_right = (v_linear + (w_angular * wheel_separation / 2)) / wheel_radius
        
        self.left_vel = (linear_x - (angular_z * self.wheel_separation / 2.0)) / self.wheel_radius
        self.right_vel = (linear_x + (angular_z * self.wheel_separation / 2.0)) / self.wheel_radius

    def publish_states(self):
        """Publish joint states and odometry based on wheel velocities."""
        dt = 0.02  # 50 Hz
        
        # ─── Update joint angles (wheel rotation) ───
        for name in self.left_wheels:
            self.joint_angles[name] += self.left_vel * dt
        for name in self.right_wheels:
            self.joint_angles[name] += self.right_vel * dt
        
        # ─── Publish joint states (wheel spin visualization) ───
        now = self.get_clock().now()
        joint_state = JointState()
        joint_state.header.stamp = now.to_msg()
        joint_state.header.frame_id = "base_link"
        
        for joint_name in self.left_wheels + self.right_wheels:
            joint_state.name.append(joint_name)
            joint_state.position.append(self.joint_angles[joint_name])
            joint_state.velocity.append(self.left_vel if joint_name in self.left_wheels else self.right_vel)
            joint_state.effort.append(0.0)
        
        self.joint_state_pub.publish(joint_state)
        
        # ─── Update robot pose (odometry) ───
        # Forward kinematics: compute robot velocity in world frame
        linear_vel = (self.left_vel + self.right_vel) / 2.0 * self.wheel_radius
        angular_vel = (self.right_vel - self.left_vel) / self.wheel_separation * self.wheel_radius
        
        # Update pose
        if abs(angular_vel) > 1e-6:
            # Curved motion
            radius = linear_vel / angular_vel
            self.x += radius * (math.sin(self.theta + angular_vel * dt) - math.sin(self.theta))
            self.y += radius * (math.cos(self.theta) - math.cos(self.theta + angular_vel * dt))
        else:
            # Straight motion
            self.x += linear_vel * math.cos(self.theta) * dt
            self.y += linear_vel * math.sin(self.theta) * dt
        
        self.theta += angular_vel * dt
        
        # ─── Publish odometry message ───
        odom = Odometry()
        odom.header.stamp = now.to_msg()
        odom.header.frame_id = "odom"
        odom.child_frame_id = "base_footprint"
        
        # Position
        odom.pose.pose.position.x = self.x
        odom.pose.pose.position.y = self.y
        odom.pose.pose.position.z = 0.0
        
        # Orientation (convert theta to quaternion)
        q = self.euler_to_quaternion(0, 0, self.theta)
        odom.pose.pose.orientation = q
        
        # Velocity
        odom.twist.twist.linear.x = linear_vel
        odom.twist.twist.angular.z = angular_vel
        
        self.odom_pub.publish(odom)
        
        # ─── Broadcast odom -> base_link transform ───
        t = TransformStamped()
        t.header.stamp = now.to_msg()
        t.header.frame_id = "odom"
        t.child_frame_id = "base_footprint"
        
        t.transform.translation.x = self.x
        t.transform.translation.y = self.y
        t.transform.translation.z = 0.0
        
        t.transform.rotation = q
        
        self.tf_broadcaster.sendTransform(t)

    @staticmethod
    def euler_to_quaternion(roll, pitch, yaw):
        """Convert Euler angles to quaternion."""
        cy = math.cos(yaw * 0.5)
        sy = math.sin(yaw * 0.5)
        cp = math.cos(pitch * 0.5)
        sp = math.sin(pitch * 0.5)
        cr = math.cos(roll * 0.5)
        sr = math.sin(roll * 0.5)
        
        q = Quaternion()
        q.w = cr * cp * cy + sr * sp * sy
        q.x = sr * cp * cy - cr * sp * sy
        q.y = cr * sp * cy + sr * cp * sy
        q.z = cr * cp * sy - sr * sp * cy
        
        return q


def main(args=None):
    rclpy.init(args=args)
    node = CmdVelToJoints()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
