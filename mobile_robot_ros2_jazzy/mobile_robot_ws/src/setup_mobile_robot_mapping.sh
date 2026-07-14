#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
#  setup_mobile_robot_mapping.sh
#  Recreates the full `mobile_robot_mapping` ROS 2 package (no-IMU SLAM stack:
#  wheel encoders + YDLIDAR X2 + rf2o laser odometry + EKF + slam_toolbox,
#  plus a GIMP batch-mode map cleanup tool).
#
#  USAGE:
#    Run this from inside your ROS 2 workspace's `src` directory:
#      cd ~/mobile_robot_ros2_jazzy/mobile_robot_ws/src
#      bash setup_mobile_robot_mapping.sh
#
#  This creates ./mobile_robot_mapping/ alongside your existing `mobile_robot`
#  package. It does NOT touch your existing URDF, controllers, or bringup —
#  wire those in per the notes in the generated README.md.
# ═══════════════════════════════════════════════════════════════════════════
set -e

PKG_DIR="mobile_robot_mapping"
mkdir -p "$PKG_DIR/config" "$PKG_DIR/launch" "$PKG_DIR/rviz" "$PKG_DIR/scripts"

echo "Creating $PKG_DIR/package.xml ..."
cat > "$PKG_DIR/package.xml" << 'EOF'
<?xml version="1.0"?>
<?xml-model href="http://download.ros.org/schema/package_format3.xsd" schematypens="http://www.w3.org/2001/XMLSchema"?>
<package format="3">
  <name>mobile_robot_mapping</name>
  <version>1.0.0</version>
  <description>
    No-IMU SLAM mapping stack for AURA mobile robot: wheel encoders + YDLIDAR X2,
    fused via robot_localization EKF with rf2o laser odometry, filtered scans,
    and slam_toolbox online async mapping.
  </description>
  <maintainer email="lab@aura.local">AURA Lab</maintainer>
  <license>Apache-2.0</license>

  <buildtool_depend>ament_cmake</buildtool_depend>

  <exec_depend>robot_localization</exec_depend>
  <exec_depend>slam_toolbox</exec_depend>
  <exec_depend>rf2o_laser_odometry</exec_depend>
  <exec_depend>laser_filters</exec_depend>
  <exec_depend>ydlidar_ros2_driver</exec_depend>
  <exec_depend>tf2_ros</exec_depend>
  <exec_depend>rviz2</exec_depend>
  <exec_depend>launch</exec_depend>
  <exec_depend>launch_ros</exec_depend>

  <export>
    <build_type>ament_cmake</build_type>
  </export>
</package>
EOF

echo "Creating $PKG_DIR/CMakeLists.txt ..."
cat > "$PKG_DIR/CMakeLists.txt" << 'EOF'
cmake_minimum_required(VERSION 3.8)
project(mobile_robot_mapping)

find_package(ament_cmake REQUIRED)

install(DIRECTORY
  launch
  config
  rviz
  DESTINATION share/${PROJECT_NAME}
)

install(PROGRAMS
  scripts/check_odom_calibration.py
  scripts/gimp_clean_map.sh
  DESTINATION lib/${PROJECT_NAME}
)

# Install scripts into the share directory too, or just install them as programs.
# Let's keep them matching CMake install patterns.
install(FILES
  scripts/gimp_clean_map.scm
  DESTINATION share/${PROJECT_NAME}/scripts
)

ament_package()
EOF

echo "Creating $PKG_DIR/config/ekf.yaml ..."
cat > "$PKG_DIR/config/ekf.yaml" << 'EOF'
# ═══════════════════════════════════════════════════════════════════════════
#  ekf.yaml — Dual odometry fusion, NO IMU
#  Input 0: /wheel_odom      → owns translation (vx)
#  Input 1: /rf2o_odom       → owns rotation (yaw, vyaw) — slip independent
#  ROS 2 Jazzy | AURA Mobile Robot
# ═══════════════════════════════════════════════════════════════════════════

