from setuptools import setup, find_packages
import os
from glob import glob

package_name = 'mobile_robot'

setup(
    name=package_name,
    version='2.0.0',
    packages=find_packages(),
    data_files=[
        # Package manifest
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),

        # Launch files
        (os.path.join('share', package_name, 'launch'),
            glob('launch/*.launch.py')),

        # Config files
        (os.path.join('share', package_name, 'config'),
            glob('config/*.yaml')),

        # URDF / xacro files
        (os.path.join('share', package_name, 'urdf'),
            glob('urdf/*.urdf.xacro') + glob('urdf/*.xacro')),

        # RViz configurations
        (os.path.join('share', package_name, 'rviz'),
            glob('rviz/*.rviz')),

        # Maps
        (os.path.join('share', package_name, 'maps'),
            glob('maps/*.yaml') + glob('maps/*.pgm')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='AURA Project',
    maintainer_email='your@email.com',
    description='AURA Autonomous Rover — ROS 2 Jazzy navigation stack',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            # Real hardware scripts
            'encoder_serial_node  = mobile_robot.scripts.encoder_serial_node:main',
            'encoder_serial_node.py = mobile_robot.scripts.encoder_serial_node:main',
            'imu_serial_node      = mobile_robot.scripts.imu_serial_node:main',
            'wheel_odom_node      = mobile_robot.scripts.wheel_odom_node:main',
            'wheel_odom_node.py   = mobile_robot.scripts.wheel_odom_node:main',

            # Teleoperation
            'teleop_hold          = mobile_robot.scripts.teleop_hold:main',
            'teleop_hold.py       = mobile_robot.scripts.teleop_hold:main',

            # Simulation/utility scripts
            'cmd_vel_to_joints    = mobile_robot.cmd_vel_to_joints:main',
        ],
    },
)
