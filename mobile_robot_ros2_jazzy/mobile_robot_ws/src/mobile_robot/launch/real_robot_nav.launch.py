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
    EmitEvent,
    RegisterEventHandler,
)
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    LaunchConfiguration,
    PathJoinSubstitution,
    PythonExpression,
)
from launch_ros.actions import Node, LifecycleNode
from launch_ros.substitutions import FindPackageShare
from launch_ros.event_handlers import OnStateTransition
from launch_ros.events.lifecycle import ChangeState
from lifecycle_msgs.msg import Transition
from launch.events import matches_action


def generate_launch_description():
    pkg = get_package_share_directory('mobile_robot')

    # ── Launch arguments ──────────────────────────────────────────────────
    args = [
        DeclareLaunchArgument('serial_port',      default_value='/dev/arduino',
                              description='Serial port for Arduino Nano — uses permanent symlink /dev/arduino'),
        DeclareLaunchArgument('lidar_port',       default_value='/dev/ydlidar',
                              description='Serial port for YDLIDAR — uses permanent symlink /dev/ydlidar'),
        DeclareLaunchArgument('serial_baud',     default_value='115200'),
        DeclareLaunchArgument('wheel_radius',    default_value='0.065'),
        DeclareLaunchArgument('wheel_separation', default_value='0.660'),
        DeclareLaunchArgument('ticks_per_rev',   default_value='720.0'),
        DeclareLaunchArgument('ticks_scale',     default_value='1.0',
                              description='Scaling factor for wheel ticks to calibrate slip/gear-ratio'),
        DeclareLaunchArgument('min_pwm',         default_value='60',
                              description='Minimum PWM deadband for heavy wheels'),
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
    rf2o_cfg     = os.path.join(pkg, 'config', 'rf2o_params.yaml')
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

    # ── Joint State Publisher ─────────────────────────────────────────────
    jsp_node = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher',
        name='joint_state_publisher',
        parameters=[{'use_sim_time': False}],
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
            'min_pwm':        LaunchConfiguration('min_pwm'),
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
            'use_mag':              False,
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
            'ticks_scale':      LaunchConfiguration('ticks_scale'),
            'odom_frame':       'odom',
            'base_frame':       'base_footprint',
            'publish_tf':       False,   # EKF publishes authoritative TF
        }],
    )

    # ── rf2o LIDAR odometry ───────────────────────────────────────────────
    rf2o_node = Node(
        package='rf2o_laser_odometry',
        executable='rf2o_laser_odometry_node',
        name='rf2o_laser_odometry',
        output='screen',
        parameters=[rf2o_cfg],
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

    # ── YDLIDAR X2 ──────────────────────────────────────────────────────────
    # NOTE: "Fail to get baseplate device information!" is a known, non-fatal
    # SDK warning for YDLIDAR X2. The X2 does not support the extended device
    # info query; the lidar still starts and scans correctly.
    ydlidar_node = Node(
        package='ydlidar_ros2_driver',
        executable='ydlidar_ros2_driver_node',
        name='ydlidar_node',
        output='screen',
        parameters=[{
            'port':               LaunchConfiguration('lidar_port'),
            'baudrate':           115200,        # YDLIDAR X2: 115200 baud
            'frame_id':           'lidar_link',  # must match URDF frame name
            'ignore_array':       '',
            'frequency':          10.0,
            'angle_min':          -180.0,
            'angle_max':           180.0,
            'range_min':           0.12,         # X2 minimum range (m)
            'range_max':           10.0,         # X2 maximum range (m)
            'isSingleChannel':     True,         # X2 uses single-channel protocol
            'support_motor_dtr':   True,         # X2 uses DTR to control motor
            'resolution_fixed':    False,        # X2 single-ch: let SDK auto-detect
            'intensity':           False,        # X2 does not output intensity
            'invalid_range_is_inf': False,       # out-of-range returns 0, not inf
            'lidar_type':          1,            # triangle lidar type
            'device_type':         0,            # serial device
            'sample_rate':         3,            # X2: 3K samples/s
            'abnormal_check_count': 4,
            'auto_reconnect':      True,
        }],
    )

    # ── SLAM Toolbox (mapping mode) ─────────────────────────────────────
    # The YDLIDAR driver publishes /scan with BEST_EFFORT reliability.
    # slam_toolbox defaults to RELIABLE, causing a QoS incompatibility that
    # silently drops ALL scan messages. The qos_overrides parameter below
    # tells slam_toolbox to subscribe to /scan with BEST_EFFORT instead.
    slam_node = LifecycleNode(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        parameters=[
            slam_cfg,
            {'use_sim_time': False},
            # QoS fix: match YDLIDAR BEST_EFFORT publisher on /scan
            {'qos_overrides./scan.subscription.reliability': 'best_effort'},
        ],
        namespace='',
        condition=IfCondition(LaunchConfiguration('use_slam')),
    )

    configure_event = EmitEvent(
        event=ChangeState(
            lifecycle_node_matcher=matches_action(slam_node),
            transition_id=Transition.TRANSITION_CONFIGURE
        ),
        condition=IfCondition(LaunchConfiguration('use_slam')),
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
        ),
        condition=IfCondition(LaunchConfiguration('use_slam')),
    )

    # ── Map Server & AMCL (localization mode) ─────────────────────────────
    map_server = Node(
        package='nav2_map_server',
        executable='map_server',
        name='map_server',
        output='screen',
        parameters=[{'yaml_filename': LaunchConfiguration('map_yaml'), 'use_sim_time': False}],
        condition=UnlessCondition(LaunchConfiguration('use_slam')),
    )

    amcl = Node(
        package='nav2_amcl',
        executable='amcl',
        name='amcl',
        output='screen',
        parameters=[nav2_cfg, {'use_sim_time': False}],
        condition=UnlessCondition(LaunchConfiguration('use_slam')),
    )

    lifecycle_manager_localization = Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        name='lifecycle_manager_localization',
        output='screen',
        parameters=[{
            'use_sim_time': False,
            'autostart': True,
            'node_names': ['map_server', 'amcl']
        }],
        condition=UnlessCondition(LaunchConfiguration('use_slam')),
    )

    # ── Nav2 Nodes (Jazzy customization) ──────────────────────────────────
    remappings = [('/tf', 'tf'), ('/tf_static', 'tf_static')]

    controller_server = Node(
        package='nav2_controller',
        executable='controller_server',
        name='controller_server',
        output='screen',
        parameters=[nav2_cfg],
        remappings=remappings + [('cmd_vel', 'cmd_vel_nav')],
    )

    smoother_server = Node(
        package='nav2_smoother',
        executable='smoother_server',
        name='smoother_server',
        output='screen',
        parameters=[nav2_cfg],
        remappings=remappings,
    )

    planner_server = Node(
        package='nav2_planner',
        executable='planner_server',
        name='planner_server',
        output='screen',
        parameters=[nav2_cfg],
        remappings=remappings,
    )

    behavior_server = Node(
        package='nav2_behaviors',
        executable='behavior_server',
        name='behavior_server',
        output='screen',
        parameters=[nav2_cfg],
        remappings=remappings + [('cmd_vel', 'cmd_vel_nav')],
    )

    bt_navigator = Node(
        package='nav2_bt_navigator',
        executable='bt_navigator',
        name='bt_navigator',
        output='screen',
        parameters=[nav2_cfg],
        remappings=remappings,
    )

    waypoint_follower = Node(
        package='nav2_waypoint_follower',
        executable='waypoint_follower',
        name='waypoint_follower',
        output='screen',
        parameters=[nav2_cfg],
        remappings=remappings,
    )

    velocity_smoother = Node(
        package='nav2_velocity_smoother',
        executable='velocity_smoother',
        name='velocity_smoother',
        output='screen',
        parameters=[nav2_cfg],
        remappings=remappings + [('cmd_vel', 'cmd_vel_nav')],
    )

    lifecycle_manager_navigation = Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        name='lifecycle_manager_navigation',
        output='screen',
        parameters=[{
            'use_sim_time': False,
            'autostart': True,
            'node_names': [
                'controller_server',
                'smoother_server',
                'planner_server',
                'behavior_server',
                'bt_navigator',
                'waypoint_follower',
                'velocity_smoother'
            ]
        }],
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
            jsp_node,
            hardware_bridge,
            imu_filter,
            wheel_odom,
            rf2o_node,
            ekf_node,
            ydlidar_node,

            # t=3s: Start localization source (either SLAM or AMCL)
            TimerAction(period=3.0, actions=[
                slam_node,
                configure_event,
                activate_event,
                map_server,
                amcl,
                lifecycle_manager_localization,
            ]),

            # t=5s: Start Nav2
            TimerAction(period=5.0, actions=[
                controller_server,
                smoother_server,
                planner_server,
                behavior_server,
                bt_navigator,
                waypoint_follower,
                velocity_smoother,
                lifecycle_manager_navigation,
            ]),

            # t=6s: Start RViz
            TimerAction(period=6.0, actions=[rviz_node]),
        ]
    )
