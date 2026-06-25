#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════
#  real_robot_nav.launch.py — ROS 2 Jazzy
#  Full real-hardware navigation launch:
#
#  ┌─────────────────────────────────────────────────────────────────────┐
#  │  Arduino/ESP32 ──USB──► encoder_serial_bridge  → /wheel_ticks      │
#  │                          imu_serial_node        → /imu/data_raw    │
#  │                          imu_filter_madgwick    → /imu/data        │
#  │                          wheel_odom_node        → /wheel_odom      │
#  │                          ekf_filter_node        → /odometry/filtered│
#  │                          YDLIDAR                → /scan            │
#  │                          SLAM Toolbox           → /map             │
#  │                          Nav2                   → /cmd_vel         │
#  │                          robot_state_publisher  → TF static frames │
#  └─────────────────────────────────────────────────────────────────────┘
#
#  TF Tree:
#    map → odom → base_footprint → base_link → {laser_frame, imu_link, ...}
#
#  Usage:
#    ros2 launch mobile_robot real_robot_nav.launch.py
#    ros2 launch mobile_robot real_robot_nav.launch.py \
#        serial_port:=/dev/ttyUSB0 \
#        imu_serial_port:=/dev/ttyUSB0 \
#        use_slam:=true \
#        map_yaml:=""
# ═══════════════════════════════════════════════════════════════════════════

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    GroupAction,
    IncludeLaunchDescription,
    LogInfo,
    OpaqueFunction,
    TimerAction,
)
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    LaunchConfiguration,
    PathJoinSubstitution,
    PythonExpression,
)
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    pkg = get_package_share_directory('mobile_robot')

    # ── Launch arguments ──────────────────────────────────────────────────
    args = [
        DeclareLaunchArgument('serial_port',     default_value='/dev/ttyUSB1',
                              description='Serial port for Arduino Nano (encoder + motors)'),
        DeclareLaunchArgument('lidar_port',      default_value='/dev/ttyUSB0',
                              description='Serial port for YDLIDAR'),
        DeclareLaunchArgument('serial_baud',     default_value='115200'),
        DeclareLaunchArgument('wheel_radius',    default_value='0.065'),
        DeclareLaunchArgument('wheel_separation', default_value='0.660'),
        DeclareLaunchArgument('ticks_per_rev',   default_value='1440.0'),
        DeclareLaunchArgument('use_slam',        default_value='true',
                              description='true=SLAM mapping, false=localisation with existing map'),
        DeclareLaunchArgument('map_yaml',        default_value='',
                              description='Path to map YAML for localisation mode'),
        DeclareLaunchArgument('use_imu',         default_value='false',
                              description='Enable IMU madgwick filter (requires IMU firmware)'),
        DeclareLaunchArgument('use_rviz',        default_value='true'),
        DeclareLaunchArgument('rviz_config',     default_value=os.path.join(pkg, 'rviz', 'slam_nav.rviz')),
    ]

    # ── Configs ───────────────────────────────────────────────────────────
    ekf_cfg      = os.path.join(pkg, 'config', 'ekf.yaml')
    slam_cfg     = os.path.join(pkg, 'config', 'slam_toolbox_real.yaml')
    nav2_cfg     = os.path.join(pkg, 'config', 'nav2_params_real.yaml')
    robot_urdf   = os.path.join(pkg, 'urdf', 'mobile_robot.urdf.xacro')

    # Use xacro to process the URDF dynamically if xacro is used, or fallback to file reading
    # Since robot_urdf is xacro, open().read() will read raw xacro which might cause issues
    # Let's process it via xacro command to be completely correct.
    from launch.substitutions import Command
    from launch_ros.parameter_descriptions import ParameterValue
    robot_description_content = ParameterValue(Command(['xacro ', robot_urdf]), value_type=str)

    # ── Robot State Publisher ─────────────────────────────────────────────
    rsp_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{
            'use_sim_time': False,
            'robot_description': robot_description_content,
        }],
    )

    # ── Unified Hardware Serial Bridge (Encoder + Motors) ──────────────────
    hardware_bridge = Node(
        package='mobile_robot',
        executable='encoder_serial_node.py',
        name='hardware_serial_bridge',
        output='screen',
        parameters=[{
            'serial_port':    LaunchConfiguration('serial_port'),
            'serial_baud':    LaunchConfiguration('serial_baud'),
            'wheel_base':     LaunchConfiguration('wheel_separation'),
            'max_linear_vel': 0.5,
            'max_pwm':        200,
        }],
    )

    # ── IMU Filter (Madgwick) — only run if use_imu is True ────────────────
    imu_filter = Node(
        package='imu_filter_madgwick',
        executable='imu_filter_madgwick_node',
        name='imu_filter_madgwick',
        output='screen',
        parameters=[{
            'use_sim_time':         False,
            'use_mag':              True,
            'publish_tf':           False,
            'world_frame':          'enu',
            'gain':                 0.1,
            'zeta':                 0.0,
            'mag_bias_x':           0.0,
            'mag_bias_y':           0.0,
            'mag_bias_z':           0.0,
            'orientation_stddev':   0.05,
            'angular_velocity_stddev': 0.005,
            'linear_acceleration_stddev': 0.05,
        }],
        remappings=[
            ('imu/data_raw', '/imu/data_raw'),
            ('imu/mag',      '/imu/mag'),
            ('imu/data',     '/imu/data'),
        ],
        condition=IfCondition(LaunchConfiguration('use_imu')),
    )

    # ── Wheel Odometry Node ────────────────────────────────────────────────
    wheel_odom = Node(
        package='mobile_robot',
        executable='wheel_odom_node.py',
        name='wheel_odom_node',
        output='screen',
        parameters=[{
            'wheel_radius':     LaunchConfiguration('wheel_radius'),
            'wheel_separation': LaunchConfiguration('wheel_separation'),
            'ticks_per_rev':    LaunchConfiguration('ticks_per_rev'),
            'odom_frame':       'odom',
            'base_frame':       'base_footprint',
            'publish_tf':       False,   # EKF publishes authoritative TF
        }],
    )

    # ── robot_localization EKF ────────────────────────────────────────────
    ekf_node = Node(
        package='robot_localization',
        executable='ekf_node',
        name='ekf_filter_node',
        output='screen',
        parameters=[ekf_cfg, {'use_sim_time': False}],
        remappings=[
            ('odometry/filtered', '/odometry/filtered'),
        ],
    )

    # ── YDLIDAR X2 ───────────────────────────────────────────────────────────
    ydlidar_node = Node(
        package='ydlidar_ros2_driver',
        executable='ydlidar_ros2_driver_node',
        name='ydlidar_node',
        output='screen',
        parameters=[{
            'port':              LaunchConfiguration('lidar_port'),
            'baudrate':          115200,         # YDLIDAR X2 baudrate
            'frame_id':          'lidar_link',   # must match URDF frame name
            'ignore_array':      '',
            'frequency':         10.0,
            'angle_min':         -180.0,
            'angle_max':          180.0,
            'range_min':          0.10,
            'range_max':          12.0,
            'isSingleChannel':    True,
            'support_motor_dtr':  True,
            'intensity':          False,
            'lidar_type':         1,
            'device_type':        0,
            'sample_rate':        3,
            'auto_reconnect':     True,
        }],
    )

    # ── SLAM Toolbox (mapping mode) ───────────────────────────────────────
    slam_node = Node(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        parameters=[slam_cfg, {'use_sim_time': False}],
        condition=IfCondition(LaunchConfiguration('use_slam')),
    )

    # ── Nav2 (bringup) ────────────────────────────────────────────────────
    nav2_bringup_dir = FindPackageShare('nav2_bringup')
    nav2_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            PathJoinSubstitution([nav2_bringup_dir, 'launch', 'navigation_launch.py'])
        ]),
        launch_arguments={
            'use_sim_time': 'false',
            'params_file':  nav2_cfg,
            'autostart':    'true',
        }.items(),
    )

    # ── RViz ─────────────────────────────────────────────────────────────
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', LaunchConfiguration('rviz_config')],
        output='screen',
        condition=IfCondition(LaunchConfiguration('use_rviz')),
    )

    # ── Ordered startup (delay Nav2 until sensors are up) ─────────────────
    return LaunchDescription(
        args + [
            LogInfo(msg='[AURA] Starting real robot navigation stack'),
            rsp_node,
            hardware_bridge,
            imu_filter,
            wheel_odom,
            ekf_node,
            ydlidar_node,
            TimerAction(period=3.0, actions=[slam_node]),
            TimerAction(period=5.0, actions=[nav2_launch]),
            TimerAction(period=6.0, actions=[rviz_node]),
        ]
    )
