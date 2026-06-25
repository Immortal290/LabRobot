#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSDurabilityPolicy, QoSReliabilityPolicy
from sensor_msgs.msg import Image, CameraInfo
import cv2
from cv_bridge import CvBridge
import time
import numpy as np
import math

class RealCamera(Node):
    def __init__(self):
        super().__init__('real_camera')
        
        self.declare_parameter('device_id', 0)
        self.device_id = self.get_parameter('device_id').value
        
        # Publisher QoS to match RViz exactly
        camera_qos = QoSProfile(depth=1)
        camera_qos.durability = QoSDurabilityPolicy.TRANSIENT_LOCAL
        camera_qos.reliability = QoSReliabilityPolicy.BEST_EFFORT
        
        self.image_pub = self.create_publisher(
            Image,
            '/real_camera/image_raw',
            camera_qos
        )
        
        self.info_pub = self.create_publisher(
            CameraInfo,
            '/real_camera/camera_info',
            camera_qos
        )
        
        self.bridge = CvBridge()
        
        # Try to open camera device
        self.cap = cv2.VideoCapture(self.device_id)
        if not self.cap.isOpened():
            self.get_logger().warn(f"Failed to open camera device {self.device_id}. Will publish a fallback test pattern.")
            self.use_fallback = True
        else:
            self.get_logger().info(f"Successfully opened camera device {self.device_id}")
            self.use_fallback = False
            
        # Publish timer (15 Hz)
        self.timer = self.create_timer(0.066, self.capture_and_publish)
        self.tick = 0

    def capture_and_publish(self):
        now = self.get_clock().now()
        frame = None
        
        if not self.use_fallback:
            ret, frame = self.cap.read()
            if not ret or frame is None:
                self.get_logger().warn("Failed to read frame from camera. Switching to fallback pattern.")
                self.use_fallback = True
                
        if self.use_fallback:
            # Generate fallback pattern: colored diagonal sweep
            self.tick += 1
            frame = np.zeros((240, 320, 3), dtype=np.uint8)
            # Draw gradient background
            for y in range(240):
                frame[y, :, 0] = int(y / 240.0 * 150) # Blue
                frame[y, :, 1] = int((1.0 - y / 240.0) * 100) # Green
            
            # Draw moving circle
            cx = int(160 + 80 * math.cos(self.tick * 0.1))
            cy = int(120 + 40 * math.sin(self.tick * 0.1))
            cv2.circle(frame, (cx, cy), 20, (0, 0, 255), -1) # Red circle
            
            # Overlay text
            cv2.putText(frame, "REAL LIFE CAMERA FEED", (15, 40), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(frame, "Status: Fallback Test Pattern", (15, 70), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            cv2.putText(frame, f"Device: /dev/video{self.device_id}", (15, 95), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            cv2.putText(frame, f"Time: {time.strftime('%H:%M:%S')}", (15, 210), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        
        # Publish image
        try:
            # We want to publish in rgb8/bgr8 format
            img_msg = self.bridge.cv2_to_imgmsg(frame, encoding="bgr8")
            img_msg.header.stamp = now.to_msg()
            img_msg.header.frame_id = 'camera'
            self.image_pub.publish(img_msg)
            
            # Publish camera info
            info_msg = CameraInfo()
            info_msg.header = img_msg.header
            h, w = frame.shape[:2]
            info_msg.width = w
            info_msg.height = h
            info_msg.distortion_model = 'plumb_bob'
            f = w / 2.0
            cx = w / 2.0
            cy = h / 2.0
            info_msg.k = [f, 0.0, cx, 0.0, f, cy, 0.0, 0.0, 1.0]
            info_msg.d = [0.0, 0.0, 0.0, 0.0, 0.0]
            info_msg.r = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
            info_msg.p = [f, 0.0, cx, 0.0, 0.0, f, cy, 0.0, 0.0, 0.0, 1.0, 0.0]
            self.info_pub.publish(info_msg)
        except Exception as e:
            self.get_logger().error(f"Failed to publish image: {e}")

    def __del__(self):
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()

def main(args=None):
    rclpy.init(args=args)
    node = RealCamera()
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