ekf_filter_node:
  ros__parameters:
    frequency: 30.0
    sensor_timeout: 0.1
    two_d_mode: true
    transform_time_offset: 0.0
    transform_timeout: 0.05
    print_diagnostics: true
    debug: false
    use_sim_time: false

    # ── TF Frames ────────────────────────────────────────────────────────────
    map_frame: map
    odom_frame: odom
    base_link_frame: base_footprint
    world_frame: odom
    publish_tf: true
    publish_acceleration: false

    # ── Input 0 — Wheel Odometry: trust for stable forward velocity only ────
    # x/y pose not fused (avoids baking in slip-caused position drift directly;
    # position still gets integrated correctly by the EKF from fused velocity).
    # yaw/vyaw NOT fused here anymore — rf2o owns heading instead.
    odom0: /wheel_odom
    odom0_config:
      - [false, false, false,
         false, false, false,
         true,  false, false,
         false, false, false]
    odom0_queue_size: 10
    odom0_nodelay: true
    odom0_differential: false
    odom0_relative: false
    odom0_pose_rejection_threshold: 5.0
    odom0_twist_rejection_threshold: 1.0

    # ── Input 1 — rf2o LIDAR Odometry: owns yaw (slip-independent) ──────────
    # rf2o_differential=true because rf2o's absolute pose output drifts over
    # a full session, but its relative (scan-to-scan) motion is accurate —
    # so we only trust the *change* in its pose estimate, not its raw value.
    odom1: /rf2o_odom
    odom1_config:
      - [false, false, false,
         false, false, true,
         false, false, false,
         false, false, true]
    odom1_queue_size: 10
    odom1_nodelay: true
    odom1_differential: true
    odom1_relative: false
    odom1_pose_rejection_threshold: 3.0
    odom1_twist_rejection_threshold: 0.8
EOF

echo "Creating $PKG_DIR/config/slam_toolbox_real.yaml ..."
cat > "$PKG_DIR/config/slam_toolbox_real.yaml" << 'EOF'
# ═══════════════════════════════════════════════════════════════════════════
#  slam_toolbox_real.yaml — SLAM Toolbox, no-IMU wheel+LIDAR setup
#  Sensor: YDLIDAR X2 (filtered) | Odometry: EKF-fused wheel + rf2o laser odom
#  ROS 2 Jazzy | AURA Mobile Robot
#
#  PHASE 1 — MAPPING
#    ros2 launch mobile_robot_mapping real_slam_mapping.launch.py
#    → Drive slowly, gentle arcs, loop back through mapped areas often
#    → ros2 service call /slam_toolbox/save_map \
#        slam_toolbox/srv/SaveMap "{name: {data: 'lab_map'}}"
# ═══════════════════════════════════════════════════════════════════════════

slam_toolbox:
  ros__parameters:

    mode: mapping
    use_sim_time: false
    debug_logging: false

    odom_frame: odom
    map_frame: map
    base_frame: base_footprint

    scan_topic: /scan            # this is the FILTERED scan (see laser_filter.yaml)
    throttle_scans: 1

    tf_buffer_duration: 30.0
    transform_timeout: 0.5

    map_update_interval: 3.0
    map_file_name: ''
    map_start_at_dock: false
    map_start_pose: [0.0, 0.0, 0.0]

    resolution: 0.05
    max_laser_range: 8.0         # matches laser_filter.yaml upper_threshold

    # Tighter than stock defaults — catches drift sooner since we have no IMU
    minimum_travel_distance: 0.08
    minimum_travel_heading: 0.08

    use_scan_matching: true
    use_scan_bagging: false
    minimum_score_for_scan_matching: 0.65   # raised from default 0.5 — reject weak matches

    correlation_search_space_dimension: 0.7       # widened — compensates for no-IMU uncertainty
    correlation_search_space_resolution: 0.01
    correlation_search_space_smear_deviation: 0.15

    do_loop_closing: true
    loop_search_max_linear_distance: 5.0
    loop_search_max_angular_distance: 0.524
    loop_match_minimum_chain_size: 10
    loop_match_maximum_variance_coarse: 3.0
    loop_match_minimum_response_coarse: 0.35
    loop_match_minimum_response_fine: 0.45

    publish_pose_graph: true
EOF

echo "Creating $PKG_DIR/config/laser_filter.yaml ..."
cat > "$PKG_DIR/config/laser_filter.yaml" << 'EOF'
# ═══════════════════════════════════════════════════════════════════════════
#  laser_filter.yaml — cleans YDLIDAR X2 raw scans BEFORE slam_toolbox / rf2o
#  Subscribes:  /scan_raw   (direct output of the YDLIDAR driver)
#  Publishes:   /scan       (what slam_toolbox and rf2o_laser_odometry consume)
# ═══════════════════════════════════════════════════════════════════════════

