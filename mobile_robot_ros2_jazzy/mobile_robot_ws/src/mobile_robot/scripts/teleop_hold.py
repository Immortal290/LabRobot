#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import sys, select, termios, tty
import time

class TeleopHold(Node):
    def __init__(self):
        super().__init__('teleop_hold')
        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.speed = 0.5
        self.turn = 1.0
        
        self.last_key_time = time.time()
        self.last_key = None
        self.timeout = 0.3  # Stops 0.3 seconds after releasing
        
        self.timer = self.create_timer(0.05, self.loop)
        
        print("\n===================================")
        print("      HOLD-TO-MOVE TELEOP")
        print("===================================")
        print("  i : Forward")
        print("  j : Left")
        print("  l : Right")
        print("  , : Backward")
        print("\nLet go of the key to stop instantly.")
        print("Press Ctrl+C to quit.\n")

    def get_key(self):
        tty.setraw(sys.stdin.fileno())
        rlist, _, _ = select.select([sys.stdin], [], [], 0.0)
        if rlist:
            key = sys.stdin.read(1)
        else:
            key = ''
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
        return key

    def loop(self):
        key = self.get_key()
        
        if key:
            self.last_key = key
            self.last_key_time = time.time()
            
        if key == '\x03': # Ctrl+C
            raise SystemExit
            
        twist = Twist()
        
        # If we haven't received a key for longer than the timeout, we stop
        if time.time() - self.last_key_time > self.timeout:
            self.last_key = None
            
        if self.last_key == 'i':
            twist.linear.x = self.speed
        elif self.last_key == ',':
            twist.linear.x = -self.speed
        elif self.last_key == 'j':
            twist.angular.z = self.turn
        elif self.last_key == 'l':
            twist.angular.z = -self.turn
            
        self.pub.publish(twist)

if __name__ == '__main__':
    settings = termios.tcgetattr(sys.stdin)
    rclpy.init()
    node = TeleopHold()
    try:
        rclpy.spin(node)
    except Exception:
        pass
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
        node.destroy_node()
        rclpy.shutdown()
