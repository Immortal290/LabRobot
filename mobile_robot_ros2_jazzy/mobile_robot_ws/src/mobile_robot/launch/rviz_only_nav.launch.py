"""
rviz_only_nav.launch.py
─────────────────────────────────────────────────────────────
Autonomous navigation in RViz WITHOUT Gazebo.

Architecture (minimal, reliable):
  1. robot_state_publisher   – URDF TF tree
  2. joint_state_publisher   – wheel joint positions
  3. cmd_vel_to_joints       – /cmd_vel → odom → TF (odom→base_footprint)
  4. static_tf map→odom      – anchors map to odom frame
  5. map_server              – serves pre-built lab map  ┐
  6. planner_server          – global path (NavFn)       │ managed by
  7. controller_server       – local path + /cmd_vel out │ lifecycle_manager
  8. bt_navigator            – action server for goals   ┘
  9. nav2_lifecycle_manager  – activates all Nav2 nodes
 10. rviz2                   – top-down map view

cmd_vel flow:
  bt_navigator → controller_server → /cmd_vel → cmd_vel_to_joints → /odom + TF

ROS 2 Jazzy | Ubuntu 24.04 | No Gazebo required
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, TimerAction
from launch.substitutions import LaunchConfiguration, Command
from launch.conditions import IfCondition, UnlessCondition
from launch_ros.actions import Node, LifecycleNode
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():

    pkg = get_package_share_directory("mobile_robot")

    default_map    = os.path.join(pkg, "maps",   "lab_world_map.yaml")
    default_rviz   = os.path.join(pkg, "rviz",   "rviz_only_nav.rviz")
    default_params = os.path.join(pkg, "config", "nav2_params_rviz_only.yaml")

    # ── Launch arguments ──────────────────────────────────────
    map_arg = DeclareLaunchArgument(
        "map", default_value=default_map, description="Map YAML file")
    rviz_arg = DeclareLaunchArgument(
        "rviz_config", default_value=default_rviz, description="RViz config")
    params_arg = DeclareLaunchArgument(
        "params_file", default_value=default_params, description="Nav2 params")
    real_camera_arg = DeclareLaunchArgument(
        "real_camera", default_value="false", description="Use real-life camera feed instead of simulated camera")

    map_file   = LaunchConfiguration("map")
    rviz_file  = LaunchConfiguration("rviz_config")
    params_file = LaunchConfiguration("params_file")
    real_camera = LaunchConfiguration("real_camera")

    # ── URDF ──────────────────────────────────────────────────
    urdf_file = os.path.join(pkg, "urdf", "mobile_robot.urdf.xacro")
    robot_description = ParameterValue(
        Command(["xacro ", urdf_file]), value_type=str)

    # ─────────────────────────────────────────────────────────
    # 1. robot_state_publisher
    #    Publishes: base_footprint→base_link→lidar_link→wheels (from URDF)
    # ─────────────────────────────────────────────────────────
    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        output="screen",
        parameters=[{
            "robot_description": robot_description,
            "publish_frequency": 50.0,
            "use_sim_time": False,
        }],
    )

    # ─────────────────────────────────────────────────────────
    # 2. joint_state_publisher
    #    Publishes wheel joint states (all zero, updated by cmd_vel_to_joints)
    # ─────────────────────────────────────────────────────────
    joint_state_publisher = Node(
        package="joint_state_publisher",
        executable="joint_state_publisher",
        name="joint_state_publisher",
        output="screen",
        parameters=[{"use_sim_time": False, "rate": 50}],
    )

    # ─────────────────────────────────────────────────────────
    # 3. cmd_vel_to_joints
    #    Subscribes /cmd_vel (from Nav2 controller_server)
    #    Publishes  /odom + TF odom→base_footprint  (50 Hz)
    # ── cmd_vel_to_joints ─────────────────────────────────────
    cmd_vel_to_joints = Node(
        package="mobile_robot",
        executable="cmd_vel_to_joints",
        name="cmd_vel_to_joints",
        output="screen",
        parameters=[{"use_sim_time": False}],
    )

    # ── simulated_lidar ───────────────────────────────────────
    simulated_lidar = Node(
        package="mobile_robot",
        executable="simulated_lidar",
        name="simulated_lidar",
        output="screen",
        parameters=[{"use_sim_time": False}],
    )

    # ── simulated_camera ──────────────────────────────────────
    simulated_camera = Node(
        package="mobile_robot",
        executable="simulated_camera",
        name="simulated_camera",
        output="screen",
        parameters=[{"use_sim_time": False}],
    )

    # ── real_camera ───────────────────────────────────────────
    real_camera_node = Node(
        package="usb_cam",
        executable="usb_cam_node_exe",
        name="usb_cam",
        output="screen",
        parameters=[{
            "video_device": "/dev/video0",
            "image_width": 640,
            "image_height": 480,
            "framerate": 30.0,
        }],
        remappings=[
            ("image_raw", "/real_camera/image_raw"),
            ("camera_info", "/real_camera/camera_info"),
        ]
    )

    # ─────────────────────────────────────────────────────────
    # 4. Static TF: map → odom  (identity)
    #    Robot starts at map origin (0, 0).
    # ─────────────────────────────────────────────────────────
    static_tf_map_odom = Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        name="static_tf_map_odom",
        output="screen",
        arguments=["--x", "0", "--y", "0", "--z", "0",
                   "--roll", "0", "--pitch", "0", "--yaw", "0",
                   "--frame-id", "map", "--child-frame-id", "odom"],
    )

    # ─────────────────────────────────────────────────────────
    # 5. map_server  (lifecycle node — managed by lifecycle_manager)
    # ─────────────────────────────────────────────────────────
    map_server = LifecycleNode(
        package="nav2_map_server",
        executable="map_server",
        name="map_server",
        namespace="",
        output="screen",
        parameters=[{
            "yaml_filename": map_file,
            "use_sim_time": False,
            "frame_id": "map",
        }],
    )

    # ─────────────────────────────────────────────────────────
    # 6. planner_server  (NavFn A* global planner)
    # ─────────────────────────────────────────────────────────
    planner_server = LifecycleNode(
        package="nav2_planner",
        executable="planner_server",
        name="planner_server",
        namespace="",
        output="screen",
        parameters=[params_file],
    )

    # ─────────────────────────────────────────────────────────
    # 7. controller_server  (DWB local planner → /cmd_vel)
    # ─────────────────────────────────────────────────────────
    controller_server = LifecycleNode(
        package="nav2_controller",
        executable="controller_server",
        name="controller_server",
        namespace="",
        output="screen",
        parameters=[params_file],
        remappings=[("cmd_vel", "cmd_vel")],  # explicit — no smoother in chain
    )

    # ─────────────────────────────────────────────────────────
    # 8. behavior_server  (spin, backup, wait recoveries)
    # ─────────────────────────────────────────────────────────
    behavior_server = LifecycleNode(
        package="nav2_behaviors",
        executable="behavior_server",
        name="behavior_server",
        namespace="",
        output="screen",
        parameters=[params_file],
    )

    # ─────────────────────────────────────────────────────────
    # 9. bt_navigator  (action server /navigate_to_pose)
    # ─────────────────────────────────────────────────────────
    bt_navigator = LifecycleNode(
        package="nav2_bt_navigator",
        executable="bt_navigator",
        name="bt_navigator",
        namespace="",
        output="screen",
        parameters=[params_file],
    )

    # ─────────────────────────────────────────────────────────
    # 10. lifecycle_manager
    #     Activates all Nav2 lifecycle nodes in order.
    #     autostart=True → configure+activate automatically.
    # ─────────────────────────────────────────────────────────
    lifecycle_manager = Node(
        package="nav2_lifecycle_manager",
        executable="lifecycle_manager",
        name="lifecycle_manager_navigation",
        output="screen",
        parameters=[{
            "use_sim_time": False,
            "autostart": True,
            "node_names": [
                "map_server",
                "planner_server",
                "controller_server",
                "behavior_server",
                "bt_navigator",
            ],
            "bond_timeout": 4.0,
        }],
    )

    # ─────────────────────────────────────────────────────────
    # 11. RViz2  (delayed 3 s to let map_server activate first)
    # ─────────────────────────────────────────────────────────
    rviz2 = TimerAction(
        period=3.0,
        actions=[
            Node(
                package="rviz2",
                executable="rviz2",
                name="rviz2",
                output="screen",
                arguments=["-d", rviz_file],
                parameters=[{"use_sim_time": False}],
            )
        ]
    )

    return LaunchDescription([
        # Args
        map_arg,
        rviz_arg,
        params_arg,
        real_camera_arg,

        # Core simulation nodes (start immediately)
        robot_state_publisher,
        joint_state_publisher,
        cmd_vel_to_joints,
        simulated_lidar,
        simulated_camera,
        real_camera_node,
        static_tf_map_odom,

        # Nav2 nodes (lifecycle-managed)
        map_server,
        planner_server,
        controller_server,
        behavior_server,
        bt_navigator,

        # Lifecycle manager (auto-activates all the above)
        lifecycle_manager,

        # Visualization
        rviz2,
    ])
