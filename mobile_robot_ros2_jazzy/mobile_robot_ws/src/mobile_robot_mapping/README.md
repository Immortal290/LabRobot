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
