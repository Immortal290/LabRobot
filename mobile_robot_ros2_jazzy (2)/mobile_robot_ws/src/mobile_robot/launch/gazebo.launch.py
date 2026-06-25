"""
gazebo.launch.py
─────────────────────────────────────────────────────────────
Full Gazebo Harmonic simulation with:
  • robot spawned from URDF/xacro
  • ros2_control (diff drive + joint state broadcaster)
  • robot_state_publisher  (TF tree)
  • EKF localization (odom → base_footprint)
  • RViz2 pre-configured

ROS 2 Jazzy | Ubuntu 24.04
Usage:
    ros2 launch mobile_robot gazebo.launch.py
    ros2 launch mobile_robot gazebo.launch.py world:=<world_file>
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    RegisterEventHandler,
    TimerAction,
)
from launch.event_handlers import OnProcessExit, OnProcessStart
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, Command, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():

    pkg            = get_package_share_directory("mobile_robot")
    pkg_ros_gz_sim = get_package_share_directory("ros_gz_sim")

    # ── Launch arguments ──────────────────────────────────────
    world_arg = DeclareLaunchArgument(
        "world",
        default_value=os.path.join(pkg, "worlds", "empty_world.sdf"),
        description="Full path to the Gazebo world file"
    )
    world = LaunchConfiguration("world")

    rviz_config_arg = DeclareLaunchArgument(
        "rviz_config",
        default_value=os.path.join(pkg, "rviz", "mobile_robot.rviz"),
        description="Full path to RViz config"
    )
    rviz_config = LaunchConfiguration("rviz_config")

    x_arg = DeclareLaunchArgument("x", default_value="0.0",  description="Spawn X")
    y_arg = DeclareLaunchArgument("y", default_value="0.0",  description="Spawn Y")
    z_arg = DeclareLaunchArgument("z", default_value="0.15", description="Spawn Z")
    yaw_arg = DeclareLaunchArgument("yaw", default_value="0.0", description="Spawn Yaw")

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
            "-Y",     LaunchConfiguration("yaw"),
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

    # ── Load ros2 controllers (after spawn) ───────────────────
    load_joint_state_broadcaster = RegisterEventHandler(
        event_handler=OnProcessExit(
            target_action=spawn_robot,
            on_exit=[
                Node(
                    package="controller_manager",
                    executable="spawner",
                    arguments=["joint_state_broadcaster", "--controller-manager", "/controller_manager"],
                    output="screen",
                )
            ],
        )
    )

    load_diff_drive_controller = RegisterEventHandler(
        event_handler=OnProcessExit(
            target_action=spawn_robot,
            on_exit=[
                Node(
                    package="controller_manager",
                    executable="spawner",
                    arguments=["diff_drive_controller",
                               "--controller-manager", "/controller_manager"],
                    output="screen",
                )
            ],
        )
    )

    # ── EKF (robot_localization) ──────────────────────────────
    ekf_config = os.path.join(pkg, "config", "ekf.yaml")
    ekf_node = Node(
        package="robot_localization",
        executable="ekf_node",
        name="ekf_filter_node",
        output="screen",
        parameters=[ekf_config, {"use_sim_time": True}],
        remappings=[("odometry/filtered", "/odom_ekf")],
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
        x_arg, y_arg, z_arg, yaw_arg,
        robot_state_publisher,
        gazebo,
        spawn_robot,
        ros_gz_bridge,
        load_joint_state_broadcaster,
        load_diff_drive_controller,
        ekf_node,
        rviz2,
    ])
