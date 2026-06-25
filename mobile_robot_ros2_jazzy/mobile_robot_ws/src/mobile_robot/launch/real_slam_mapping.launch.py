#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════
#  real_slam_mapping.launch.py  —  AURA Real-Hardware SLAM Mapping
#  ROS 2 Jazzy | Raspberry Pi 5 | YDLIDAR X2
#
#  PURPOSE:
#    Dedicated mapping-only launch for Phase 1 of the 2-phase workflow:
#
#    PHASE 1 (this file) — Mapping:
#      1. Bring up all hardware (encoders, motors, LiDAR)
#      2. Start EKF odometry fusion
#      3. Run SLAM Toolbox → builds /map in real-time as you drive
#      4. Map auto-saves to maps/lab_map.* every 5 seconds
#      5. Call save_map service when done to export .pgm + .yaml
#
#    PHASE 2 — Autonomous Navigation (after mapping):
#      ros2 launch mobile_robot real_robot_nav.launch.py \
#          use_slam:=false \
#          map_yaml:=/home/lab/Desktop/AURA/.../maps/lab_map.yaml
#
#  USAGE:
#    # Default (all hardware on standard ports):
#    ros2 launch mobile_robot real_slam_mapping.launch.py
#
#    # Custom ports:
#    ros2 launch mobile_robot real_slam_mapping.launch.py \
#        serial_port:=/dev/ttyUSB0 lidar_port:=/dev/ttyUSB1
#
#    # No RViz (headless Raspberry Pi):
#    ros2 launch mobile_robot real_slam_mapping.launch.py use_rviz:=false
#
#  TELEOP (in a second terminal while this is running):
#    ros2 run teleop_twist_keyboard teleop_twist_keyboard \
#        --ros-args -r /cmd_vel:=/cmd_vel
#
#  SAVE FINAL MAP (in a third terminal when mapping is complete):
#    ros2 service call /slam_toolbox/save_map \
#        slam_toolbox/srv/SaveMap \
#        "{name: {data: '/home/lab/Desktop/AURA/mobile_robot_ros2_jazzy/mobile_robot_ws/src/mobile_robot/maps/lab_map'}}"
#
#  MONITOR:
#    ros2 topic hz /map          # map update rate (~0.2 Hz)
#    ros2 topic hz /scan         # LiDAR rate (~10 Hz)
#    ros2 topic hz /odometry/filtered  # EKF rate (~20 Hz)
#    ros2 run tf2_tools view_frames    # verify TF tree
#
#  TF TREE (required for SLAM to work):
#    map → odom → base_footprint → base_link → lidar_link
#          ↑                ↑
#      (SLAM Toolbox)   (EKF node)
#
#  SERIAL PORT IDENTIFICATION:
#    Arduino  (CH340)  → typically /dev/ttyUSB0
#    YDLIDAR  (CP2102) → typically /dev/ttyUSB1
#    Verify: udevadm info /dev/ttyUSBx | grep ID_VENDOR_ID
# ═══════════════════════════════════════════════════════════════════════════

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    LogInfo,
    TimerAction,
    EmitEvent,
    RegisterEventHandler,
)
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, Command
from launch_ros.actions import Node, LifecycleNode
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.event_handlers import OnStateTransition
from launch_ros.events.lifecycle import ChangeState
from lifecycle_msgs.msg import Transition
from launch.events import matches_action


