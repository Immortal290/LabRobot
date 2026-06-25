"""
rviz_navigation_teleop.launch.py
─────────────────────────────────────────────────────────────
Pure RViz-based navigation for Raspberry Pi 5
• Lightweight - NO Gazebo simulation
• Keyboard teleop + autonomous navigation via RViz
• Collision detection through costmaps
• Real-time robot movement visualization
• NO GPU/Physics engine required

Key Features:
  ✓ Optimized map (0.1m resolution)
  ✓ TF transforms for robot pose
  ✓ Odometry publishing for movement tracking
  ✓ Joint state publishing for wheel rotation
  ✓ Static costmaps with inflation layer
  ✓ Dynamic obstacle avoidance ready

ROS 2 Jazzy | Ubuntu 24.04 | Raspberry Pi 5

USAGE:
────────────────────────────────────────────────────────────
Terminal 1 (RViz + Navigation):
    cd ~/Desktop/AURA/mobile_robot_ros2_jazzy/mobile_robot_ws
    source install/setup.bash
    ros2 launch mobile_robot rviz_navigation_teleop.launch.py

Terminal 2 (Keyboard Teleop - OPTIONAL):
    ros2 run teleop_twist_keyboard teleop_twist_keyboard

Then in RViz:
  1. Click "2D Goal Pose" tool
  2. Click/drag on map to set goal
  3. Robot autonomously navigates!

Or use keyboard teleoperation (Terminal 2) for manual control.
────────────────────────────────────────────────────────────
"""

import os
import sys
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    TimerAction,
)
from launch.substitutions import LaunchConfiguration, Command
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    # Generate map at launch time
    try:
        pkg_dir = get_package_share_directory("mobile_robot")
        import sys
        sys.path.insert(0, os.path.join(pkg_dir, '..', 'mobile_robot'))
        from mobile_robot.optimized_map_generator import generate_optimized_map
        generate_optimized_map()
        print("✓ Map generated successfully")
    except Exception as e:
        print(f"⚠ Map generation: {e}")

    pkg = get_package_share_directory("mobile_robot")
    
    # ──────────────────────────────────────────────────────────
    # LAUNCH ARGUMENTS
    # ──────────────────────────────────────────────────────────
    
    map_arg = DeclareLaunchArgument(
        "map",
        default_value=os.path.join(pkg, "maps", "rviz_navigation_map.yaml"),
        description="Path to map YAML file"
    )
    map_file = LaunchConfiguration("map")
    
    rviz_config_arg = DeclareLaunchArgument(
        "rviz_config",
        default_value=os.path.join(pkg, "rviz", "mobile_robot.rviz"),
        description="RViz configuration file"
    )
    rviz_config = LaunchConfiguration("rviz_config")
    
    use_nav2_arg = DeclareLaunchArgument(
        "use_nav2",
        default_value="true",
        description="Enable Nav2 autonomous navigation"
    )
    use_nav2 = LaunchConfiguration("use_nav2")
    
    use_sim_time_arg = DeclareLaunchArgument(
        "use_sim_time",
        default_value="false",
        description="Use simulation time (false for real-time)"
    )
    use_sim_time = LaunchConfiguration("use_sim_time")
    
    # ──────────────────────────────────────────────────────────
    # ROBOT STATE PUBLISHER
    # Converts URDF → TF transforms for robot model
    # ──────────────────────────────────────────────────────────
    
    urdf_file = os.path.join(pkg, "urdf", "mobile_robot.urdf.xacro")
    robot_description = ParameterValue(
        Command(["xacro ", urdf_file]),
        value_type=str
    )
    
    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        output="screen",
        parameters=[{
            "robot_description": robot_description,
            "publish_frequency": 50.0,
            "use_sim_time": use_sim_time,
        }],
    )
    
    # ──────────────────────────────────────────────────────────
    # JOINT STATE PUBLISHER
    # Publishes wheel joint states (rotations)
    # ──────────────────────────────────────────────────────────
    
    joint_state_publisher = Node(
        package="joint_state_publisher",
        executable="joint_state_publisher",
        name="joint_state_publisher",
        output="screen",
        parameters=[{
            "use_sim_time": use_sim_time,
        }],
    )
    
    # ──────────────────────────────────────────────────────────
    # CMD_VEL TO JOINTS CONVERTER
    # Converts /cmd_vel → wheel rotations + odometry
    # ──────────────────────────────────────────────────────────
    
    cmd_vel_to_joints = Node(
        package="mobile_robot",
        executable="cmd_vel_to_joints",
        name="cmd_vel_to_joints",
        output="screen",
        parameters=[{
            "use_sim_time": use_sim_time,
        }],
    )
    

    
    # ──────────────────────────────────────────────────────────
    # MAP SERVER
    # Loads map and makes it available to RViz
    # ──────────────────────────────────────────────────────────
    
    map_server = Node(
        package="nav2_map_server",
        executable="map_server",
        name="map_server",
        output="screen",
        parameters=[{
            "yaml_filename": map_file,
            "use_sim_time": use_sim_time,
        }],
    )
    
    # Lifecycle transitions with longer delays
    configure_map_server = ExecuteProcess(
        cmd=['bash', '-c', 'sleep 2 && ros2 lifecycle set /map_server configure'],
        output='screen',
    )
    
    activate_map_server = ExecuteProcess(
        cmd=['bash', '-c', 'sleep 3 && ros2 lifecycle set /map_server activate'],
        output='screen',
    )
    
    # ──────────────────────────────────────────────────────────
    # COSTMAP NODE (for collision detection)
    # Inflates obstacles and creates safety margins
    # ──────────────────────────────────────────────────────────
    
    costmap_node = Node(
        package="nav2_map_server",
        executable="costmap_filter_info_server",
        name="costmap_filter_info_server",
        output="screen",
        parameters=[{
            "use_sim_time": use_sim_time,
        }],
    )
    
    # ──────────────────────────────────────────────────────────
    # RVIZ2 VISUALIZATION
    # Displays robot, map, and allows goal setting
    # ──────────────────────────────────────────────────────────
    
    rviz2 = TimerAction(
        period=2.0,
        actions=[
            Node(
                package="rviz2",
                executable="rviz2",
                name="rviz2",
                output="screen",
                arguments=["-d", rviz_config],
                parameters=[{
                    "use_sim_time": use_sim_time,
                }],
            )
        ]
    )
    
    # ──────────────────────────────────────────────────────────
    # BUILD LAUNCH DESCRIPTION
    # ──────────────────────────────────────────────────────────
    
    ld = LaunchDescription([
        # Arguments
        map_arg,
        rviz_config_arg,
        use_nav2_arg,
        use_sim_time_arg,
        
        # Core nodes (always run)
        robot_state_publisher,
        joint_state_publisher,
        cmd_vel_to_joints,
        map_server,
        
        # Map server lifecycle transitions
        configure_map_server,
        activate_map_server,
        
        costmap_node,
        
        # Visualization
        rviz2,
    ])
    
    return ld
