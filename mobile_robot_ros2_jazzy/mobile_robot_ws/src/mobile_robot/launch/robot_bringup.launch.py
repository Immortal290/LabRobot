#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
#  robot_bringup.launch.py  —  AURA Rover Hardware Bringup
#  ROS 2 Jazzy | Raspberry Pi 5 | Ubuntu 24.04
#
#  LAUNCHES:
#    ┌─────────────────────────────────────────────────────────────────────────┐
#    │  HARDWARE LAYER                                                         │
#    │    encoder_serial_node   → /wheel_ticks  (ENC packets from Arduino)    │
#    │    encoder_serial_node   ← /cmd_vel      (CMD packets to Arduino)       │
#    │    [IMU disabled — add MPU firmware to Arduino to re-enable]           │
#    │                                                                         │
#    │  PROCESSING LAYER                                                       │
#    │    wheel_odom_node       → /wheel_odom   (differential-drive odom)     │
#    │    ekf_filter_node       → /odometry/filtered (wheel-odom only)        │
#    │                                                                         │
#    │  SENSORS                                                                │
#    │    ydlidar_ros2_driver   → /scan                                        │
#    │    usb_cam               → /camera/image_raw                           │
#    │                                                                         │
#    │  ROBOT MODEL                                                            │
#    │    robot_state_publisher → /robot_description, TF static frames        │
#    │    joint_state_publisher → /joint_states                               │
#    │                                                                         │
#    │  VISUALISATION                                                          │
#    │    rviz2 (optional)                                                     │
#    └─────────────────────────────────────────────────────────────────────────┘
#
#  USAGE:
#    ros2 launch mobile_robot robot_bringup.launch.py
#    ros2 launch mobile_robot robot_bringup.launch.py serial_port:=/dev/ttyUSB0
#    ros2 launch mobile_robot robot_bringup.launch.py use_rviz:=false
#    ros2 launch mobile_robot robot_bringup.launch.py use_camera:=false
#
#  SERIAL PORT NOTES:
#    Arduino (CH340 chip)   → serial_port  (default /dev/ttyUSB0)
#    YDLIDAR  (CP2102 chip) → lidar_port   (default /dev/ttyUSB1)
#    Identify chips: udevadm info /dev/ttyUSB0 | grep ID_VENDOR_ID
#    Check with: ls /dev/ttyUSB*
#    Set permissions: sudo chmod 666 /dev/ttyUSB0 /dev/ttyUSB1
#
#  SLAM / MAP SAVING:
#    use_slam:=true   → slam_toolbox runs; map auto-saves every 30 s
#    use_slam:=false  → skip SLAM (pure hardware debug mode)
#    Manual save:  ros2 service call /slam_toolbox/save_map slam_toolbox/srv/SaveMap "{name: {data: 'my_map'}}"
# ═══════════════════════════════════════════════════════════════════════════════

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    LogInfo,
    TimerAction,
)
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, Command
from launch_ros.actions import Node


