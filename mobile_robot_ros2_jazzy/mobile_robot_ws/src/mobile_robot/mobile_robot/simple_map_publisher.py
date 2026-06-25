#!/usr/bin/env python3
"""
simple_map_publisher.py
─────────────────────────────────────────────────────────────
Publishes the occupancy grid map directly to RViz.
Simpler than nav2_map_server and more compatible with RViz QoS.

Usage:
    ros2 run mobile_robot simple_map_publisher
"""

import rclpy
from rclpy.node import Node
from nav_msgs.msg import OccupancyGrid, MapMetaData
from geometry_msgs.msg import Pose, Point, Quaternion
import numpy as np
from ament_index_python.packages import get_package_share_directory
import os


class SimpleMapPublisher(Node):
    def __init__(self):
        super().__init__('simple_map_publisher')
        
        # Get package directory
        pkg_dir = get_package_share_directory('mobile_robot')
        map_dir = os.path.join(pkg_dir, 'maps')
        
        # Load map from PGM file
        pgm_file = os.path.join(map_dir, 'rviz_navigation_map.pgm')
        
        try:
            self.map_data = self.load_pgm(pgm_file)
            self.get_logger().info(f'Loaded map: {pgm_file}')
        except Exception as e:
            self.get_logger().error(f'Failed to load map: {e}')
            return
        
        # Publisher for map
        self.map_pub = self.create_publisher(
            OccupancyGrid,
            '/map',
            qos_profile=rclpy.qos.QoSProfile(
                reliability=rclpy.qos.ReliabilityPolicy.RELIABLE,
                history=rclpy.qos.HistoryPolicy.KEEP_LAST,
                depth=1,
            )
        )
        
        # Publish map at startup and periodically
        self.timer = self.create_timer(2.0, self.publish_map)
        self.published = False
        
        self.get_logger().info('Map publisher started')
    
    def load_pgm(self, filepath):
        """Load PGM image file."""
        with open(filepath, 'rb') as f:
            # Read PGM header
            magic = f.readline()  # P5 or P6
            comment = f.readline()  # Comment line
            size_line = f.readline()  # Width Height
            width, height = map(int, size_line.split())
            max_val = int(f.readline())
            
            # Read binary data
            data = f.read(width * height)
            img = np.frombuffer(data, dtype=np.uint8)
            img = img.reshape((height, width))
            
            return {
                'width': width,
                'height': height,
                'data': img,
            }
    
    def publish_map(self):
        """Publish the occupancy grid map."""
        if not self.map_data:
            return
        
        # Create OccupancyGrid message
        msg = OccupancyGrid()
        msg.header.frame_id = 'map'
        msg.header.stamp = self.get_clock().now().to_msg()
        
        # Map metadata
        msg.info = MapMetaData()
        msg.info.resolution = 0.1  # 10cm per cell
        msg.info.width = self.map_data['width']
        msg.info.height = self.map_data['height']
        
        # Origin at center of map (-10, -10)
        msg.info.origin = Pose()
        msg.info.origin.position = Point(x=-10.0, y=-10.0, z=0.0)
        msg.info.origin.orientation = Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)
        
        # Convert image to occupancy grid
        # PGM: 255 = white (free), 0 = black (occupied)
        # OccupancyGrid: 0 = free, 100 = occupied, -1 = unknown
        img_data = self.map_data['data'].flatten()
        occupancy = np.zeros(len(img_data), dtype=np.int8)
        
        for i, val in enumerate(img_data):
            if val < 64:
                occupancy[i] = 100  # Obstacle
            elif val > 192:
                occupancy[i] = 0    # Free space
            else:
                occupancy[i] = -1   # Unknown
        
        msg.data = occupancy.tolist()
        
        # Publish
        self.map_pub.publish(msg)
        
        if not self.published:
            self.get_logger().info(
                f'✓ Published map: {self.map_data["width"]}x{self.map_data["height"]} '
                f'@ 0.1m/cell'
            )
            self.published = True


def main(args=None):
    rclpy.init(args=args)
    node = SimpleMapPublisher()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
