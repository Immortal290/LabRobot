"""
camera_rviz.launch.py
---------------------
Starts the real USB camera (/dev/video0) and opens RViz2 with a live feed.

Known usb_cam 0.8.1 quirks handled here:
  1. The 'camera_frame_id' parameter is ignored by usb_cam 0.8.1; it always
     uses camera_name as the TF frame_id in Image/CameraInfo headers.
     Solution: set camera_name='camera_link' so the frame IS 'camera_link'.

  2. usb_cam throws 'terminate called after throwing char*' from a background
     thread after successful init — this is a bug in the swscaler path but
     image streaming continues unaffected.

  3. Parameters MUST be passed as native Python types (int/float/str) in the
     parameters=[{...}] dict; using LaunchConfiguration objects causes the
     params-file to be written with wrong types that crash usb_cam's parser.

Usage:
  cd ~/Desktop/AURA/mobile_robot_ros2_jazzy/mobile_robot_ws
  source /opt/ros/jazzy/setup.bash && source install/setup.bash
  ros2 launch mobile_robot camera_rviz.launch.py
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():

    pkg_share = get_package_share_directory('mobile_robot')
    rviz_config = os.path.join(pkg_share, 'rviz', 'camera_view.rviz')

    # ── usb_cam node ──────────────────────────────────────────────────────────
    # IMPORTANT: set camera_name='camera_link' because usb_cam 0.8.1 uses
    # camera_name as the frame_id in Image headers (camera_frame_id is ignored)
    usb_cam_node = Node(
        package='usb_cam',
        executable='usb_cam_node_exe',
        name='usb_cam',
        output='screen',
        parameters=[{
            'video_device':    '/dev/video0',
            'image_width':     640,
            'image_height':    480,
            'framerate':       30.0,
            'pixel_format':    'mjpeg2rgb',
            # usb_cam 0.8.1 mjpeg2rgb path always publishes frame_id='default_cam'
            # regardless of camera_name/camera_frame_id parameters.
            # We match that by publishing a TF for 'default_cam' below.
            'camera_name':     'default_cam',
        }],
    )

    # ── Static TF: map → camera_link ─────────────────────────────────────────
    # usb_cam publishes frame_id='default_cam' in Image headers.
    # RViz Camera overlay needs a TF for that frame — publish map→default_cam.
    static_tf_node = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='camera_tf',
        output='screen',
        arguments=[
            '--x', '0', '--y', '0', '--z', '0',
            '--roll', '0', '--pitch', '0', '--yaw', '0',
            '--frame-id', 'map',
            '--child-frame-id', 'default_cam',
        ],
    )

    # ── RViz2 ─────────────────────────────────────────────────────────────────
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', rviz_config],
    )

    return LaunchDescription([
        usb_cam_node,
        static_tf_node,
        rviz_node,
    ])
