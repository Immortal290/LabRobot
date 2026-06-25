#!/usr/bin/env python3
"""
simulated_camera.py
─────────────────────────────────────────────────────────────
Simulates a camera in a 2D environment by raycasting against 
the occupancy grid map (/map) from the robot's pose (/odom).
Renders a pseudo-3D first-person view of the environment.

Publishes:
  - /camera/image_raw (sensor_msgs/Image) in "camera" frame

Subscribes:
  - /map (nav_msgs/OccupancyGrid)
  - /odom (nav_msgs/Odometry)
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSDurabilityPolicy, QoSReliabilityPolicy
from sensor_msgs.msg import Image, CameraInfo
from nav_msgs.msg import OccupancyGrid, Odometry
import math
import numpy as np


class SimulatedCamera(Node):
    def __init__(self):
        super().__init__('simulated_camera')

        # Camera rendering settings
        self.width = 80                     # 80x60 for retro look and 4x faster rendering
        self.height = 60
        self.fov = 1.047                     # 60 degrees horizontal FOV
        self.range_min = 0.1
        self.range_max = 6.0                 # max visibility (meters) matching lidar
        self.ray_step = 0.08                 # coarser step size along ray for performance

        # Precompute relative ray angles
        self.angles = np.linspace(-self.fov / 2.0, self.fov / 2.0, self.width)
        
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

        # QoS for /camera/image_raw (Transient Local + Best Effort to match RViz exactly and prevent buffer lag)
        camera_qos = QoSProfile(depth=1)
        camera_qos.durability = QoSDurabilityPolicy.TRANSIENT_LOCAL
        camera_qos.reliability = QoSReliabilityPolicy.BEST_EFFORT

        # Publisher
        self.image_pub = self.create_publisher(
            Image,
            '/camera/image_raw',
            camera_qos
        )

        self.info_pub = self.create_publisher(
            CameraInfo,
            '/camera/camera_info',
            camera_qos
        )

        # Publish timer (10 Hz for smooth visualization without high CPU load)
        self.timer = self.create_timer(0.1, self.render_and_publish)
        self.get_logger().info('Simulated Pseudo-3D Camera node started.')

    def map_callback(self, msg):
        """Store the occupancy grid map."""
        self.map_msg = msg
        self.get_logger().info(f'Received map for camera: {msg.info.width}x{msg.info.height}')

    def odom_callback(self, msg):
        """Update robot pose from odometry."""
        self.robot_x = msg.pose.pose.position.x
        self.robot_y = msg.pose.pose.position.y

        # Convert quaternion to yaw angle (theta)
        q = msg.pose.pose.orientation
        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        self.robot_theta = math.atan2(siny_cosp, cosy_cosp)

    def render_and_publish(self):
        """Render pseudo-3D view and publish to /camera/image_raw."""
        if self.map_msg is None:
            return

        t_start = self.get_clock().now()
        now = t_start

        # Initialize frame: Sky blue ceiling, dark gray floor
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        frame[0:self.height // 2, :, :] = [100, 149, 237]  # Cornflower blue ceiling
        frame[self.height // 2:self.height, :, :] = [50, 50, 50]       # Dark gray floor

        # Map info references
        res = self.map_msg.info.resolution
        origin_x = self.map_msg.info.origin.position.x
        origin_y = self.map_msg.info.origin.position.y
        width = self.map_msg.info.width
        height = self.map_msg.info.height
        data = self.map_msg.data

        # Step size based on map resolution
        step = max(self.ray_step, res * 0.8)

        # Cast rays to find obstacle distances
        for x in range(self.width):
            # Absolute ray angle in world coordinates
            ray_angle = self.robot_theta + self.angles[x]
            cos_a = math.cos(ray_angle)
            sin_a = math.sin(ray_angle)

            hit_range = self.range_max
            # Trace ray
            for r in np.arange(self.range_min, self.range_max, step):
                wx = self.robot_x + r * cos_a
                wy = self.robot_y + r * sin_a

                # Convert world coordinates to map index
                mx = int((wx - origin_x) / res)
                my = int((wy - origin_y) / res)

                # Check bounds
                if mx < 0 or mx >= width or my < 0 or my >= height:
                    hit_range = r
                    break

                idx = my * width + mx
                if data[idx] > 50:  # Occupied cell
                    hit_range = r
                    break

            # Correct distance to avoid fish-eye lens distortion
            corrected_dist = hit_range * math.cos(self.angles[x])
            corrected_dist = max(corrected_dist, self.range_min)

            # Calculate screen projection height of the wall
            # Scale factor chosen so that walls look natural
            proj_height = int((self.height * 0.8) / corrected_dist)
            proj_height = min(proj_height, self.height)

            # Vertical range of the wall column
            y_start = (self.height - proj_height) // 2
            y_end = (self.height + proj_height) // 2

            # Fog shading effect (darker in the distance)
            shade = max(0.0, min(1.0, 1.0 - (hit_range / self.range_max)))
            
            # Use a nice warm wood/brick color for walls, shaded by distance
            r_val = int(160 * shade)
            g_val = int(82 * shade)
            b_val = int(45 * shade)

            # Draw the column slice
            frame[y_start:y_end, x, :] = [r_val, g_val, b_val]

        # Prepare and publish ROS2 image message
        img_msg = Image()
        img_msg.header.stamp = now.to_msg()
        img_msg.header.frame_id = 'camera'
        img_msg.height = self.height
        img_msg.width = self.width
        img_msg.encoding = 'rgb8'
        img_msg.is_bigendian = 0
        img_msg.step = self.width * 3
        img_msg.data = frame.tobytes()

        self.image_pub.publish(img_msg)

        # Prepare and publish CameraInfo message
        info_msg = CameraInfo()
        info_msg.header = img_msg.header
        info_msg.width = self.width
        info_msg.height = self.height
        info_msg.distortion_model = 'plumb_bob'
        f = self.width / (2.0 * math.tan(self.fov / 2.0))
        cx = self.width / 2.0
        cy = self.height / 2.0
        info_msg.k = [f, 0.0, cx, 0.0, f, cy, 0.0, 0.0, 1.0]
        info_msg.d = [0.0, 0.0, 0.0, 0.0, 0.0]
        info_msg.r = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
        info_msg.p = [f, 0.0, cx, 0.0, 0.0, f, cy, 0.0, 0.0, 0.0, 1.0, 0.0]
        self.info_pub.publish(info_msg)
        t_end = self.get_clock().now()
        dt = (t_end - t_start).nanoseconds / 1e6
        self.get_logger().info(f"Render took {dt:.2f} ms")


def main(args=None):
    rclpy.init(args=args)
    node = SimulatedCamera()
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
