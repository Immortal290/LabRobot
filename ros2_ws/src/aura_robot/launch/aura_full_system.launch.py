"""
launch/aura_full_system.launch.py
==================================
Dependency-aware launch of every AURA node.

Launch order:
  1. health_monitor        (must be first — provides /aura/arduino_ok, /aura/lidar_ok)
  2. hardware_controller   (depends on arduino_ok)
  3. barcode_navigator     (depends on DB)
  4. otp_manager           (depends on DB)
  5. inventory_sync        (depends on DB)
  6. delivery_manager      (depends on hardware_controller, otp_manager)
  7. ros2_bridge           (depends on backend WebSocket)

Usage:
  ros2 launch aura_robot aura_full_system.launch.py
  ros2 launch aura_robot aura_full_system.launch.py mock:=true
"""

import os
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    LogInfo,
    TimerAction,
    GroupAction,
)
from launch.substitutions import LaunchConfiguration, EnvironmentVariable
from launch_ros.actions import Node


def generate_launch_description():
    # ── Launch arguments ────────────────────────────────────────────────────
    mock_arg = DeclareLaunchArgument(
        "mock", default_value="false",
        description="Run in mock/simulation mode (no real hardware required)"
    )
    backend_url_arg = DeclareLaunchArgument(
        "backend_url", default_value="ws://localhost:8000/ws/bridge",
        description="FastAPI backend WebSocket URL"
    )
    backend_api_arg = DeclareLaunchArgument(
        "backend_api_url", default_value="http://localhost:8000/api/v1",
        description="FastAPI backend REST API URL"
    )
    db_url_arg = DeclareLaunchArgument(
        "db_url",
        default_value="postgresql://robot_user:robot_password@localhost:5435/labrobot",
        description="PostgreSQL connection string"
    )
    arduino_port_arg = DeclareLaunchArgument(
        "arduino_port", default_value="/dev/ttyUSB0",
        description="Arduino Nano serial port"
    )
    lidar_port_arg = DeclareLaunchArgument(
        "lidar_port", default_value="/dev/ttyUSB1",
        description="YDLIDAR X4 serial port"
    )

    # ── Shared environment ───────────────────────────────────────────────────
    shared_env = {
        "DATABASE_URL":     LaunchConfiguration("db_url"),
        "BACKEND_API_URL":  LaunchConfiguration("backend_api_url"),
        "ARDUINO_PORT":     LaunchConfiguration("arduino_port"),
        "LIDAR_PORT":       LaunchConfiguration("lidar_port"),
        "BARCODE_MOCK":     LaunchConfiguration("mock"),
        "PYTHONUNBUFFERED": "1",
    }

    # ── Node definitions ────────────────────────────────────────────────────

    health_monitor = Node(
        package="aura_robot",
        executable="health_monitor",
        name="aura_health_monitor",
        output="screen",
        emulate_tty=True,
        env=shared_env,
        parameters=[{"use_sim_time": False}],
    )

    # Delay 2 s so health_monitor can publish its first topics
    hardware_controller = TimerAction(
        period=2.0,
        actions=[Node(
            package="aura_robot",
            executable="hardware_controller",
            name="aura_hardware_controller",
            output="screen",
            emulate_tty=True,
            env=shared_env,
        )],
    )

    barcode_navigator = TimerAction(
        period=3.0,
        actions=[Node(
            package="aura_robot",
            executable="barcode_navigator",
            name="aura_barcode_navigator",
            output="screen",
            emulate_tty=True,
            env=shared_env,
        )],
    )

    otp_manager = TimerAction(
        period=3.0,
        actions=[Node(
            package="aura_robot",
            executable="otp_manager",
            name="aura_otp_manager",
            output="screen",
            emulate_tty=True,
            env=shared_env,
        )],
    )

    inventory_sync = TimerAction(
        period=3.0,
        actions=[Node(
            package="aura_robot",
            executable="inventory_sync",
            name="aura_inventory_sync",
            output="screen",
            emulate_tty=True,
            env=shared_env,
        )],
    )

    # Delivery manager starts last (5 s) — depends on hardware + OTP + inventory
    delivery_manager = TimerAction(
        period=5.0,
        actions=[Node(
            package="aura_robot",
            executable="delivery_manager",
            name="aura_delivery_manager",
            output="screen",
            emulate_tty=True,
            env=shared_env,
        )],
    )

    # Bridge starts at 6 s — needs all other nodes up
    ros2_bridge = TimerAction(
        period=6.0,
        actions=[Node(
            package="aura_robot",
            executable="ros2_bridge",
            name="aura_ros2_bridge",
            output="screen",
            emulate_tty=True,
            env={
                **shared_env,
                "BACKEND_URL": LaunchConfiguration("backend_url"),
                "PUBLISH_HZ":  "10",
            },
        )],
    )

    return LaunchDescription([
        mock_arg,
        backend_url_arg,
        backend_api_arg,
        db_url_arg,
        arduino_port_arg,
        lidar_port_arg,
        LogInfo(msg="═══ AURA Full System Launch Starting ═══"),
        health_monitor,
        hardware_controller,
        barcode_navigator,
        otp_manager,
        inventory_sync,
        delivery_manager,
        ros2_bridge,
        LogInfo(msg="═══ All nodes launched. System online. ═══"),
    ])
