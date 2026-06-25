"""
slam_mapping.launch.py
─────────────────────────────────────────────────────────────
SLAM-based mapping with standard Gazebo environment.

Features:
  • Gazebo with standard world (willowgarage or custom)
  • SLAM Toolbox for real-time mapping
  • Robot spawned with LiDAR sensor
  • RViz visualization with map display
  • Keyboard teleop for robot exploration

Usage:
    ros2 launch mobile_robot slam_mapping.launch.py

    # Optional: specify different world
    ros2 launch mobile_robot slam_mapping.launch.py world:=empty

Then in another terminal:
    ros2 run teleop_twist_keyboard teleop_twist_keyboard

Watch the map build in RViz as the robot explores!

ROS 2 Jazzy | Ubuntu 24.04 | Gazebo Harmonic
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    TimerAction,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, Command
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():

    pkg            = get_package_share_directory("mobile_robot")
    pkg_ros_gz_sim = get_package_share_directory("ros_gz_sim")

    # ── Launch arguments ──────────────────────────────────────
    world_arg = DeclareLaunchArgument(
        "world",
        default_value="willowgarage",
        description="Gazebo world name (willowgarage, empty, etc.)"
    )
    world = LaunchConfiguration("world")

    rviz_config_arg = DeclareLaunchArgument(
        "rviz_config",
        default_value=os.path.join(pkg, "rviz", "slam_mapping.rviz"),
        description="Full path to RViz config"
    )
    rviz_config = LaunchConfiguration("rviz_config")

    x_arg = DeclareLaunchArgument("x", default_value="0.0",  description="Spawn X")
    y_arg = DeclareLaunchArgument("y", default_value="0.0",  description="Spawn Y")
    z_arg = DeclareLaunchArgument("z", default_value="0.15", description="Spawn Z")

    use_sim_time = "true"

    # ── URDF/xacro ────────────────────────────────────────────
    urdf_file = os.path.join(pkg, "urdf", "mobile_robot.urdf.xacro")
    robot_description = ParameterValue(
        Command(["xacro ", urdf_file]),
        value_type=str
    )

    # ── robot_state_publisher ─────────────────────────────────
    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        output="screen",
        parameters=[{
            "robot_description": robot_description,
            "use_sim_time": True,
            "publish_frequency": 50.0,
        }],
    )

    # ── Gazebo Harmonic ───────────────────────────────────────
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_ros_gz_sim, "launch", "gz_sim.launch.py")
        ),
        launch_arguments={
            "gz_args": ["-r -v4 ", world],
            "on_exit_shutdown": "true",
        }.items(),
    )

    # ── Spawn robot ───────────────────────────────────────────
    spawn_robot = Node(
        package="ros_gz_sim",
        executable="create",
        name="spawn_mobile_robot",
        output="screen",
        arguments=[
            "-name",  "mobile_robot",
            "-topic", "/robot_description",
            "-x",     LaunchConfiguration("x"),
            "-y",     LaunchConfiguration("y"),
            "-z",     LaunchConfiguration("z"),
        ],
    )

    # ── ROS-GZ bridge ─────────────────────────────────────────
    bridge_params = os.path.join(pkg, "config", "ros_gz_bridge.yaml")
    ros_gz_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="ros_gz_bridge",
        output="screen",
        parameters=[{"config_file": bridge_params, "use_sim_time": True}],
    )

    # ── SLAM Toolbox ──────────────────────────────────────────
    slam_params = os.path.join(pkg, "config", "slam_toolbox.yaml")
    slam_toolbox = Node(
        package="slam_toolbox",
        executable="async_slam_toolbox_node",
        name="slam_toolbox",
        output="screen",
        parameters=[slam_params],
        remappings=[
            ("/tf", "tf"),
            ("/tf_static", "tf_static"),
        ],
    )

    # ── RViz2 (delayed to let everything boot) ────────────────
    rviz2 = TimerAction(
        period=5.0,
        actions=[
            Node(
                package="rviz2",
                executable="rviz2",
                name="rviz2",
                output="screen",
                arguments=["-d", rviz_config],
                parameters=[{"use_sim_time": True}],
            )
        ]
    )

    return LaunchDescription([
        world_arg,
        rviz_config_arg,
        x_arg, y_arg, z_arg,
        robot_state_publisher,
        gazebo,
        spawn_robot,
        ros_gz_bridge,
        slam_toolbox,
        rviz2,
    ])