scan_filter_chain:
  - name: shadows
    type: laser_filters/ScanShadowsFilter
    params:
      min_angle: 10.0
      max_angle: 170.0
      neighbors: 1
      window: 1

  - name: speckle
    type: laser_filters/SpeckleFilter
    params:
      max_range: 8.0
      max_range_difference: 0.1
      filter_window: 2

  - name: range
    type: laser_filters/LaserScanRangeFilter
    params:
      lower_threshold: 0.15    # strips self-detection noise near the sensor body
      upper_threshold: 8.0     # X2 spec is 10m but readings near max are unreliable indoors
EOF

echo "Creating $PKG_DIR/config/rf2o_params.yaml ..."
cat > "$PKG_DIR/config/rf2o_params.yaml" << 'EOF'
# ═══════════════════════════════════════════════════════════════════════════
#  rf2o_params.yaml — LIDAR-only odometry, feeds EKF as odom1 (yaw source)
#  Scan-to-scan matching estimate — independent of wheel slip entirely.
# ═══════════════════════════════════════════════════════════════════════════

rf2o_laser_odometry:
  ros__parameters:
    laser_scan_topic: /scan          # filtered scan
    odom_topic: /rf2o_odom
    publish_tf: false                # EKF owns odom->base_footprint TF, not rf2o
    base_frame_id: base_footprint
    odom_frame_id: odom
    init_pose_from_topic: ''
    freq: 20.0
EOF

echo "Creating $PKG_DIR/launch/real_slam_mapping.launch.py ..."
cat > "$PKG_DIR/launch/real_slam_mapping.launch.py" << 'EOF'
#!/usr/bin/env python3
"""
real_slam_mapping.launch.py
────────────────────────────────────────────────────────────────────────────
No-IMU mapping pipeline for AURA mobile robot.

    YDLIDAR X2  ──/scan_raw──►  laser_filters  ──/scan──┬──► rf2o_laser_odometry ──/rf2o_odom──┐
                                                          │                                      │
                                                          └──────────────────► slam_toolbox      │
                                                                                     ▲            │
                        /wheel_odom ─────────────────────────────────────────────►  EKF  ◄────────┘
                                                                                     │
                                                                          odom -> base_footprint TF

PREREQUISITES (from your existing robot bringup — NOT started by this file):
  - robot_state_publisher / URDF publishing base_footprint -> laser static TF
  - Your diff-drive controller / wheel odometry node publishing /wheel_odom
  - YDLIDAR ROS2 driver publishing raw scans

    This launch file assumes your existing bringup publishes raw scans on
    /scan_raw. If your YDLIDAR driver currently publishes directly to /scan,
    either remap its output to /scan_raw in your existing bringup launch, or
    edit the remapping in the `laser_filter_node` action below.

USAGE:
    ros2 launch mobile_robot_mapping real_slam_mapping.launch.py

    # then drive the robot slowly with teleop, loop back through mapped
    # areas periodically, and when done:
    ros2 service call /slam_toolbox/save_map \\
        slam_toolbox/srv/SaveMap "{name: {data: 'lab_map'}}"
────────────────────────────────────────────────────────────────────────────
"""

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.substitutions import LaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    pkg_share = get_package_share_directory('mobile_robot_mapping')

    ekf_yaml = os.path.join(pkg_share, 'config', 'ekf.yaml')
    slam_yaml = os.path.join(pkg_share, 'config', 'slam_toolbox_real.yaml')
    laser_filter_yaml = os.path.join(pkg_share, 'config', 'laser_filter.yaml')
    rf2o_yaml = os.path.join(pkg_share, 'config', 'rf2o_params.yaml')
    rviz_config = os.path.join(pkg_share, 'rviz', 'mapping.rviz')

    use_sim_time = LaunchConfiguration('use_sim_time', default='false')
    start_rviz = LaunchConfiguration('start_rviz', default='true')

    declare_use_sim_time = DeclareLaunchArgument(
        'use_sim_time', default_value='false',
        description='Use simulation clock (false for real hardware)')

    declare_start_rviz = DeclareLaunchArgument(
        'start_rviz', default_value='true',
        description='Whether to launch RViz alongside the mapping stack')

    # ── 1. Laser filter chain: /scan_raw -> /scan ───────────────────────────
    laser_filter_node = Node(
        package='laser_filters',
        executable='scan_to_scan_filter_chain',
        name='scan_filter_chain',
        output='screen',
        parameters=[laser_filter_yaml],
        remappings=[
            ('scan', '/scan_raw'),
            ('scan_filtered', '/scan'),
        ],
    )

    # ── 2. rf2o LIDAR odometry: /scan -> /rf2o_odom ─────────────────────────
    rf2o_node = Node(
        package='rf2o_laser_odometry',
        executable='rf2o_laser_odometry_node',
        name='rf2o_laser_odometry',
        output='screen',
        parameters=[rf2o_yaml],
    )

    # ── 3. EKF: fuses /wheel_odom (translation) + /rf2o_odom (yaw) ──────────
    ekf_node = Node(
        package='robot_localization',
        executable='ekf_node',
        name='ekf_filter_node',
        output='screen',
        parameters=[ekf_yaml, {'use_sim_time': use_sim_time}],
    )

    # ── 4. slam_toolbox — online async mapping ──────────────────────────────
    slam_toolbox_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory('slam_toolbox'),
                'launch',
                'online_async_launch.py'
            )
        ),
        launch_arguments={
            'slam_params_file': slam_yaml,
            'use_sim_time': use_sim_time,
        }.items(),
    )

    from launch.conditions import IfCondition

    # ── 5. RViz (optional) ───────────────────────────────────────────────────
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', rviz_config],
        condition=IfCondition(start_rviz),
    )

    return LaunchDescription([
        declare_use_sim_time,
        declare_start_rviz,
        laser_filter_node,
        rf2o_node,
        ekf_node,
        slam_toolbox_launch,
        rviz_node,
    ])
