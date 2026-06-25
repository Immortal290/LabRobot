"""
╔══════════════════════════════════════════════════════════════╗
║  display.launch.py  —  Lab Assistant Robot  (ROS 2 Jazzy)   ║
╠══════════════════════════════════════════════════════════════╣
║  Launches (all automatic, zero manual config in RViz):       ║
║  1. robot_state_publisher  — URDF + all TF frames           ║
║  2. joint_state_publisher_gui — wheel joint sliders          ║
║  3. rviz2 — with pre-loaded robot.rviz config               ║
║     ✓ Grid          ✓ RobotModel   ✓ TF frames              ║
║     ✓ LaserScan     ✓ Collision    ✓ Axes                   ║
╠══════════════════════════════════════════════════════════════╣
║  Usage:                                                      ║
║    ros2 launch lab_robot display.launch.py                   ║
║    ros2 launch lab_robot display.launch.py                   ║
║         use_gui:=false   ← headless joint publisher         ║
╚══════════════════════════════════════════════════════════════╝
"""
 
import os
 
from ament_index_python.packages import get_package_share_directory
 
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    LogInfo,
    TimerAction,
)
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import (
    Command,
    FindExecutable,
    LaunchConfiguration,
    PathJoinSubstitution,
)
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
 
 
def generate_launch_description():
 
    # ── Package paths ────────────────────────────────────────────
    pkg_share = get_package_share_directory('lab_robot')
 
    xacro_file  = os.path.join(pkg_share, 'urdf',
                                'lab_assistant_robot.urdf.xacro')
    rviz_config = os.path.join(pkg_share, 'rviz', 'robot.rviz')
 
    # ── Launch arguments ─────────────────────────────────────────
    declare_use_gui = DeclareLaunchArgument(
        name='use_gui',
        default_value='true',
        description='true = joint_state_publisher_gui  |  '
                    'false = headless joint_state_publisher')
 
    declare_use_rviz = DeclareLaunchArgument(
        name='use_rviz',
        default_value='true',
        description='Set to false to skip launching RViz2')
 
    declare_rviz_cfg = DeclareLaunchArgument(
        name='rviz_config',
        default_value=rviz_config,
        description='Absolute path to custom .rviz config')
 
    use_gui      = LaunchConfiguration('use_gui')
    use_rviz     = LaunchConfiguration('use_rviz')
    rviz_cfg_arg = LaunchConfiguration('rviz_config')
 
    # ── Parse XACRO → robot_description string ──────────────────
    robot_description_content = Command([
        FindExecutable(name='xacro'),
        ' ',
        xacro_file,
    ])
    robot_description = {'robot_description': robot_description_content}
 
    # ── 1. Robot State Publisher ─────────────────────────────────
    #  Reads robot_description and broadcasts all TF frames
    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[
            robot_description,
            {'publish_frequency': 50.0},
            {'ignore_timestamp': False},
        ],
    )
 
    # ── 2a. Joint State Publisher GUI (interactive sliders) ──────
    joint_state_publisher_gui_node = Node(
        package='joint_state_publisher_gui',
        executable='joint_state_publisher_gui',
        name='joint_state_publisher_gui',
        output='screen',
        condition=IfCondition(use_gui),
    )
 
    # ── 2b. Joint State Publisher (headless, no GUI) ─────────────
    joint_state_publisher_node = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher',
        name='joint_state_publisher',
        output='screen',
        condition=UnlessCondition(use_gui),
    )
 
    # ── 3. RViz2 with pre-loaded config ──────────────────────────
    #  -d  loads the .rviz file → all displays pre-configured
    rviz2_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', rviz_cfg_arg],
        parameters=[robot_description],
        condition=IfCondition(use_rviz),
    )
 
    # ── Startup banner ───────────────────────────────────────────
    banner = LogInfo(
        msg=[
            '\n',
            '╔══════════════════════════════════════════════╗\n',
            '║  Lab Assistant Robot — RViz2 Display         ║\n',
            '╠══════════════════════════════════════════════╣\n',
            '║  XACRO  : urdf/lab_assistant_robot.urdf.xacro║\n',
            '║  RViz   : rviz/robot.rviz  (pre-configured)  ║\n',
            '║  Topics : /robot_description  /joint_states  ║\n',
            '╚══════════════════════════════════════════════╝',
        ]
    )
 
    return LaunchDescription([
        # Arguments
        declare_use_gui,
        declare_use_rviz,
        declare_rviz_cfg,
 
        # Startup log
        banner,
 
        # Nodes
        robot_state_publisher_node,
        joint_state_publisher_gui_node,
        joint_state_publisher_node,
 
        # RViz with slight delay so robot_state_publisher is ready
        TimerAction(period=1.0, actions=[rviz2_node]),
    ])
 
