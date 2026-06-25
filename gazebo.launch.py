"""
╔══════════════════════════════════════════════════════════════╗
║  gazebo.launch.py  —  Lab Assistant Robot  (ROS 2 Jazzy)    ║
╠══════════════════════════════════════════════════════════════╣
║  Launches:                                                   ║
║  1. Gazebo (empty world)                                     ║
║  2. robot_state_publisher                                    ║
║  3. spawn_entity  (drops robot into simulation)              ║
║  4. ros2_control spawners for 4 wheel velocity controllers  ║
║  5. rviz2  (pre-configured, optional)                       ║
╠══════════════════════════════════════════════════════════════╣
║  Usage:                                                      ║
║    ros2 launch lab_robot gazebo.launch.py                    ║
║    ros2 launch lab_robot gazebo.launch.py use_rviz:=false   ║
╚══════════════════════════════════════════════════════════════╝
"""

import os

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    IncludeLaunchDescription,
    LogInfo,
    RegisterEventHandler,
    TimerAction,
)
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    Command,
    FindExecutable,
    LaunchConfiguration,
    PathJoinSubstitution,
)
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():

    pkg_share   = get_package_share_directory('lab_robot')
    xacro_file  = os.path.join(pkg_share, 'urdf',
                                'lab_assistant_robot.urdf.xacro')
    rviz_config = os.path.join(pkg_share, 'rviz', 'robot.rviz')

    # ── Declare arguments ────────────────────────────────────────
    declare_use_rviz = DeclareLaunchArgument(
        'use_rviz', default_value='true',
        description='Launch RViz2 alongside Gazebo')

    declare_world = DeclareLaunchArgument(
        'world', default_value='',
        description='Path to Gazebo world file (empty = default)')

    declare_x = DeclareLaunchArgument('x_pose', default_value='0.0')
    declare_y = DeclareLaunchArgument('y_pose', default_value='0.0')
    declare_z = DeclareLaunchArgument('z_pose', default_value='0.15')

    use_rviz = LaunchConfiguration('use_rviz')
    x_pose   = LaunchConfiguration('x_pose')
    y_pose   = LaunchConfiguration('y_pose')
    z_pose   = LaunchConfiguration('z_pose')

    # ── robot_description from XACRO ────────────────────────────
    robot_description_content = Command([
        FindExecutable(name='xacro'), ' ', xacro_file,
    ])
    robot_description = {'robot_description': robot_description_content}

    # ── Robot State Publisher ────────────────────────────────────
    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[robot_description, {'publish_frequency': 50.0}],
    )

    # ── Gazebo (ros_gz_sim for Jazzy) ────────────────────────────
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            PathJoinSubstitution([
                FindPackageShare('ros_gz_sim'),
                'launch', 'gz_sim.launch.py',
            ])
        ]),
        launch_arguments={'gz_args': '-r empty.sdf'}.items(),
    )

    # ── Spawn robot into Gazebo ──────────────────────────────────
    spawn_entity = Node(
        package='ros_gz_sim',
        executable='create',
        name='spawn_lab_robot',
        arguments=[
            '-name',  'lab_assistant_robot',
            '-topic', 'robot_description',
            '-x', x_pose,
            '-y', y_pose,
            '-z', z_pose,
        ],
        output='screen',
    )

    # ── ros2_control spawners ────────────────────────────────────
    #   Spawned AFTER the robot entity is ready in Gazebo
    def make_controller_spawner(controller_name):
        return Node(
            package='controller_manager',
            executable='spawner',
            arguments=[controller_name],
            output='screen',
        )

    joint_state_broadcaster = make_controller_spawner(
        'joint_state_broadcaster')
    fl_controller = make_controller_spawner(
        'fl_wheel_velocity_controller')
    fr_controller = make_controller_spawner(
        'fr_wheel_velocity_controller')
    rl_controller = make_controller_spawner(
        'rl_wheel_velocity_controller')
    rr_controller = make_controller_spawner(
        'rr_wheel_velocity_controller')

    # Wait for spawn to finish before spawning controllers
    load_controllers = RegisterEventHandler(
        event_handler=OnProcessExit(
            target_action=spawn_entity,
            on_exit=[
                TimerAction(period=2.0, actions=[
                    joint_state_broadcaster,
                    fl_controller,
                    fr_controller,
                    rl_controller,
                    rr_controller,
                ])
            ],
        )
    )

    # ── RViz2 ────────────────────────────────────────────────────
    rviz2_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', rviz_config],
        parameters=[robot_description],
        condition=IfCondition(use_rviz),
    )

    return LaunchDescription([
        declare_use_rviz,
        declare_world,
        declare_x, declare_y, declare_z,

        LogInfo(msg='\n[lab_robot] Starting Gazebo simulation...'),

        robot_state_publisher_node,
        gazebo,
        spawn_entity,
        load_controllers,

        TimerAction(period=3.0, actions=[rviz2_node]),
    ])