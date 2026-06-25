"""
teleop.launch.py
─────────────────────────────────────────────────────────────
Launch teleop_twist_keyboard remapped to /cmd_vel.
Run this in a SEPARATE terminal alongside gazebo.launch.py.

ROS 2 Jazzy | Ubuntu 24.04
Usage:
    ros2 launch mobile_robot teleop.launch.py
    
Keyboard controls (teleop_twist_keyboard):
    i     - move forward
    ,     - move backward
    j     - turn left
    l     - turn right
    k     - stop
    u/o   - forward-left / forward-right
    q/z   - increase/decrease max speeds
    w/x   - increase/decrease linear speed
    e/c   - increase/decrease angular speed
"""

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():

    # ── Arguments ─────────────────────────────────────────────
    use_sim_time_arg = DeclareLaunchArgument(
        "use_sim_time", default_value="false",
        description="Use simulation clock"
    )

    cmd_vel_topic_arg = DeclareLaunchArgument(
        "cmd_vel_topic", default_value="/cmd_vel",
        description="cmd_vel topic to publish to"
    )

    # ── teleop_twist_keyboard ─────────────────────────────────
    teleop_node = Node(
        package="teleop_twist_keyboard",
        executable="teleop_twist_keyboard",
        name="teleop_twist_keyboard",
        output="screen",
        prefix="xterm -e",          # opens in its own terminal window
        remappings=[
            ("/cmd_vel", LaunchConfiguration("cmd_vel_topic"))
        ],
        parameters=[{
            "use_sim_time": LaunchConfiguration("use_sim_time"),
        }],
    )

    return LaunchDescription([
        use_sim_time_arg,
        cmd_vel_topic_arg,
        teleop_node,
    ])
