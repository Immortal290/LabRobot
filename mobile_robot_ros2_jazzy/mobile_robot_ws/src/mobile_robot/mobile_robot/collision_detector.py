#!/usr/bin/env python3
"""
collision_detector.py
─────────────────────────────────────────────────────────────
Lightweight collision detection for RViz navigation.

Monitors costmap and detects obstacles in robot's path.
Publishes collision alerts for safety checks.

Topics:
  INPUT:  /map (occupancy grid)
  OUTPUT: /collision_alert (std_msgs/Bool)
  OUTPUT: /closest_obstacle_distance (std_msgs/Float32)

ROS 2 Jazzy | Raspberry Pi 5 compatible

Usage:
    ros2 run mobile_robot collision_detector
"""

import rclpy
from rclpy.node import Node
from nav_msgs.msg import OccupancyGrid
from std_msgs.msg import Bool, Float32
from geometry_msgs.msg import PointStamped
import math
import numpy as np


class CollisionDetector(Node):
    def __init__(self):
        super().__init__('collision_detector')
        
        # Subscription to map/costmap
        self.map_sub = self.create_subscription(
            OccupancyGrid,
            '/map',
            self.map_callback,
            1  # Low frequency - map rarely changes
        )
        
        # Publishers
        self.collision_pub = self.create_publisher(
            Bool,
            '/collision_alert',
            10
        )
        
        self.distance_pub = self.create_publisher(
            Float32,
            '/closest_obstacle_distance',
            10
        )
        
        # Parameters
        self.declare_parameter('safety_radius', 0.5)  # meters
        self.declare_parameter('collision_threshold', 50)  # 0-100 costmap value
        self.declare_parameter('check_frequency', 10.0)  # Hz
        
        self.safety_radius = self.get_parameter('safety_radius').value
        self.collision_threshold = self.get_parameter('collision_threshold').value
        
        # Map data
        self.map_data = None
        self.map_resolution = 0.1
        self.map_origin_x = -10.0
        self.map_origin_y = -10.0
        self.map_width = 200
        self.map_height = 200
        
        # Robot position (from odometry - optional)
        self.robot_x = 0.0
        self.robot_y = 0.0
        
        # Timer for collision checking
        check_period = 1.0 / self.get_parameter('check_frequency').value
        self.timer = self.create_timer(check_period, self.check_collision)
        
        self.get_logger().info('Collision detector node started.')
        self.get_logger().info(f'Safety radius: {self.safety_radius}m')

    def map_callback(self, msg):
        """Receive and process occupancy grid map."""
        self.map_data = np.array(msg.data, dtype=np.uint8).reshape(
            (msg.info.height, msg.info.width)
        )
        self.map_resolution = msg.info.resolution
        self.map_origin_x = msg.info.origin.position.x
        self.map_origin_y = msg.info.origin.position.y
        self.map_width = msg.info.width
        self.map_height = msg.info.height

    def check_collision(self):
        """Check if robot collides with obstacles."""
        if self.map_data is None:
            return
        
        # Convert robot position to map coordinates
        map_x = int((self.robot_x - self.map_origin_x) / self.map_resolution)
        map_y = int((self.robot_y - self.map_origin_y) / self.map_resolution)
        
        # Safety check - ensure coordinates are within map
        if not (0 <= map_x < self.map_width and 0 <= map_y < self.map_height):
            self.get_logger().warn('Robot outside map bounds!')
            return
        
        # Search for obstacles within safety radius
        radius_cells = int(self.safety_radius / self.map_resolution)
        closest_distance = float('inf')
        collision_detected = False
        
        for dy in range(-radius_cells, radius_cells + 1):
            for dx in range(-radius_cells, radius_cells + 1):
                check_x = map_x + dx
                check_y = map_y + dy
                
                # Boundary check
                if not (0 <= check_x < self.map_width and 0 <= check_y < self.map_height):
                    continue
                
                cost = self.map_data[check_y, check_x]
                
                # Calculate actual distance
                distance = math.sqrt(dx**2 + dy**2) * self.map_resolution
                
                # Check if obstacle
                if cost > self.collision_threshold:
                    collision_detected = True
                    closest_distance = min(closest_distance, distance)
        
        # Publish results
        collision_msg = Bool()
        collision_msg.data = collision_detected
        self.collision_pub.publish(collision_msg)
        
        distance_msg = Float32()
        distance_msg.data = float(closest_distance) if closest_distance != float('inf') else -1.0
        self.distance_pub.publish(distance_msg)
        
        # Log if collision detected
        if collision_detected:
            self.get_logger().warn(
                f'⚠️  COLLISION ALERT! Obstacle at {closest_distance:.2f}m'
            )


def main(args=None):
    rclpy.init(args=args)
    node = CollisionDetector()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