EOF

echo "Creating $PKG_DIR/rviz/mapping.rviz ..."
cat > "$PKG_DIR/rviz/mapping.rviz" << 'EOF'
Panels:
  - Class: rviz_common/Displays
    Name: Displays
  - Class: rviz_common/Views
    Name: Views
Visualization Manager:
  Class: ""
  Displays:
    - Class: rviz_default_plugins/Grid
      Name: Grid
      Enabled: true
    - Class: rviz_default_plugins/TF
      Name: TF
      Enabled: true
    - Class: rviz_default_plugins/LaserScan
      Name: LaserScan (filtered)
      Topic:
        Value: /scan
      Enabled: true
      Size (m): 0.03
      Color: 255; 0; 0
    - Class: rviz_default_plugins/Map
      Name: Map
      Topic:
        Value: /map
      Enabled: true
    - Class: rviz_default_plugins/MarkerArray
      Name: SLAM Pose Graph
      Topic:
        Value: /slam_toolbox/graph_visualization
      Enabled: true
    - Class: rviz_default_plugins/Odometry
      Name: Wheel Odom
      Topic:
        Value: /wheel_odom
      Enabled: false
    - Class: rviz_default_plugins/Odometry
      Name: rf2o Odom
      Topic:
        Value: /rf2o_odom
      Enabled: false
  Global Options:
    Fixed Frame: map
  Views:
    Current:
      Class: rviz_default_plugins/Orbit
      Distance: 10
      Pitch: 0.9
EOF

echo "Creating $PKG_DIR/scripts/check_odom_calibration.py ..."
cat > "$PKG_DIR/scripts/check_odom_calibration.py" << 'EOF'
#!/usr/bin/env python3
"""
check_odom_calibration.py
────────────────────────────────────────────────────────────────────────────
Live comparison tool for calibrating wheel odometry.

Prints side-by-side distance and heading reported by /wheel_odom and
/rf2o_odom so you can:
  1. Drive exactly N metres in a straight line and compare reported distance
     to your tape-measured ground truth -> adjust wheel_radius.
  2. Rotate exactly 360 degrees and compare reported heading change to a
     protractor/floor-marked ground truth -> adjust wheel_separation.
  3. Cross-check wheel_odom against rf2o_odom directly -- large persistent
     disagreement between the two usually means wheel slip or a wheel
     calibration error, since rf2o is slip-independent.

USAGE:
    ros2 run mobile_robot_mapping check_odom_calibration.py
────────────────────────────────────────────────────────────────────────────
"""

import math
import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry


def yaw_from_quaternion(q):
    siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny_cosp, cosy_cosp)


