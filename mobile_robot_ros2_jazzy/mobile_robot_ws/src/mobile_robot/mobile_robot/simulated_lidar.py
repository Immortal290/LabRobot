#!/usr/bin/env python3
"""
simulated_lidar.py
─────────────────────────────────────────────────────────────
Simulates a LiDAR (LaserScan) in a 2D environment by raycasting 
against the occupancy grid map (/map) from the robot's pose (/odom).

Publishes:
  - /scan (sensor_msgs/LaserScan) in "laser_frame"

Subscribes:
  - /map (nav_msgs/OccupancyGrid)
  - /odom (nav_msgs/Odometry)
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSDurabilityPolicy
from sensor_msgs.msg import LaserScan
from nav_msgs.msg import OccupancyGrid, Odometry
import math
import numpy as np


class SimulatedLidar(Node):
    def __init__(self):
        super().__init__('simulated_lidar')

        # LiDAR settings
        self.num_rays = 180                 # 2-degree resolution
        self.range_min = 0.12                # minimum range (m)
        self.range_max = 6.0                 # maximum range (m)
        self.ray_step = 0.04                 # raycast resolution (m)

        # Precompute angles and their sin/cos
        self.angles = np.linspace(-math.pi, math.pi, self.num_rays, endpoint=False)
        self.cos_angles = np.cos(self.angles)
        self.sin_angles = np.sin(self.angles)

        # State variables
        self.map_msg = None
        self.robot_x = 0.0
        self.robot_y = 0.0
        self.robot_theta = 0.0

        # QoS for /map (Transient Local is required for static maps)
        map_qos = QoSProfile(depth=1)
        map_qos.durability = QoSDurabilityPolicy.TRANSIENT_LOCAL

        # Subscriptions
        self.map_sub = self.create_subscription(
            OccupancyGrid,
            '/map',
            self.map_callback,
            map_qos
        )

        self.odom_sub = self.create_subscription(
            Odometry,
            '/odom',
            self.odom_callback,
            10
        )

        # Publisher
        self.scan_pub = self.create_publisher(
            LaserScan,
            '/scan',
            10
        )

        # Publish timer (10 Hz)
        self.timer = self.create_timer(0.1, self.publish_scan)
        self.get_logger().info('Simulated LiDAR node started.')

    def map_callback(self, msg):
        """Store the occupancy grid map."""
        self.map_msg = msg
        self.get_logger().info(f'Received map: {msg.info.width}x{msg.info.height} @ {msg.info.resolution} m/px')

    def odom_callback(self, msg):
        """Update robot pose from odometry."""
        self.robot_x = msg.pose.pose.position.x
        self.robot_y = msg.pose.pose.position.y

        # Quaternion to Euler yaw (theta)
        q = msg.pose.pose.orientation
        siny_cosp = 2 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
        self.robot_theta = math.atan2(siny_cosp, cosy_cosp)

    def publish_scan(self):
        """Raycast against the map and publish the LaserScan message."""
        if self.map_msg is None:
            return

        now = self.get_clock().now()

        # Create LaserScan message
        scan = LaserScan()
        scan.header.stamp = now.to_msg()
        scan.header.frame_id = 'laser_frame'
        scan.angle_min = -math.pi
        scan.angle_max = math.pi
        scan.angle_increment = (2 * math.pi) / self.num_rays
        scan.time_increment = 0.0
        scan.scan_time = 0.1
        scan.range_min = self.range_min
        scan.range_max = self.range_max

        # Map info
        res = self.map_msg.info.resolution
        origin_x = self.map_msg.info.origin.position.x
        origin_y = self.map_msg.info.origin.position.y
        width = self.map_msg.info.width
        height = self.map_msg.info.height
        data = self.map_msg.data

        # Raycasting loop
        ranges = []
        for i in range(self.num_rays):
            # Absolute angle of the ray in world coordinates
            ray_angle = self.robot_theta + self.angles[i]
            cos_a = math.cos(ray_angle)
            sin_a = math.sin(ray_angle)

            hit_range = self.range_max
            # Step along the ray
            for r in np.arange(self.range_min, self.range_max, self.ray_step):
                # Calculate world position of the ray point
                wx = self.robot_x + r * cos_a
                wy = self.robot_y + r * sin_a

                # Convert to map index
                mx = int((wx - origin_x) / res)
                my = int((wy - origin_y) / res)

                # Check map bounds
                if mx < 0 or mx >= width or my < 0 or my >= height:
                    hit_range = r
                    break

                # Index in 1D array
                idx = my * width + mx

                # Check if cell is occupied (value > 50)
                if data[idx] > 50:
                    hit_range = r
                    break

            ranges.append(float(hit_range))

        scan.ranges = ranges
        self.scan_pub.publish(scan)


def main(args=None):
    rclpy.init(args=args)
    node = SimulatedLidar()
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