def generate_launch_description():
    pkg = get_package_share_directory('mobile_robot')

    # ── URDF / xacro processing ───────────────────────────────────────────────
    urdf_path = os.path.join(pkg, 'urdf', 'mobile_robot.urdf.xacro')

    # Use xacro to process the URDF
    from launch_ros.parameter_descriptions import ParameterValue
    robot_description_content = ParameterValue(Command(['xacro ', urdf_path]), value_type=str)

    # ── Declare launch arguments ──────────────────────────────────────────────
    args = [
        # Serial ports
        DeclareLaunchArgument(
            'serial_port', default_value='/dev/arduino',
            description='USB serial port for Arduino Nano — uses permanent symlink /dev/arduino'
        ),
        DeclareLaunchArgument(
            'serial_baud', default_value='115200',
            description='Baud rate for Arduino serial communication'
        ),
        DeclareLaunchArgument(
            'lidar_port', default_value='/dev/ydlidar',
            description='Serial port for YDLIDAR — uses permanent symlink /dev/ydlidar'
        ),

        # Robot geometry — must match physical measurements
        DeclareLaunchArgument(
            'wheel_radius', default_value='0.065',
            description='Wheel radius in metres (measure your actual wheel)'
        ),
        DeclareLaunchArgument(
            'wheel_separation', default_value='0.660',
            description='Wheel centre-to-centre distance in metres'
        ),
        DeclareLaunchArgument(
            'ticks_per_rev', default_value='1440.0',
            description='Encoder ticks per wheel revolution (measure this!)'
        ),

        # Visualisation
        DeclareLaunchArgument(
            'use_rviz', default_value='true',
            description='Launch RViz2 for visualisation'
        ),
        DeclareLaunchArgument(
            'rviz_config', default_value=os.path.join(pkg, 'rviz', 'slam_mapping.rviz'),
            description='RViz configuration file — defaults to SLAM mapping view'
        ),

        # Camera
        DeclareLaunchArgument(
            'use_camera', default_value='true',
            description='Launch USB camera node'
        ),
        DeclareLaunchArgument(
            'camera_device', default_value='/dev/video0',
            description='Camera device file'
        ),

        # SLAM mapping
        DeclareLaunchArgument(
            'use_slam', default_value='true',
            description='Run slam_toolbox for live mapping and auto-save'
        ),
        DeclareLaunchArgument(
            'slam_map_save_path', default_value='/home/lab/Desktop/AURA/mobile_robot_ros2_jazzy/mobile_robot_ws/src/mobile_robot/maps/aura_map',
            description='Absolute path prefix for the auto-saved map (no extension)'
        ),

        # NOTE: IMU disabled — add MPU firmware to Arduino then restore use_imu_filter arg
    ]

    # ── Config file paths ─────────────────────────────────────────────────────
    ekf_cfg  = os.path.join(pkg, 'config', 'ekf.yaml')
    slam_cfg = os.path.join(pkg, 'config', 'slam_toolbox_real.yaml')

    # ── 1. Robot State Publisher ──────────────────────────────────────────────
    # Reads URDF → publishes /robot_description and static TF frames
    rsp_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{
            'use_sim_time':       False,
            'robot_description':  robot_description_content,
        }],
    )

    # ── 2. Joint State Publisher ──────────────────────────────────────────────
    # Publishes /joint_states for the continuous wheel joints
    jsp_node = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher',
        name='joint_state_publisher',
        output='screen',
        parameters=[{'use_sim_time': False}],
    )

    # ── 3. Unified Hardware Serial Bridge (Encoder + Motors) ────────────────────
    # Reads ENC packets from Arduino → publishes /wheel_ticks
    # Converts /cmd_vel → CMD PWM packets → sends to Arduino
    # NOTE: IMU parsing disabled until MPU firmware is added to Arduino
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

    # ── 5. Wheel Odometry Node ─────────────────────────────────────────────────
    # /wheel_ticks → /wheel_odom (differential-drive kinematics)
    wheel_odom_node = Node(
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
            'publish_tf':       False,   # EKF publishes the authoritative TF
        }],
    )

    # ── 6. robot_localization EKF ─────────────────────────────────────────────
    # Fuses /wheel_odom → /odometry/filtered  (wheel-odom only, no IMU)
    # Also publishes odom → base_footprint TF
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

    # ── 8. YDLIDAR X2 ─────────────────────────────────────────────────────────
    # Publishes /scan [sensor_msgs/LaserScan]
    # Port: /dev/ttyUSB1 (CP2102 chip — confirmed by udevadm)
    # Arduino is on /dev/ttyUSB0 (CH340 chip)
    ydlidar_node = Node(
        package='ydlidar_ros2_driver',
        executable='ydlidar_ros2_driver_node',
        name='ydlidar_node',
        output='screen',
        parameters=[{
            'port':              LaunchConfiguration('lidar_port'),
            'baudrate':          115200,         # YDLIDAR X2 baudrate
            'frame_id':          'lidar_link',   # must match URDF lidar frame
            'ignore_array':      '',
            'frequency':         10.0,           # Hz
            'angle_min':         -180.0,
            'angle_max':          180.0,
            'range_min':          0.10,          # X2 min range
            'range_max':          12.0,          # X2 max range
            'isSingleChannel':    True,           # X2 is single-channel
            'support_motor_dtr':  True,           # X2 needs DTR to spin motor
            'intensity':          False,
            'lidar_type':         1,
            'device_type':        0,
            'sample_rate':        3,
            'auto_reconnect':     True,
        }],
    )

    # ── 9. USB Camera ─────────────────────────────────────────────────────────
    # Publishes /camera/image_raw + /camera/camera_info
    camera_node = Node(
        package='usb_cam',
        executable='usb_cam_node_exe',
        name='usb_cam',
        output='screen',
        parameters=[{
            'video_device':     LaunchConfiguration('camera_device'),
            'image_width':      640,
            'image_height':     480,
            'framerate':        30.0,
            'camera_frame_id':  'camera_optical_frame',
            'pixel_format':     'yuyv',
            'camera_name':      'camera',
        }],
        condition=IfCondition(LaunchConfiguration('use_camera')),
    )

    # ── 10. SLAM Toolbox (async mapping mode) ────────────────────────────────
    # Builds /map OccupancyGrid from /scan + TF (odom→base_footprint from EKF).
    # Auto-saves pose graph every map_update_interval seconds to maps/lab_map.*
    # Only launched when use_slam:=true (default).
    slam_node = Node(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        parameters=[slam_cfg, {'use_sim_time': False}],
        condition=IfCondition(LaunchConfiguration('use_slam')),
    )

    # ── 11. RViz2 ─────────────────────────────────────────────────────────────
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', LaunchConfiguration('rviz_config')],
        output='screen',
        condition=IfCondition(LaunchConfiguration('use_rviz')),
    )

    # ── Ordered launch ────────────────────────────────────────────────────────
    return LaunchDescription(
        args + [
            LogInfo(msg='━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'),
            LogInfo(msg='  AURA Rover — robot_bringup.launch.py'),
            LogInfo(msg='  Starting hardware nodes...'),
            LogInfo(msg='━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'),

            # Immediately: robot description + serial hardware
            rsp_node,
            jsp_node,
            hardware_bridge,

            # After 1s: wheel odom
            TimerAction(period=1.0, actions=[wheel_odom_node]),

            # After 2s: EKF (wheel-odom only)
            TimerAction(period=2.0, actions=[ekf_node]),

            # After 1s: LIDAR
            TimerAction(period=1.0, actions=[ydlidar_node]),

            # After 1s: camera
            TimerAction(period=1.0, actions=[camera_node]),

            # After 4s: SLAM Toolbox (needs EKF odom TF + /scan to be live)
            # Builds /map and auto-saves pose graph every 5 s while driving.
            TimerAction(period=4.0, actions=[slam_node]),

            # After 5s: RViz (wait for /map to appear)
            TimerAction(period=5.0, actions=[rviz_node]),

            LogInfo(msg='[AURA] robot_bringup started. Monitor: ros2 topic hz /scan /map'),
            LogInfo(msg='[AURA] Map saves to: maps/lab_map.posegraph (every 5 s)'),
            LogInfo(msg='[AURA] Final save: ros2 service call /slam_toolbox/save_map slam_toolbox/srv/SaveMap "{name: {data: \'lab_map\'}}"'),
        ]
    )