def generate_launch_description():
    pkg = get_package_share_directory('mobile_robot')

    # ── Config paths ──────────────────────────────────────────────────────
    ekf_cfg  = os.path.join(pkg, 'config', 'ekf.yaml')
    slam_cfg = os.path.join(pkg, 'config', 'slam_toolbox_real.yaml')
    rviz_cfg = os.path.join(pkg, 'rviz',   'slam_mapping.rviz')

    # ── URDF ──────────────────────────────────────────────────────────────
    urdf_path = os.path.join(pkg, 'urdf', 'mobile_robot.urdf.xacro')
    robot_description = ParameterValue(
        Command(['xacro ', urdf_path]), value_type=str
    )

    # ── Launch arguments ──────────────────────────────────────────────────
    args = [
        DeclareLaunchArgument(
            'serial_port', default_value='/dev/arduino',
            description='Serial port for Arduino (encoders + motors)'),
        DeclareLaunchArgument(
            'serial_baud', default_value='115200',
            description='Baud rate for Arduino'),
        DeclareLaunchArgument(
            'lidar_port', default_value='/dev/ydlidar',
            description='Serial port for YDLIDAR X2 — uses permanent symlink /dev/ydlidar'),
        DeclareLaunchArgument(
            'wheel_radius', default_value='0.065',
            description='Wheel radius in metres'),
        DeclareLaunchArgument(
            'wheel_separation', default_value='0.660',
            description='Wheel centre-to-centre distance in metres'),
        DeclareLaunchArgument(
            'ticks_per_rev', default_value='1440.0',
            description='Encoder ticks per wheel revolution'),
        DeclareLaunchArgument(
            'use_rviz', default_value='true',
            description='Launch RViz2 for live map visualization'),
        DeclareLaunchArgument(
            'rviz_config', default_value=rviz_cfg,
            description='RViz config file'),
    ]

    # ══════════════════════════════════════════════════════════════════════
    #  NODE DEFINITIONS — ordered by startup dependency
    # ══════════════════════════════════════════════════════════════════════

    # ── 1. Robot State Publisher ──────────────────────────────────────────
    # Publishes URDF TF tree: base_footprint → base_link → lidar_link, wheels
    rsp_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{
            'use_sim_time':      False,
            'robot_description': robot_description,
            'publish_frequency': 50.0,
        }],
    )

    # ── 2. Joint State Publisher ──────────────────────────────────────────
    # Publishes wheel joint states so URDF visualization works in RViz
    jsp_node = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher',
        name='joint_state_publisher',
        output='screen',
        parameters=[{'use_sim_time': False}],
    )

    # ── 3. Hardware Serial Bridge (Encoder + Motor) ───────────────────────
    # Reads ENC packets from Arduino → publishes /wheel_ticks
    # Converts /cmd_vel → CMD PWM packets → sends to Arduino
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

    # ── 4. Wheel Odometry Node ────────────────────────────────────────────
    # /wheel_ticks → /wheel_odom  (differential drive kinematics)
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

    # ── 5. EKF Odometry Filter ────────────────────────────────────────────
    # Fuses /wheel_odom → /odometry/filtered
    # Also publishes the authoritative odom → base_footprint TF
    # SLAM Toolbox uses this TF to localize each incoming scan.
    ekf_node = Node(
        package='robot_localization',
        executable='ekf_node',
        name='ekf_filter_node',
        output='screen',
        parameters=[ekf_cfg, {'use_sim_time': False}],
        remappings=[('odometry/filtered', '/odometry/filtered')],
    )

    # ── 6. YDLIDAR X2 ─────────────────────────────────────────────────────
    # Publishes /scan [sensor_msgs/LaserScan] at ~10 Hz
    # SLAM Toolbox reads /scan to build the occupancy grid map.
    ydlidar_node = Node(
        package='ydlidar_ros2_driver',
        executable='ydlidar_ros2_driver_node',
        name='ydlidar_node',
        output='screen',
        parameters=[{
            'port':             LaunchConfiguration('lidar_port'),
            'baudrate':         115200,
            'frame_id':         'lidar_link',   # must match URDF frame
            'ignore_array':     '',
            'frequency':        10.0,
            'angle_min':        -180.0,
            'angle_max':         180.0,
            'range_min':          0.10,
            'range_max':         12.0,
            'isSingleChannel':   True,    # YDLIDAR X2 is single-channel
            'support_motor_dtr': True,    # X2 needs DTR signal to spin motor
            'intensity':         False,
            'lidar_type':        1,
            'device_type':       0,
            'sample_rate':       3,
            'auto_reconnect':    True,
        }],
    )

    # ── 7. SLAM Toolbox (async mapping) ───────────────────────────────────
    # Subscribes: /scan  (LaserScan)
    # Uses TF:    odom → base_footprint  (from EKF above)
    # Publishes:  /map  (OccupancyGrid) — live map built as robot explores
    #             /slam_toolbox/pose_graph  (MarkerArray) — pose graph viz
    #
    # AUTO-SAVE: every map_update_interval seconds the pose graph is
    # serialized to:
    slam_node = LifecycleNode(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        parameters=[slam_cfg, {'use_sim_time': False}],
        namespace=''
    )

    configure_event = EmitEvent(
        event=ChangeState(
            lifecycle_node_matcher=matches_action(slam_node),
            transition_id=Transition.TRANSITION_CONFIGURE
        )
    )

    activate_event = RegisterEventHandler(
        OnStateTransition(
            target_lifecycle_node=slam_node,
            start_state="configuring",
            goal_state="inactive",
            entities=[
                LogInfo(msg="[LifecycleLaunch] Slamtoolbox node is activating."),
                EmitEvent(event=ChangeState(
                    lifecycle_node_matcher=matches_action(slam_node),
                    transition_id=Transition.TRANSITION_ACTIVATE
                ))
            ]
        )
    )

    # ── 8. RViz2 ──────────────────────────────────────────────────────────
    # Shows: robot model, /scan laser beams, /map occupancy grid,
    #        TF axes, pose graph nodes
    # Delayed 6 s to let SLAM produce the first /map update before opening.
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', LaunchConfiguration('rviz_config')],
        parameters=[{'use_sim_time': False}],
        condition=IfCondition(LaunchConfiguration('use_rviz')),
    )

    # ══════════════════════════════════════════════════════════════════════
    #  ORDERED STARTUP
    #  Delays are staggered so each node has its dependencies ready:
    #    t=0s  RSP + JSP + hardware bridge  (base TF + serial link)
    #    t=1s  wheel_odom_node             (needs serial data)
    #    t=2s  EKF                          (needs /wheel_odom)
    #    t=2s  YDLIDAR                      (independent, start early)
    #    t=5s  SLAM Toolbox                 (needs EKF TF + /scan)
    #    t=6s  RViz2                        (needs /map to show map)
    # ══════════════════════════════════════════════════════════════════════
    return LaunchDescription(
        args + [
            LogInfo(msg='═══════════════════════════════════════════════════'),
            LogInfo(msg='  AURA — real_slam_mapping.launch.py'),
            LogInfo(msg='  PHASE 1: Real-Time SLAM Mapping'),
            LogInfo(msg='  Drive the robot with teleop to explore the lab.'),
            LogInfo(msg='  Map auto-saves every 5 s → maps/lab_map.*'),
            LogInfo(msg='═══════════════════════════════════════════════════'),

            # t=0s: RSP, JSP, hardware bridge
            rsp_node,
            jsp_node,
            hardware_bridge,

            # t=1s: wheel odometry (needs ENC packets from Arduino)
            TimerAction(period=1.0, actions=[wheel_odom_node]),

            # t=2s: EKF (needs /wheel_odom)
            TimerAction(period=2.0, actions=[ekf_node]),

            # t=3s: YDLIDAR — extra 1s delay lets the motor physically spin up
            # before the driver starts checking for data (prevents timeout crash)
            TimerAction(period=3.0, actions=[ydlidar_node]),

            # t=5s: SLAM Toolbox — needs both EKF TF and /scan to be live
            # We trigger the lifecycle transitions configure and activate here.
            TimerAction(period=5.0, actions=[
                slam_node,
                configure_event,
                activate_event
            ]),

            # t=6s: RViz — wait for first /map update
            TimerAction(period=6.0, actions=[rviz_node]),

            LogInfo(msg='[AURA] Stack started. In a NEW terminal run:'),
            LogInfo(msg='[AURA] Stack started. In a NEW terminal run:'),
            LogInfo(msg='  ros2 run teleop_twist_keyboard teleop_twist_keyboard'),
            LogInfo(msg='[AURA] Monitor map: ros2 topic hz /map'),
            LogInfo(msg='[AURA] Save final map (in new terminal):'),
            LogInfo(msg='  ros2 service call /slam_toolbox/save_map slam_toolbox/srv/SaveMap'),
            LogInfo(msg='  arg: "{name: {data: lab_map}}"'),
        ]
    )
