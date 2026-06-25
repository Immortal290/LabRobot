#!/usr/bin/env python3
"""
Continuous Map Publisher
Repeatedly publishes the map to RViz with proper QoS settings
"""

import os
import yaml
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos_event import QoSEvent
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy, QoSDurabilityPolicy
from nav_msgs.msg import OccupancyGrid
from ament_index_python.packages import get_package_share_directory


class ContinuousMapPublisher(Node):
    def __init__(self):
        super().__init__('continuous_map_publisher')
        
        # QoS for compatibility with RViz
        qos_profile = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=1,
            durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
        )
        
        self.publisher = self.create_publisher(
            OccupancyGrid,
            '/map',
            qos_profile
        )
        
        # Load map
        pkg_dir = get_package_share_directory('mobile_robot')
        map_yaml = os.path.join(pkg_dir, 'maps', 'rviz_navigation_map.yaml')
        map_pgm = os.path.join(pkg_dir, 'maps', 'rviz_navigation_map.pgm')
        
        # Load YAML
        with open(map_yaml, 'r') as f:
            map_config = yaml.safe_load(f)
        
        # Load PGM
        with open(map_pgm, 'rb') as f:
            # Skip PGM header
            header = f.readline()  # P5
            comment = f.readline()  # comment
            size = f.readline().decode().split()
            width, height = int(size[0]), int(size[1])
            maxval = f.readline()
            
            # Read image data
            data = np.frombuffer(f.read(), dtype=np.uint8)
        
        # Create OccupancyGrid
        self.map_msg = OccupancyGrid()
        self.map_msg.header.frame_id = 'map'
        self.map_msg.info.resolution = float(map_config['resolution'])
        self.map_msg.info.width = width
        self.map_msg.info.height = height
        
        # Set origin
        origin = map_config['origin']
        self.map_msg.info.origin.position.x = float(origin[0])
        self.map_msg.info.origin.position.y = float(origin[1])
        self.map_msg.info.origin.position.z = float(origin[2]) if len(origin) > 2 else 0.0
        
        # Convert occupancy - scale from 0-255 to 0-100
        free_thresh = map_config.get('free_thresh', 0.25)
        occupied_thresh = map_config.get('occupied_thresh', 0.65)
        
        occupancy_data = []
        for val in data:
            normalized = val / 255.0
            if normalized > occupied_thresh:
                occupancy_data.append(100)  # Occupied
            elif normalized < free_thresh:
                occupancy_data.append(0)    # Free
            else:
                occupancy_data.append(-1)   # Unknown
        
        self.map_msg.data = occupancy_data
        
        self.get_logger().info(f"Map loaded: {width}x{height} @ {self.map_msg.info.resolution}m/cell")
        
        # Publish continuously at 10Hz
        self.timer = self.create_timer(0.1, self.publish_map)
    
    def publish_map(self):
        self.map_msg.header.stamp = self.get_clock().now().to_msg()
        self.publisher.publish(self.map_msg)
        self.get_logger().debug('Map published')


def main(args=None):
    rclpy.init(args=args)
    node = ContinuousMapPublisher()
    rclpy.spin(node)
    rclpy.shutdown()


if __name__ == '__main__':
    main()
