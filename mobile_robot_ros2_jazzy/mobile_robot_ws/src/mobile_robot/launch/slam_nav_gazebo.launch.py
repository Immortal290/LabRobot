"""
slam_nav_gazebo.launch.py
─────────────────────────────────────────────────────────────
All-in-one: Gazebo + SLAM Toolbox + Nav2 + RViz

What this launches:
  ✓ Gazebo Harmonic with lab world
  ✓ Robot spawned with diff-drive + LiDAR
  ✓ SLAM Toolbox → builds /map in real-time
  ✓ Nav2 (BT Navigator + Planner + Controller) → autonomous nav
  ✓ RViz2 with Map + LaserScan + RobotModel + 2D Goal Pose

How to use:
  Terminal 1 — launch everything:
      cd ~/Desktop/AURA/mobile_robot_ros2_jazzy/mobile_robot_ws
      source install/setup.bash
      ros2 launch mobile_robot slam_nav_gazebo.launch.py

  Terminal 2 — keyboard teleop (to build the map):
      ros2 run teleop_twist_keyboard teleop_twist_keyboard

  In RViz:
      Click "2D Goal Pose" → click on map → robot navigates autonomously!

ROS 2 Jazzy | Ubuntu 24.04 | Gazebo Harmonic
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    RegisterEventHandler,
    TimerAction,
    ExecuteProcess,
)
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, Command
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():

    pkg            = get_package_share_directory("mobile_robot")
    pkg_ros_gz_sim = get_package_share_directory("ros_gz_sim")
    pkg_nav2_bringup = get_package_share_directory("nav2_bringup")

    # ── Launch arguments ──────────────────────────────────────
    world_arg = DeclareLaunchArgument(
        "world",
        default_value=os.path.join(pkg, "worlds", "lab_world.sdf"),
        description="Full path to the Gazebo world file"
    )
    world = LaunchConfiguration("world")

    rviz_config_arg = DeclareLaunchArgument(
        "rviz_config",
        default_value=os.path.join(pkg, "rviz", "slam_nav.rviz"),
        description="Full path to RViz config"
    )
    rviz_config = LaunchConfiguration("rviz_config")

    x_arg   = DeclareLaunchArgument("x",   default_value="0.0",  description="Spawn X")
    y_arg   = DeclareLaunchArgument("y",   default_value="0.0",  description="Spawn Y")
    z_arg   = DeclareLaunchArgument("z",   default_value="0.15", description="Spawn Z")
    yaw_arg = DeclareLaunchArgument("yaw", default_value="0.0",  description="Spawn Yaw")

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
                    arguments=["diff_drive_controller", "--controller-manager", "/controller_manager"],
                    output="screen",
                )
            ],
        )
    )

    # ── SLAM Toolbox (starts mapping once controllers are up) ──
    slam_params = os.path.join(pkg, "config", "slam_toolbox.yaml")
    slam_toolbox = TimerAction(
        period=8.0,   # wait for Gazebo + controllers to stabilize
        actions=[
            Node(
                package="slam_toolbox",
                executable="async_slam_toolbox_node",
                name="slam_toolbox",
                output="screen",
                parameters=[
                    slam_params,
                    {"use_sim_time": True},
                ],
            )
        ]
    )

    # ── Nav2 Bringup (navigation only – no map_server, SLAM provides /map) ──
    nav2_params_file = os.path.join(pkg, "config", "nav2_params.yaml")
    nav2 = TimerAction(
        period=12.0,  # wait for SLAM to have a first map
        actions=[
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(pkg_nav2_bringup, "launch", "navigation_launch.py")
                ),
                launch_arguments={
                    "use_sim_time": use_sim_time,
                    "params_file": nav2_params_file,
                    "use_composition": "False",
                }.items(),
            )
        ]
    )

    # ── RViz2 ─────────────────────────────────────────────────
    rviz2 = TimerAction(
        period=6.0,
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
        slam_toolbox,
        nav2,
        rviz2,
    ])
