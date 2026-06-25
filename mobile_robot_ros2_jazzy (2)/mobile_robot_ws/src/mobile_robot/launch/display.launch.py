"""
display.launch.py
─────────────────────────────────────────────────────────────
Launch RViz2 with the robot model, TF, and joint state publisher.
Use this for quick model inspection without simulation.

ROS 2 Jazzy | Ubuntu 24.04
Usage:
    ros2 launch mobile_robot display.launch.py
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, TimerAction
from launch.substitutions import LaunchConfiguration, Command
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():

    pkg = get_package_share_directory("mobile_robot")

    # ── Launch arguments ──────────────────────────────────────
    use_sim_time_arg = DeclareLaunchArgument(
        "use_sim_time", default_value="false",
        description="Use simulation clock"
    )
    use_sim_time = LaunchConfiguration("use_sim_time")

    rviz_config_arg = DeclareLaunchArgument(
        "rviz_config",
        default_value=os.path.join(pkg, "rviz", "mobile_robot.rviz"),
        description="Full path to RViz config"
    )
    rviz_config = LaunchConfiguration("rviz_config")

    # ── Xacro → URDF string ───────────────────────────────────
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
        parameters=[
            {"robot_description": robot_description,
             "use_sim_time": use_sim_time,
             "publish_frequency": 50.0}
        ],
    )

    # ── joint_state_publisher_gui ─────────────────────────────
    joint_state_publisher_gui = Node(
        package="joint_state_publisher_gui",
        executable="joint_state_publisher_gui",
        name="joint_state_publisher_gui",
        output="screen",
        parameters=[{"use_sim_time": use_sim_time}],
    )

    # ── RViz2 ─────────────────────────────────────────────────
    rviz2 = TimerAction(
        period=2.0,
        actions=[
            Node(
                package="rviz2",
                executable="rviz2",
                name="rviz2",
                output="screen",
                arguments=["-d", rviz_config],
                parameters=[{"use_sim_time": use_sim_time}],
            )
        ]
    )

    return LaunchDescription([
        use_sim_time_arg,
        rviz_config_arg,
        robot_state_publisher,
        joint_state_publisher_gui,
        rviz2,
    ])
