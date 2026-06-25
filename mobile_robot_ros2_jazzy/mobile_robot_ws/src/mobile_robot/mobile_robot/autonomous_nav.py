#!/usr/bin/env python3
"""
autonomous_nav.py
─────────────────────────────────────────────────────────────
Simple autonomous navigation node for testing.

Publishes:
  - /nav_goals (geometry_msgs/PoseStamped) - navigation waypoints
  - /goal_pose (geometry_msgs/PoseStamped) - single goal pose

Subscribes to:
  - /odom (nav_msgs/Odometry) - robot position

Usage:
    ros2 run mobile_robot autonomous_nav

Then send goals via:
    ros2 topic pub /goal_pose geometry_msgs/PoseStamped \
      "{header: {stamp: now, frame_id: 'map'}, pose: {position: {x: 2.0, y: 2.0, z: 0}}}"
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped, Pose, Point, Quaternion, Twist
from nav_msgs.msg import Odometry
import math


class AutonomousNav(Node):
    def __init__(self):
        super().__init__('autonomous_nav')
        
        # Subscribers
        self.odom_sub = self.create_subscription(
            Odometry,
            '/odom',
            self.odom_callback,
            10
        )
        
        self.goal_sub = self.create_subscription(
            PoseStamped,
            '/goal_pose',
            self.goal_callback,
            10
        )
        
        # Publishers
        self.cmd_vel_pub = self.create_publisher(
            Twist,
            '/cmd_vel',
            10
        )
        
        # Current pose
        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0
        
        # Target goal
        self.goal_x = None
        self.goal_y = None
        self.goal_theta = None
        self.goal_active = False
        
        # Control parameters
        self.max_linear_vel = 0.5   # m/s
        self.max_angular_vel = 1.0  # rad/s
        self.dist_tolerance = 0.1   # m
        self.angle_tolerance = 0.2  # rad (≈ 11 degrees)
        
        # Timer for control loop (10 Hz)
        self.timer = self.create_timer(0.1, self.control_loop)
        
        self.get_logger().info('Autonomous navigation node started.')
        self.get_logger().info('Send goals via: ros2 topic pub /goal_pose geometry_msgs/PoseStamped ...')

    def odom_callback(self, msg):
        """Update robot position from odometry."""
        self.x = msg.pose.pose.position.x
        self.y = msg.pose.pose.position.y
        
        # Extract yaw from quaternion
        q = msg.pose.pose.orientation
        siny_cosp = 2 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
        self.theta = math.atan2(siny_cosp, cosy_cosp)

    def goal_callback(self, msg):
        """Receive new navigation goal."""
        self.goal_x = msg.pose.position.x
        self.goal_y = msg.pose.position.y
        self.goal_active = True
        
        q = msg.pose.orientation
        siny_cosp = 2 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
        self.goal_theta = math.atan2(siny_cosp, cosy_cosp)
        
        self.get_logger().info(f'New goal: ({self.goal_x:.2f}, {self.goal_y:.2f}), theta: {self.goal_theta:.2f}')

    def control_loop(self):
        """Control loop to move towards goal."""
        if not self.goal_active:
            # No goal set - stop
            cmd = Twist()
            self.cmd_vel_pub.publish(cmd)
            return
        
        # Calculate distance to goal
        dx = self.goal_x - self.x
        dy = self.goal_y - self.y
        dist_to_goal = math.sqrt(dx**2 + dy**2)
        
        # Calculate angle to goal
        angle_to_goal = math.atan2(dy, dx)
        
        # Calculate angle error (normalize to [-π, π])
        angle_error = angle_to_goal - self.theta
        while angle_error > math.pi:
            angle_error -= 2 * math.pi
        while angle_error < -math.pi:
            angle_error += 2 * math.pi
        
        # Check if goal reached
        if dist_to_goal < self.dist_tolerance and abs(angle_error) < self.angle_tolerance:
            self.get_logger().info('Goal reached!')
            self.goal_active = False
            cmd = Twist()
            self.cmd_vel_pub.publish(cmd)
            return
        
        # Simple proportional control
        # First rotate towards goal, then move
        
        cmd = Twist()
        
        if abs(angle_error) > self.angle_tolerance * 2:
            # Still need to rotate significantly
            cmd.angular.z = math.copysign(
                min(abs(angle_error), self.max_angular_vel),
                angle_error
            )
            cmd.linear.x = 0.0
        else:
            # Move towards goal while maintaining heading
            cmd.linear.x = min(dist_to_goal, self.max_linear_vel)
            cmd.angular.z = math.copysign(
                min(abs(angle_error) * 0.5, self.max_angular_vel),
                angle_error
            )
        
        self.cmd_vel_pub.publish(cmd)


def main(args=None):
    rclpy.init(args=args)
    node = AutonomousNav()
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
