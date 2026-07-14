from setuptools import setup, find_packages
import os
from glob import glob

package_name = 'aura_robot'

setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='AURA Team',
    maintainer_email='aura@labrobot.local',
    description='AURA autonomous laboratory delivery robot core nodes',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            # Core bridge — relays between ROS2 and FastAPI WebSocket
            'ros2_bridge        = aura_robot.ros2_bridge:main',
            # Health monitor — watches all nodes, hardware, DB
            'health_monitor     = aura_robot.health_monitor:main',
            # Delivery manager — orchestrates the full delivery lifecycle
            'delivery_manager   = aura_robot.delivery_manager:main',
            # Hardware controller — Arduino serial + servo management
            'hardware_controller = aura_robot.hardware_controller:main',
            # Barcode navigator — scans barcodes and issues nav goals
            'barcode_navigator  = aura_robot.barcode_navigator:main',
            # OTP manager — generates, sends and verifies OTPs
            'otp_manager        = aura_robot.otp_manager:main',
            # Inventory sync — mirrors DB inventory state onto ROS topics
            'inventory_sync     = aura_robot.inventory_sync:main',
        ],
    },
)
