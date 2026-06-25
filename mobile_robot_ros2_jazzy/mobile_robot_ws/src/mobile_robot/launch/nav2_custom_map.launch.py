"""
nav2_custom_map.launch.py
─────────────────────────────────────────────────────────────
Autonomous navigation with custom map and point-and-click goals.

Features:
  • Custom generated map with walls/obstacles
  • Nav2 for path planning and autonomous navigation
  • RViz with point-and-click goal selection (2D Goal Pose tool)
  • Robot state publisher and odometry
  • Costmaps (static + dynamic)

ROS 2 Jazzy | Ubuntu 24.04

Usage:
    ros2 launch mobile_robot nav2_custom_map.launch.py

Then:
    • Click "2D Goal Pose" tool in RViz
    • Click on map to set goal point
    • Robot will autonomously navigate!

Keyboard teleop (optional, in separate terminal):
    ros2 run teleop_twist_keyboard teleop_twist_keyboard
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    TimerAction,
    ExecuteProcess,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, Command
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():

    pkg = get_package_share_directory("mobile_robot")
    
    # Generate map on startup
    generate_map = ExecuteProcess(
        cmd=['python3', os.path.join(pkg, 'mobile_robot', 'map_generator.py')],
        output='screen',
    )
    
    # ── URDF/xacro ───────────────────────────────────────────
    urdf_file = os.path.join(pkg, "urdf", "mobile_robot.urdf.xacro")
    robot_description = ParameterValue(
        Command(["xacro ", urdf_file]),
        value_type=str
    )

    # ── robot_state_publisher ────────────────────────────────
    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        output="screen",
        parameters=[{
            "robot_description": robot_description,
            "publish_frequency": 50.0,
        }],
    )

    # ── joint_state_publisher (for wheel rotation) ───────────
    joint_state_publisher = Node(
        package="joint_state_publisher",
        executable="joint_state_publisher",
        name="joint_state_publisher",
        output="screen",
        parameters=[{
            "use_sim_time": False,
        }],
    )

    # ── cmd_vel_to_joints (odometry node) ────────────────────
    cmd_vel_to_joints = Node(
        package="mobile_robot",
        executable="cmd_vel_to_joints",
        name="cmd_vel_to_joints",
        output="screen",
    )

    # ── Map Server ───────────────────────────────────────────
    map_file = os.path.join(pkg, "maps", "custom_map.yaml")
    map_server = Node(
        package="nav2_map_server",
        executable="map_server",
        name="map_server",
        output="screen",
        parameters=[{
            "yaml_filename": map_file,
            "use_sim_time": False,
        }],
    )

    # ── AMCL (Localization) ──────────────────────────────────
    amcl_config = os.path.join(pkg, "config", "amcl.yaml")
    amcl = Node(
        package="nav2_amcl",
        executable="amcl",
        name="amcl",
        output="screen",
        parameters=[amcl_config],
        remappings=[
            ("/tf", "tf"),
            ("/tf_static", "tf_static"),
        ],
    )

    # ── Nav2 Controller Manager ──────────────────────────────
    nav2_config = os.path.join(pkg, "config", "nav2_params.yaml")
    nav2_container = Node(
        package="nav2_controller",
        executable="controller_server",
        name="controller_server",
        output="screen",
        parameters=[nav2_config],
        remappings=[
            ("/tf", "tf"),
            ("/tf_static", "tf_static"),
        ],
    )

    # ── Nav2 Planner ────────────────────────────────────────
    nav2_planner = Node(
        package="nav2_planner",
        executable="planner_server",
        name="planner_server",
        output="screen",
        parameters=[nav2_config],
        remappings=[
            ("/tf", "tf"),
            ("/tf_static", "tf_static"),
        ],
    )

    # ── Nav2 Behaviors ──────────────────────────────────────
    nav2_behaviors = Node(
        package="nav2_behaviors",
        executable="behavior_server",
        name="behavior_server",
        output="screen",
        parameters=[nav2_config],
        remappings=[
            ("/tf", "tf"),
            ("/tf_static", "tf_static"),
        ],
    )

    # ── Nav2 BT Navigator ──────────────────────────────────────
    nav2_navigator = Node(
        package="nav2_bt_navigator",
        executable="bt_navigator",
        name="bt_navigator",
        output="screen",
        parameters=[nav2_config],
        remappings=[
            ("/tf", "tf"),
            ("/tf_static", "tf_static"),
        ],
    )

    # ── Lifecycle Manager ──────────────────────────────────────
    lifecycle_manager = Node(
        package="nav2_lifecycle_manager",
        executable="lifecycle_manager_server",
        name="lifecycle_manager",
        output="screen",
        parameters=[{
            "autostart": True,
            "node_names": [
                "map_server",
                "amcl",
                "controller_server",
                "planner_server",
                "behavior_server",
                "bt_navigator",
            ]
        }],
    )

    # ── RViz2 (delayed) ─────────────────────────────────────
    rviz_config = os.path.join(pkg, "rviz", "nav2_custom_map.rviz")
    rviz2 = TimerAction(
        period=3.0,
        actions=[
            Node(
                package="rviz2",
                executable="rviz2",
                name="rviz2",
                output="screen",
                arguments=["-d", rviz_config],
            )
        ]
    )

    return LaunchDescription([
        generate_map,
        robot_state_publisher,
        joint_state_publisher,
        cmd_vel_to_joints,
        map_server,
        amcl,
        nav2_container,
        nav2_planner,
        nav2_behaviors,
        nav2_navigator,
        lifecycle_manager,
        rviz2,
    ])
