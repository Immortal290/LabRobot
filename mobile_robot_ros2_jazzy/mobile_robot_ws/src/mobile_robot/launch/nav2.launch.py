#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
#  nav2.launch.py  —  Nav2 Autonomous Navigation Launch
#  ROS 2 Jazzy | AURA Rover
#
#  PURPOSE:
#    Launches the Nav2 stack for autonomous navigation using a pre-built map.
#    Run AFTER robot_bringup.launch.py (which provides sensors + odometry).
#
#  PREREQUISITES:
#    - robot_bringup.launch.py must be running
#    - A saved map (.yaml + .pgm) must exist (created by slam.launch.py)
#    - Set map_yaml argument to point to your saved map file
#
#  USAGE:
#    Terminal 1: ros2 launch mobile_robot robot_bringup.launch.py
#    Terminal 2: ros2 launch mobile_robot nav2.launch.py \
#                  map_yaml:=/home/pi/maps/lab_map.yaml
#
#  HOW NAV2 USES THE MAP:
#    1. map_server loads lab_map.yaml → publishes /map (static occupancy grid)
#    2. amcl (if enabled) localises robot within that map using /scan
#       OR: SLAM Toolbox in localisation mode provides pose (no amcl needed)
#    3. You set a Goal Pose in RViz → bt_navigator receives NavigateToPose goal
#    4. planner_server (NavFn/Dijkstra) plans global path on global_costmap
#    5. controller_server (DWB) generates velocity commands to follow path
#    6. Local costmap adds real-time /scan data for dynamic obstacle avoidance
#    7. behavior_server recovers (spin/backup) if robot gets stuck
#    8. velocity_smoother smooths commands before publishing /cmd_vel
#    9. /cmd_vel → encoder_serial_node → Arduino → motors
#
#  AUTONOMOUS NAVIGATION WORKFLOW:
#    1. Open RViz (launched here automatically)
#    2. Click "2D Pose Estimate" → click on RViz map to set initial pose
#    3. Click "2D Goal Pose" → click destination
#    4. Watch the robot navigate autonomously!
# ═══════════════════════════════════════════════════════════════════════════════

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    LogInfo,
    TimerAction,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    pkg = get_package_share_directory('mobile_robot')

    nav2_cfg = os.path.join(pkg, 'config', 'nav2_params.yaml')
    rviz_cfg = os.path.join(pkg, 'rviz',   'rviz_config.rviz')

    default_map = os.path.join(pkg, 'maps', 'lab_map.yaml')

    args = [
        DeclareLaunchArgument(
            'map_yaml',
            default_value=default_map,
            description='Full path to the map YAML file (from slam.launch.py map saving)'
        ),
        DeclareLaunchArgument(
            'nav2_params_file',
            default_value=nav2_cfg,
            description='Path to Nav2 params file'
        ),
        DeclareLaunchArgument(
            'use_rviz', default_value='true',
            description='Launch RViz for visualisation and goal setting'
        ),
        DeclareLaunchArgument(
            'rviz_config', default_value=rviz_cfg,
            description='RViz configuration file'
        ),
        DeclareLaunchArgument(
            'autostart', default_value='true',
            description='Auto-activate Nav2 lifecycle nodes'
        ),
    ]

    # ── Nav2 Bringup (includes all Nav2 servers via lifecycle) ───────────────
    nav2_bringup_dir = FindPackageShare('nav2_bringup')
    nav2_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            PathJoinSubstitution([nav2_bringup_dir, 'launch', 'bringup_launch.py'])
        ]),
        launch_arguments={
            'use_sim_time': 'false',
            'params_file':  LaunchConfiguration('nav2_params_file'),
            'map':          LaunchConfiguration('map_yaml'),
            'autostart':    LaunchConfiguration('autostart'),
        }.items(),
    )

    # ── RViz for autonomous navigation ────────────────────────────────────────
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2_nav',
        arguments=['-d', LaunchConfiguration('rviz_config')],
        output='screen',
        condition=IfCondition(LaunchConfiguration('use_rviz')),
    )

    return LaunchDescription(
        args + [
            LogInfo(msg='━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'),
            LogInfo(msg='  AURA Rover — nav2.launch.py'),
            LogInfo(msg='  Starting Nav2 autonomous navigation stack'),
            LogInfo(msg='  Ensure robot_bringup.launch.py is running!'),
            LogInfo(msg='  In RViz: set 2D Pose Estimate, then 2D Goal Pose'),
            LogInfo(msg='━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'),

            # Nav2 stack
            nav2_launch,

            # RViz after Nav2 is initialising (3s delay)
            TimerAction(period=3.0, actions=[rviz_node]),
        ]
    )
