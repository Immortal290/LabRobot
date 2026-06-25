# Mobile Robot - Keyboard Teleop with LiDAR Visualization

## Quick Start: Move Robot with Keyboard + See LiDAR Scan

### Option 1: Combined Launch (Recommended)
Everything in one command:
```bash
cd ~/Desktop/AURA/mobile_robot_ros2_jazzy/mobile_robot_ws
source install/setup.bash
ros2 launch mobile_robot sim_with_teleop.launch.py
```

This will automatically launch:
- **Gazebo Harmonic** - full physics simulation
- **Robot** - spawned with differential drive control
- **LiDAR Sensor** - 360° laser scan at 10 Hz
- **Keyboard Teleop** - in a separate terminal window
- **RViz2** - showing robot model + laser scan visualization

### Option 2: Separate Terminals
If you prefer manual control:

**Terminal 1 - Gazebo simulation:**
```bash
cd ~/Desktop/AURA/mobile_robot_ros2_jazzy/mobile_robot_ws
source install/setup.bash
ros2 launch mobile_robot gazebo.launch.py
```

**Terminal 2 - Keyboard teleop (opens in xterm):**
```bash
source install/setup.bash
ros2 launch mobile_robot teleop.launch.py
```

---

## Keyboard Controls

In the teleop terminal window:

| Key | Action |
|-----|--------|
| **i** | Move forward |
| **,** (comma) | Move backward |
| **j** | Turn left |
| **l** | Turn right |
| **k** | Stop / Deadman (must hold for movement) |
| **u** | Forward-left diagonal |
| **o** | Forward-right diagonal |
| **m** | Backward-left diagonal |
| **.** | Backward-right diagonal |
| **q** | Increase max linear speed |
| **z** | Decrease max linear speed |
| **w** | Increase linear velocity |
| **x** | Decrease linear velocity |
| **e** | Increase angular velocity |
| **c** | Decrease angular velocity |

---

## RViz2 Visualization

The RViz2 window displays:
- **Robot Model** - URDF visualization (wooden kiosk)
- **LaserScan** - red/white points showing LiDAR measurements in 2D plane
- **Grid** - reference plane
- **TF Frames** - transform tree visualization
- **Odometry** - path trajectory of the robot

### LiDAR Specs (in simulation):
- **Range**: 0.12m - 12.0m
- **FOV**: 360° (horizontal)
- **Update Rate**: 10 Hz
- **Resolution**: 0.01m
- **Topic**: `/scan` (LaserScan format)

---

## Testing the Setup

### 1. Verify LiDAR is Publishing
```bash
# In a new terminal
source install/setup.bash
ros2 topic echo /scan --no-arr
```

You should see LaserScan messages with:
- header.frame_id: `laser_frame`
- ranges: array of 360 measurements
- angle_min/max: -π to π radians

### 2. Verify Robot is Moving
```bash
# In a new terminal
source install/setup.bash
ros2 topic echo /cmd_vel
```

When you press movement keys in teleop, you should see Twist messages with linear/angular velocities.

### 3. Check Robot TF Frames
```bash
ros2 run tf2_tools view_frames
# Opens frame_tree.pdf showing kinematic tree
```

---

## World Files

The simulation uses SDF world files in `worlds/`:
- `empty_world.sdf` - empty ground (default)
- Customize by adding obstacles, lights, etc.

Launch with a different world:
```bash
ros2 launch mobile_robot sim_with_teleop.launch.py world:=./src/mobile_robot/worlds/your_world.sdf
```

---

## Configuration Files

- **`config/ros2_controllers.yaml`** - Differential drive controller settings
  - Wheel names, radius, separation
  - Velocity/acceleration limits
  - Odometry frame settings

- **`config/ros_gz_bridge.yaml`** - Gazebo ↔ ROS topic bridges
  - `/scan` ← LiDAR (GZ to ROS)
  - `/cmd_vel` → robot (ROS to GZ)
  - `/odom`, `/imu/data`, `/camera/image_raw`

- **`urdf/gazebo.xacro`** - Gazebo sensor plugins
  - LiDAR ray-casting sensor
  - IMU sensor (gyro + accel)
  - Camera sensor
  - ros2_control interface

---

## Troubleshooting

### "Package 'teleop_twist_keyboard' not found"
```bash
sudo apt install ros-jazzy-teleop-twist-keyboard
```

### Keyboard teleop window doesn't appear
- Ensure `xterm` is installed: `sudo apt install xterm`
- Or modify teleop.launch.py to remove `prefix="xterm -e"`

### Robot doesn't move
1. Check that `/cmd_vel` is being published: `ros2 topic list`
2. Verify differential drive controller is loaded: `ros2 service call /controller_manager/list_controllers controller_manager_msgs/srv/ListControllers`
3. Check for errors in terminal output

### LiDAR scan not showing in RViz
1. Verify topic exists: `ros2 topic list | grep scan`
2. Check topic data: `ros2 topic echo /scan --no-arr`
3. In RViz, ensure LaserScan display is enabled
4. Check frame_id is correctly set to `laser_frame`

---

## Performance Notes

- **Gazebo simulation**: real-time (on modern hardware)
- **LiDAR update rate**: 10 Hz (configurable in `urdf/gazebo.xacro`)
- **ROS 2 control rate**: 50 Hz
- **RViz rendering**: 30 FPS (depends on GPU)

---

## Files Involved

```
mobile_robot/
├── launch/
│   ├── sim_with_teleop.launch.py  ← Use this for teleop + lidar
│   ├── gazebo.launch.py            ← Gazebo only
│   ├── teleop.launch.py            ← Teleop only
│   └── display.launch.py           ← Model viewer (no simulation)
├── urdf/
│   ├── mobile_robot.urdf.xacro
│   ├── gazebo.xacro                ← Sensor plugins
│   ├── macros.xacro
│   └── materials.xacro
├── config/
│   ├── ros2_controllers.yaml       ← Motor controller config
│   └── ros_gz_bridge.yaml          ← Topic bridges
├── rviz/
│   └── mobile_robot.rviz           ← RViz visualization config
└── worlds/
    └── empty_world.sdf             ← Gazebo world
```

---

## Next Steps

- Add obstacles to the world for navigation testing
- Configure SLAM (e.g., `slam_toolbox`) for autonomous mapping
- Add path planning with `nav2` stack
- Set up autonomous navigation goals
