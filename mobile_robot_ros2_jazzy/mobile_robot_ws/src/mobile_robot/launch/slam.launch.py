#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
#  slam.launch.py  —  SLAM Toolbox Mapping Launch
#  ROS 2 Jazzy | AURA Rover
#
#  PURPOSE:
#    Launches SLAM Toolbox in online async mapping mode.
#    Run AFTER robot_bringup.launch.py to build a map while teleoperating.
#
#  PREREQUISITES:
#    - robot_bringup.launch.py must be running
#    - /scan must be publishing  (verify: ros2 topic hz /scan)
#    - /odometry/filtered must be publishing
#    - TF chain odom→base_footprint→lidar_link must be complete
#
#  USAGE:
#    Terminal 1: ros2 launch mobile_robot robot_bringup.launch.py
#    Terminal 2: ros2 launch mobile_robot slam.launch.py
#    Terminal 3: ros2 run teleop_twist_keyboard teleop_twist_keyboard
#
#  MAP SAVING:
#    While SLAM is running, save the map at any time:
#      ros2 service call /slam_toolbox/save_map slam_toolbox/srv/SaveMap \
#        "{name: {data: '/path/to/maps/lab_map'}}"
#    Or use map_saver_cli:
#      ros2 run nav2_map_server map_saver_cli -f ~/maps/lab_map
#
#  HOW SLAM TOOLBOX BUILDS THE MAP:
#    1. Subscribes /scan (YDLIDAR X4 laser scans)
#    2. Reads TF: odom → base_footprint → base_link → lidar_link
#       (this tells SLAM where the robot is in the odom frame)
#    3. Projects each scan into the odom frame
#    4. Performs Karto SLAM scan-to-map matching to refine robot pose
#    5. Adds keyframes at regular distance/heading intervals
#    6. Performs loop closure detection against stored keyframes
#    7. Graph optimisation corrects accumulated drift on loop closure
#    8. Publishes /map [nav_msgs/OccupancyGrid] and map→odom TF correction
# ═══════════════════════════════════════════════════════════════════════════════

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg = get_package_share_directory('mobile_robot')

    slam_cfg = os.path.join(pkg, 'config', 'slam_toolbox.yaml')
    rviz_cfg = os.path.join(pkg, 'rviz',   'rviz_config.rviz')

    args = [
        DeclareLaunchArgument(
            'use_rviz', default_value='true',
            description='Open RViz with SLAM visualisation'
        ),
        DeclareLaunchArgument(
            'rviz_config', default_value=rviz_cfg,
            description='RViz config file'
        ),
        DeclareLaunchArgument(
            'slam_params_file', default_value=slam_cfg,
            description='Path to slam_toolbox parameter file'
        ),
    ]

    # ── SLAM Toolbox (async online mapping) ───────────────────────────────────
    # async_slam_toolbox_node: processes scans asynchronously to keep up with
    # real hardware without blocking the main control loop.
    slam_node = Node(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        parameters=[
            LaunchConfiguration('slam_params_file'),
            {'use_sim_time': False},
        ],
    )

    # ── RViz for SLAM monitoring ──────────────────────────────────────────────
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2_slam',
        arguments=['-d', LaunchConfiguration('rviz_config')],
        output='screen',
        condition=IfCondition(LaunchConfiguration('use_rviz')),
    )

    return LaunchDescription(
        args + [
            LogInfo(msg='━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'),
            LogInfo(msg='  AURA Rover — slam.launch.py'),
            LogInfo(msg='  Starting SLAM Toolbox (online async mapping)'),
            LogInfo(msg='  Ensure robot_bringup.launch.py is running!'),
            LogInfo(msg='  Drive robot to build map, then save:'),
            LogInfo(msg='    ros2 run nav2_map_server map_saver_cli -f ~/maps/lab_map'),
            LogInfo(msg='━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'),
            slam_node,
            rviz_node,
        ]
    )
