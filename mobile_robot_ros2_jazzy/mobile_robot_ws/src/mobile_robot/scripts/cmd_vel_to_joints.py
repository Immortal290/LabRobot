#!/usr/bin/env python3
"""
cmd_vel_to_joints.py
─────────────────────────────────────────────────────────────
Converts /cmd_vel (Twist) messages to joint state commands.
Shows robot wheel movement in RViz based on keyboard teleop input.

Usage:
    ros2 run mobile_robot cmd_vel_to_joints
    
Or in a separate terminal while display_with_teleop.launch.py is running.
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import JointState
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
        
        # Current wheel velocities (rad/s)
        self.left_vel = 0.0
        self.right_vel = 0.0
        self.joint_angles = {name: 0.0 for name in self.left_wheels + self.right_wheels}
        
        # Timer to publish joint states at 50 Hz
        self.timer = self.create_timer(0.02, self.publish_joint_states)
        
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

    def publish_joint_states(self):
        """Publish updated joint states based on wheel velocities."""
        # Update joint angles (integrate velocity)
        dt = 0.02  # 50 Hz
        for name in self.left_wheels:
            self.joint_angles[name] += self.left_vel * dt
        for name in self.right_wheels:
            self.joint_angles[name] += self.right_vel * dt
        
        # Create JointState message
        now = self.get_clock().now()
        joint_state = JointState()
        joint_state.header.stamp = now.to_msg()
        joint_state.header.frame_id = "base_link"
        
        # Add all wheel joints
        for joint_name in self.left_wheels + self.right_wheels:
            joint_state.name.append(joint_name)
            joint_state.position.append(self.joint_angles[joint_name])
            joint_state.velocity.append(self.left_vel if joint_name in self.left_wheels else self.right_vel)
            joint_state.effort.append(0.0)
        
        self.joint_state_pub.publish(joint_state)


def main(args=None):
    rclpy.init(args=args)
    node = CmdVelToJoints()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