class OdomCalibrationChecker(Node):
    def __init__(self):
        super().__init__('check_odom_calibration')

        self.wheel_start = None
        self.rf2o_start = None
        self.wheel_last = None
        self.rf2o_last = None

        self.create_subscription(Odometry, '/wheel_odom', self.wheel_cb, 10)
        self.create_subscription(Odometry, '/rf2o_odom', self.rf2o_cb, 10)
        self.create_timer(1.0, self.report)

        self.get_logger().info(
            'Listening on /wheel_odom and /rf2o_odom. '
            'Drive a known distance or rotate a known angle and compare.'
        )

    def wheel_cb(self, msg):
        pos = msg.pose.pose.position
        yaw = yaw_from_quaternion(msg.pose.pose.orientation)
        self.wheel_last = (pos.x, pos.y, yaw)
        if self.wheel_start is None:
            self.wheel_start = self.wheel_last

    def rf2o_cb(self, msg):
        pos = msg.pose.pose.position
        yaw = yaw_from_quaternion(msg.pose.pose.orientation)
        self.rf2o_last = (pos.x, pos.y, yaw)
        if self.rf2o_start is None:
            self.rf2o_start = self.rf2o_last

    def report(self):
        if not self.wheel_last or not self.rf2o_last:
            self.get_logger().warn('Waiting for both /wheel_odom and /rf2o_odom...')
            return

        wx0, wy0, wyaw0 = self.wheel_start
        wx, wy, wyaw = self.wheel_last
        wheel_dist = math.hypot(wx - wx0, wy - wy0)
        wheel_yaw_deg = math.degrees(wyaw - wyaw0)

        rx0, ry0, ryaw0 = self.rf2o_start
        rx, ry, ryaw = self.rf2o_last
        rf2o_dist = math.hypot(rx - rx0, ry - ry0)
        rf2o_yaw_deg = math.degrees(ryaw - ryaw0)

        print('─' * 60)
        print(f'  wheel_odom : dist={wheel_dist:6.3f} m   yaw={wheel_yaw_deg:7.2f} deg')
        print(f'  rf2o_odom  : dist={rf2o_dist:6.3f} m   yaw={rf2o_yaw_deg:7.2f} deg')
        print(f'  yaw disagreement: {abs(wheel_yaw_deg - rf2o_yaw_deg):.2f} deg')


def main():
    rclpy.init()
    node = OdomCalibrationChecker()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
EOF

echo "Creating $PKG_DIR/scripts/gimp_clean_map.scm ..."
cat > "$PKG_DIR/scripts/gimp_clean_map.scm" << 'EOF'
; ═══════════════════════════════════════════════════════════════════════════
;  gimp_clean_map.scm — GIMP Script-Fu batch procedure for cleaning a
;  slam_toolbox / map_saver occupancy grid PGM.
;
;  What it does, in order:
;    1. Loads the map, forces grayscale
;    2. Despeckle (median-based) — removes salt-and-pepper noise: isolated
;       stray black pixels in free space, isolated white specks in walls
;    3. Re-quantizes every pixel to exactly ONE of the three canonical
;       occupancy-grid values:
;         0   = occupied (black)
;         205 = unknown  (gray)
;         254 = free     (white)
;       This is the important step GIMP's normal filters don't do on their
;       own — despeckling/blurring alone leaves semi-gray edge pixels, which
;       map_server / nav2 can misread as fractional occupancy probability
;       instead of a clean binary/unknown map.
;    4. Saves as a raw PGM (P5) — the format ROS map_server expects.
;
;  Not called directly — invoked via gimp_clean_map.sh, which passes in the
;  file paths and tuning parameters.
; ═══════════════════════════════════════════════════════════════════════════

