#!/usr/bin/env python3
"""
real_slam_mapping.launch.py
────────────────────────────────────────────────────────────────────────────
No-IMU mapping pipeline for AURA mobile robot.

    YDLIDAR X2  ──/scan_raw──►  laser_filters  ──/scan──┬──► rf2o_laser_odometry ──/rf2o_odom──┐
                                                          │                                      │
                                                          └──────────────────► slam_toolbox      │
                                                                                     ▲            │
                        /wheel_odom ─────────────────────────────────────────────►  EKF  ◄────────┘
                                                                                     │
                                                                          odom -> base_footprint TF

PREREQUISITES (from your existing robot bringup — NOT started by this file):
  - robot_state_publisher / URDF publishing base_footprint -> laser static TF
  - Your diff-drive controller / wheel odometry node publishing /wheel_odom
  - YDLIDAR ROS2 driver publishing raw scans

    This launch file assumes your existing bringup publishes raw scans on
    /scan_raw. If your YDLIDAR driver currently publishes directly to /scan,
    either remap its output to /scan_raw in your existing bringup launch, or
    edit the remapping in the `laser_filter_node` action below.

USAGE:
    ros2 launch mobile_robot_mapping real_slam_mapping.launch.py

    # then drive the robot slowly with teleop, loop back through mapped
    # areas periodically, and when done:
    ros2 service call /slam_toolbox/save_map \\
        slam_toolbox/srv/SaveMap "{name: {data: 'lab_map'}}"
────────────────────────────────────────────────────────────────────────────
"""

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.substitutions import LaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    pkg_share = get_package_share_directory('mobile_robot_mapping')

    ekf_yaml = os.path.join(pkg_share, 'config', 'ekf.yaml')
    slam_yaml = os.path.join(pkg_share, 'config', 'slam_toolbox_real.yaml')
    laser_filter_yaml = os.path.join(pkg_share, 'config', 'laser_filter.yaml')
    rf2o_yaml = os.path.join(pkg_share, 'config', 'rf2o_params.yaml')
    rviz_config = os.path.join(pkg_share, 'rviz', 'mapping.rviz')

    use_sim_time = LaunchConfiguration('use_sim_time', default='false')
    start_rviz = LaunchConfiguration('start_rviz', default='true')

    declare_use_sim_time = DeclareLaunchArgument(
        'use_sim_time', default_value='false',
        description='Use simulation clock (false for real hardware)')

    declare_start_rviz = DeclareLaunchArgument(
        'start_rviz', default_value='true',
        description='Whether to launch RViz alongside the mapping stack')

    # ── 1. Laser filter chain: /scan_raw -> /scan ───────────────────────────
    laser_filter_node = Node(
        package='laser_filters',
        executable='scan_to_scan_filter_chain',
        name='scan_filter_chain',
        output='screen',
        parameters=[laser_filter_yaml],
        remappings=[
            ('scan', '/scan_raw'),
            ('scan_filtered', '/scan'),
        ],
    )

    # ── 2. rf2o LIDAR odometry: /scan -> /rf2o_odom ─────────────────────────
    rf2o_node = Node(
        package='rf2o_laser_odometry',
        executable='rf2o_laser_odometry_node',
        name='rf2o_laser_odometry',
        output='screen',
        parameters=[rf2o_yaml],
    )

    # ── 3. EKF: fuses /wheel_odom (translation) + /rf2o_odom (yaw) ──────────
    ekf_node = Node(
        package='robot_localization',
        executable='ekf_node',
        name='ekf_filter_node',
        output='screen',
        parameters=[ekf_yaml, {'use_sim_time': use_sim_time}],
    )

    # ── 4. slam_toolbox — online async mapping ──────────────────────────────
    slam_toolbox_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory('slam_toolbox'),
                'launch',
                'online_async_launch.py'
            )
        ),
        launch_arguments={
            'slam_params_file': slam_yaml,
            'use_sim_time': use_sim_time,
        }.items(),
    )

    from launch.conditions import IfCondition

    # ── 5. RViz (optional) ───────────────────────────────────────────────────
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', rviz_config],
        condition=IfCondition(start_rviz),
    )

    return LaunchDescription([
        declare_use_sim_time,
        declare_start_rviz,
        laser_filter_node,
        rf2o_node,
        ekf_node,
        slam_toolbox_launch,
        rviz_node,
    ])