(define (clean-map-batch infile outfile despeckle-radius black-cutoff white-cutoff)
  (let* ((image    (car (gimp-file-load RUN-NONINTERACTIVE infile infile)))
         (drawable (car (gimp-image-get-active-drawable image))))

    ; ── 1. Force grayscale ──────────────────────────────────────────────────
    (if (not (= (car (gimp-image-base-type image)) GRAY))
        (gimp-image-convert-grayscale image))
    (set! drawable (car (gimp-image-get-active-drawable image)))

    ; ── 2. Despeckle — median-based speckle/salt-and-pepper removal ────────
    ; type=1 (recursive median) gives stronger cleanup on scattered LIDAR
    ; noise than a single pass; radius controls how large a speckle cluster
    ; gets removed vs preserved as real geometry.
    (plug-in-despeckle RUN-NONINTERACTIVE image drawable
                        1                 ; DESPECKLE-RECURSIVE-MEDIAN
                        despeckle-radius
                        -1                ; black level (-1 = use full range)
                        256)              ; white level (256 = use full range)

    ; ── 3. Re-quantize to the 3 canonical occupancy-grid values ────────────
    ; Build a temporary indexed palette of exactly {0, 205, 254} and force
    ; every pixel to snap to its nearest entry — this both cleans up
    ; despeckle's soft edges AND guarantees map_server reads it correctly.
    (let* ((pal (car (gimp-palette-new "ros_map_cleanup_palette"))))
      (gimp-palette-add-entry pal "occupied" '(0 0 0))
      (gimp-palette-add-entry pal "unknown"  '(205 205 205))
      (gimp-palette-add-entry pal "free"     '(254 254 254))
      (gimp-image-convert-indexed image
                                   NO-DITHER
                                   CUSTOM-PALETTE
                                   3        ; num colors (ignored for custom)
                                   FALSE    ; alpha-dither
                                   FALSE    ; remove-unused
                                   "ros_map_cleanup_palette")))
    (gimp-image-convert-grayscale image)
    (gimp-image-flatten image)
    (set! drawable (car (gimp-image-get-active-drawable image)))

    ; ── 4. Save as raw PGM (P5) ─────────────────────────────────────────────
    (file-pnm-save RUN-NONINTERACTIVE image drawable outfile outfile 1)

    (gimp-image-delete image)))
EOF

echo "Creating $PKG_DIR/scripts/gimp_clean_map.sh ..."
cat > "$PKG_DIR/scripts/gimp_clean_map.sh" << 'EOF'
#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
#  gimp_clean_map.sh — despeckle + re-quantize a saved SLAM map, no GUI.
#
#  USAGE:
#    ./gimp_clean_map.sh <input_map.pgm> <output_map_clean.pgm> \
#                         [despeckle_radius] [black_cutoff] [white_cutoff]
#
#  EXAMPLE:
#    ./gimp_clean_map.sh maps/lab_map.pgm maps/lab_map_clean.pgm 2
#
#  Also copies/updates the paired .yaml so the cleaned map is immediately
#  usable with Nav2 (image: field repointed to the new filename; resolution,
#  origin, thresholds all carried over unchanged).
#
#  REQUIRES: GIMP installed with Script-Fu (standard on any GIMP install).
#    sudo apt install gimp
# ═══════════════════════════════════════════════════════════════════════════
set -e

if [ -z "$1" ] || [ -z "$2" ]; then
  echo "Usage: $0 <input_map.pgm> <output_map_clean.pgm> [despeckle_radius] [black_cutoff] [white_cutoff]"
  exit 1
fi

IN="$1"
OUT="$2"
RADIUS="${3:-2}"      # despeckle radius in px — raise if noise is coarser, lower to preserve fine detail
BLACK="${4:--1}"      # -1 = use full range (see .scm comments)
WHITE="${5:-256}"     # 256 = use full range

if [ ! -f "$IN" ]; then
  echo "ERROR: input map not found: $IN"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/gimp_clean_map.scm" ]; then
  SCM_FILE="$SCRIPT_DIR/gimp_clean_map.scm"
elif [ -f "$SCRIPT_DIR/../../share/mobile_robot_mapping/scripts/gimp_clean_map.scm" ]; then
  SCM_FILE="$SCRIPT_DIR/../../share/mobile_robot_mapping/scripts/gimp_clean_map.scm"
else
  echo "ERROR: gimp_clean_map.scm not found!"
  exit 1
fi

echo "Running GIMP batch cleanup on: $IN"
echo "  despeckle_radius=$RADIUS"

gimp -i -b "(load \"$SCM_FILE\") (clean-map-batch \"$IN\" \"$OUT\" $RADIUS $BLACK $WHITE) (gimp-quit 0)"

echo "Cleaned map written to: $OUT"

# ── Keep the paired YAML in sync ────────────────────────────────────────────
YAML_IN="${IN%.*}.yaml"
YAML_OUT="${OUT%.*}.yaml"

if [ -f "$YAML_IN" ]; then
  sed "s#image: .*#image: $(basename "$OUT")#" "$YAML_IN" > "$YAML_OUT"
  echo "Updated YAML written to: $YAML_OUT (image: field repointed to $(basename "$OUT"))"
else
  echo "WARNING: no paired YAML found at $YAML_IN — copy/edit one manually before using this map in Nav2."
fi

echo ""
echo "Tip: open both $IN and $OUT side by side in an image viewer before"
echo "trusting the cleaned version — over-aggressive despeckling can erase"
echo "thin real features (doorways, chair/table legs) along with noise."
EOF

echo "Creating $PKG_DIR/README.md ..."
cat > "$PKG_DIR/README.md" << 'EOF'
# mobile_robot_mapping

No-IMU SLAM mapping stack for the AURA mobile robot: **wheel encoders + YDLIDAR X2 only**.

Fixes map distortion/smearing by:
1. Filtering LIDAR noise before it reaches SLAM (`laser_filters`)
2. Adding LIDAR-based odometry (`rf2o_laser_odometry`) as a slip-independent yaw source
3. Fusing wheel odometry (translation) + rf2o odometry (rotation) in `robot_localization`'s EKF
4. Tuning `slam_toolbox` to trust scan matching more and reject weak matches

```
YDLIDAR X2 ──/scan_raw──► laser_filters ──/scan──┬──► rf2o_laser_odometry ──/rf2o_odom──┐
                                                   │                                      │
                                                   └────────────────────► slam_toolbox    │
                                                                                ▲          │
                     /wheel_odom ────────────────────────────────────────►  EKF ◄─────────┘
                                                                                │
                                                                  odom → base_footprint TF
```

## Repo layout

```
mobile_robot_mapping/
├── package.xml
├── CMakeLists.txt
├── config/
│   ├── ekf.yaml              # dual odometry fusion (wheel=translation, rf2o=yaw)
│   ├── slam_toolbox_real.yaml
│   ├── laser_filter.yaml     # shadow/speckle/range filtering for YDLIDAR X2
│   └── rf2o_params.yaml
├── launch/
│   └── real_slam_mapping.launch.py
├── rviz/
│   └── mapping.rviz
└── scripts/
    ├── check_odom_calibration.py   # live wheel vs. lidar odometry comparison tool
    ├── gimp_clean_map.sh           # batch-mode map noise cleanup wrapper
    └── gimp_clean_map.scm          # GIMP Script-Fu procedure it calls
```

## Prerequisites (from your existing robot bringup)

This package does **not** start these — they should already be running from your
existing `mobile_robot` bringup:
- `robot_state_publisher` publishing the URDF, including the static
  `base_footprint → laser` transform (must match your physical LIDAR mount exactly)
- Your diff-drive controller / wheel odometry node publishing `/wheel_odom`
- The YDLIDAR ROS2 driver

**Important:** this launch file expects the raw LIDAR driver to publish on
`/scan_raw`, not `/scan`. Either:
- remap your existing YDLIDAR driver's output topic to `/scan_raw`, or
- edit the `remappings` in `launch/real_slam_mapping.launch.py`'s `laser_filter_node` to match your actual raw topic name.

## Install

```bash
# System dependencies
sudo apt install ros-jazzy-robot-localization ros-jazzy-slam-toolbox \
                 ros-jazzy-laser-filters

# rf2o_laser_odometry is not always in apt for Jazzy — build from source if needed:
cd ~/mobile_robot_ws/src
git clone https://github.com/MAPIRlab/rf2o_laser_odometry.git

# Place this package alongside your existing mobile_robot package
cp -r mobile_robot_mapping ~/mobile_robot_ws/src/

cd ~/mobile_robot_ws
colcon build --packages-select mobile_robot_mapping rf2o_laser_odometry
source install/setup.bash
```

## One-time calibration (do this before your first real mapping run)

Accurate odometry matters more than any YAML tuning. Do this once:

1. **Wheel radius** — drive exactly 3 m in a straight line (tape measure),
   compare against `/wheel_odom` reported distance. Adjust `wheel_radius` in
   your diff-drive controller config proportionally.

2. **Wheel separation (track width)** — rotate exactly 360° in place
   (protractor or floor marking as ground truth), compare against
   `/wheel_odom` reported heading change. Adjust `wheel_separation` until
   within ~1–2°.

3. **Cross-check with the LIDAR odometry** using the included tool — large,
   persistent disagreement between the two usually means wheel slip or a
   miscalibrated wheel parameter, since `rf2o` doesn't depend on wheel contact
   at all:
   ```bash
   ros2 run mobile_robot_mapping check_odom_calibration.py
   ```
   Drive/rotate known amounts and watch the printed comparison.

4. **Verify the LIDAR mount TF** matches physical reality:
   ```bash
   ros2 run tf2_ros tf2_echo base_footprint laser
   ```
   Even 2–3° of yaw error here will smear every single scan.

## Run

```bash
ros2 launch mobile_robot_mapping real_slam_mapping.launch.py
```

Then drive with teleop:
- Keep speed low: ≤0.15 m/s linear, ≤0.3 rad/s angular
- Use gentle arcing turns rather than in-place spins
- Loop back through already-mapped areas every 1–2 minutes so
  `do_loop_closing` can snap out accumulated drift
- Avoid long feature-sparse open areas without revisiting them
- Watch the `SLAM Pose Graph` markers in RViz — visible kinks at a location
  mean you should pause and re-traverse that area slowly

## Save the map

```bash
ros2 service call /slam_toolbox/save_map \
  slam_toolbox/srv/SaveMap "{name: {data: 'lab_map'}}"
```

This writes `lab_map.pgm` + `lab_map.yaml` for use with Nav2.

To resume a mapping session later instead of starting fresh:
```bash
ros2 service call /slam_toolbox/serialize_map \
  slam_toolbox/srv/SerializePoseGraph \
  "{filename: {data: '/path/to/lab_map'}}"
```
and set `map_file_name` in `slam_toolbox_real.yaml` to that path.

## Post-processing: cleaning the saved map in GIMP

Even with good calibration and loop closure, a saved map often still has
small speckle noise (isolated stray pixels from LIDAR outliers) and soft
gray edges. `scripts/gimp_clean_map.sh` runs GIMP in **batch mode** (no GUI,
scriptable) to clean this up automatically:

1. Despeckles the image (removes isolated stray black/white pixels)
2. Re-quantizes every pixel to exactly one of the three values map_server
   expects: `0` (occupied), `205` (unknown), `254` (free) — this matters
   because despeckling/blurring alone leaves semi-gray edge pixels that
   Nav2 can misread as fractional occupancy probability instead of a clean
   binary map
3. Saves as a raw PGM and updates the paired `.yaml` to point at the new file

```bash
sudo apt install gimp   # if not already installed

./scripts/gimp_clean_map.sh maps/lab_map.pgm maps/lab_map_clean.pgm
```

Optional third argument tunes despeckle strength (default `2`):
```bash
./scripts/gimp_clean_map.sh maps/lab_map.pgm maps/lab_map_clean.pgm 3
```
Higher radius removes more noise but risks erasing thin real features
(doorways, table/chair legs, narrow gaps). **Always compare the cleaned
map against the original before using it** — open both `.pgm` files side
by side in an image viewer, or in RViz with the `Map` display pointed at
each `.yaml` in turn.

Then use the cleaned map for navigation:
```bash
ros2 launch mobile_robot_mapping real_robot_nav.launch.py \
    use_slam:=false map_yaml:=/path/to/maps/lab_map_clean.yaml
```

## Tuning notes

| Symptom | Likely cause | Fix |
|---|---|---|
| Walls doubled/smeared at an angle | Yaw drift | Recheck wheel separation calibration; confirm rf2o is actually being fused (check `odom1` in ekf.yaml is receiving data) |
| Fuzzy/speckled walls even when stationary | Raw LIDAR noise | Tighten `laser_filter.yaml` speckle/shadow params |
| Map fine in corridors, bad in open rooms | Weak scan matching (few features) | Lower `minimum_score_for_scan_matching` slightly, or deliberately loop through the open area more |
| EKF rejecting most odometry updates | Rejection thresholds too tight, or one source is very noisy | Check `ros2 topic hz /wheel_odom /rf2o_odom`, loosen `*_rejection_threshold` temporarily to diagnose |

## Realistic expectations

Wheel + LIDAR-only mapping (no IMU) works well for small-to-medium indoor
spaces with careful calibration and disciplined driving (slow, frequent loop
closure). Large open areas or fast/aggressive driving will still show more
drift than an IMU-equipped setup — that's a fundamental limitation of this
sensor combination, not a tuning problem.
EOF

chmod +x "$PKG_DIR/scripts/check_odom_calibration.py" "$PKG_DIR/scripts/gimp_clean_map.sh"

echo ""
echo "════════════════════════════════════════════════════════════════════"
echo " Done. Package created at: $(pwd)/$PKG_DIR"
echo ""
echo " NEXT STEPS:"
echo "  1. Wire /scan_raw, /wheel_odom topics and the base_footprint->laser"
echo "     static TF from YOUR existing URDF/bringup (see README.md)."
echo "  2. Install deps:"
echo "     sudo apt install ros-jazzy-robot-localization ros-jazzy-slam-toolbox ros-jazzy-laser-filters gimp"
echo "     git clone https://github.com/MAPIRlab/rf2o_laser_odometry.git   # if not in apt"
echo "  3. cd .. && colcon build --packages-select mobile_robot_mapping rf2o_laser_odometry"
echo "  4. source install/setup.bash"
echo "  5. ros2 launch mobile_robot_mapping real_slam_mapping.launch.py"
echo "  6. After saving a map: ./mobile_robot_mapping/scripts/gimp_clean_map.sh maps/lab_map.pgm maps/lab_map_clean.pgm"
echo "════════════════════════════════════════════════════════════════════"
