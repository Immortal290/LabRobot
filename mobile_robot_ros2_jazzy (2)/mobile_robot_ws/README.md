# 🤖 Mobile Kiosk Robot — ROS 2 Jazzy

**Platform:** Ubuntu 24.04 | ROS 2 Jazzy | Gazebo Harmonic  
**Robot:** 2ft × 2ft mobile base, 1.5ft kiosk body, touchpad stand, LiDAR navigation

---

## 📐 Robot Dimensions

| Part | Size |
|-- --|-- --|
| Base platform | 610mm × 610mm × 80mm (2ft × 2ft) |
| Kiosk cabinet | 500mm × 400mm × 457mm (1.5ft) |
| Angled top section | 500mm × 400mm × 150mm |
| Wheels (4×) | ⌀150mm × 50mm |
| LiDAR (top-mounted) | ⌀80mm × 70mm cylinder |
| Touchpad screen | 280mm × 20mm × 180mm |

---

## 1. Prerequisites

### 1.1 Install ROS 2 Jazzy

```bash
sudo apt update && sudo apt install -y curl
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
  -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
  http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" \
  | sudo tee /etc/apt/sources.list.d/ros2.list
sudo apt update
sudo apt install -y ros-jazzy-desktop
```

### 1.2 Install Gazebo Harmonic

```bash
sudo apt install -y ros-jazzy-ros-gz
```

### 1.3 Install all required ROS 2 packages

```bash
sudo apt install -y \
  ros-jazzy-robot-state-publisher \
  ros-jazzy-joint-state-publisher \
  ros-jazzy-joint-state-publisher-gui \
  ros-jazzy-xacro \
  ros-jazzy-ros2-control \
  ros-jazzy-ros2-controllers \
  ros-jazzy-gz-ros2-control \
  ros-jazzy-diff-drive-controller \
  ros-jazzy-joint-state-broadcaster \
  ros-jazzy-robot-localization \
  ros-jazzy-teleop-twist-keyboard \
  ros-jazzy-rviz2 \
  ros-jazzy-ros-gz-bridge \
  ros-jazzy-ros-gz-sim \
  python3-colcon-common-extensions \
  python3-rosdep
```

### 1.4 Initialize rosdep

```bash
sudo rosdep init    # skip if already done
rosdep update
```

---

## 2. Build the Workspace

```bash
# Navigate to workspace
cd ~/mobile_robot_ws

# Source ROS 2
source /opt/ros/jazzy/setup.bash

# Resolve dependencies
rosdep install --from-paths src --ignore-src -r -y

# Build
colcon build --symlink-install

# Source the workspace
source install/setup.bash
```

> 💡 **Add to ~/.bashrc for convenience:**
> ```bash
> echo "source /opt/ros/jazzy/setup.bash" >> ~/.bashrc
> echo "source ~/mobile_robot_ws/install/setup.bash" >> ~/.bashrc
> ```

---

## 3. Launch Options

### 3.1 🖥️ View Robot Model Only (no simulation)

```bash
ros2 launch mobile_robot display.launch.py
```

Opens **RViz2** with:
- Robot model rendered from URDF
- TF tree (all frames)
- Joint state publisher GUI (drag sliders to move wheels)

---

### 3.2 🌍 Full Gazebo Simulation

```bash
ros2 launch mobile_robot gazebo.launch.py
```

This single command starts:
- Gazebo Harmonic with empty world + walls + obstacles
- Robot spawned at origin
- `diff_drive_controller` and `joint_state_broadcaster`
- ROS-Gazebo bridge (LaserScan, IMU, Odometry, cmd_vel, TF, clock)
- EKF localization (`/odom` + `/imu/data` → fused pose)
- RViz2 with full pre-config (model, TF, LaserScan, Odometry, Path)

Optional arguments:
```bash
ros2 launch mobile_robot gazebo.launch.py x:=1.0 y:=0.0 yaw:=1.57
ros2 launch mobile_robot gazebo.launch.py world:=/path/to/my_world.sdf
```

---

### 3.3 🎮 Teleoperation (keyboard)

In a **second terminal**:

```bash
source /opt/ros/jazzy/setup.bash
source ~/mobile_robot_ws/install/setup.bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard \
  --ros-args --remap cmd_vel:=/cmd_vel
```

**Controls:**
```
Moving around:
   u    i    o
   j    k    l
   m    ,    .

i/,  : forward/backward
j/l  : turn left/right
u/o  : diagonal forward
k    : STOP

q/z  : increase/decrease ALL speeds by 10%
w/x  : increase/decrease LINEAR speed
e/c  : increase/decrease ANGULAR speed

CTRL-C to quit
```

---

### 3.4 Combined (Simulation + Teleop in one command)

```bash
ros2 launch mobile_robot gazebo.launch.py &
sleep 10
ros2 launch mobile_robot teleop.launch.py use_sim_time:=true
```

---

## 4. Key Topics

| Topic | Type | Description |
|-- ---|-- --|-- -- -- -|
| `/cmd_vel` | `geometry_msgs/Twist` | Drive command input |
| `/scan` | `sensor_msgs/LaserScan` | LiDAR 360° scan |
| `/odom` | `nav_msgs/Odometry` | Wheel odometry |
| `/imu/data` | `sensor_msgs/Imu` | IMU measurements |
| `/odom_ekf` | `nav_msgs/Odometry` | EKF-fused odometry |
| `/tf` | `tf2_msgs/TFMessage` | Transform tree |
| `/joint_states` | `sensor_msgs/JointState` | All joint positions |
| `/robot_description` | `std_msgs/String` | URDF XML |
| `/camera/image_raw` | `sensor_msgs/Image` | Front camera |

---

## 5. TF Frame Tree

```
map
└── odom
    └── base_footprint
        └── base_link
            ├── body_link
            │   ├── top_section_link
            │   │   ├── touchpad_link
            │   │   ├── lidar_mount_link
            │   │   │   └── lidar_link
            │   │   │       └── laser_frame  ← /scan origin
            │   └── camera_link
            │       └── camera_optical_frame
            ├── front_left_wheel
            ├── front_right_wheel
            ├── rear_left_wheel
            ├── rear_right_wheel
            └── imu_link
```

---

## 6. VS Code Integration

Open the workspace file in VS Code:

```bash
code ~/mobile_robot_ws/mobile_robot.code-workspace
```

Available **Tasks** (Ctrl+Shift+P → "Run Task"):
- 🔨 Build workspace
- 🧹 Clean workspace
- 🚀 Launch Display (RViz only)
- 🌍 Launch Gazebo Simulation
- 🎮 Launch Teleop
- 📋 List Topics
- 📡 Echo /scan

Recommended **Extensions** (auto-prompted on open):
- `ms-iot.vscode-ros` — ROS integration
- `ms-python.python` — Python support
- `ms-vscode.cpptools` — C++ IntelliSense
- `redhat.vscode-xml` — URDF/xacro/SDF editing
- `redhat.vscode-yaml` — config file editing

---

## 7. Useful Debugging Commands

```bash
# Check all active topics
ros2 topic list

# View laser scan data
ros2 topic echo /scan --once

# View odometry
ros2 topic echo /odom --once

# View TF tree (install: sudo apt install ros-jazzy-tf2-tools)
ros2 run tf2_tools view_frames

# Check controller status
ros2 control list_controllers

# View controller state
ros2 control list_hardware_interfaces

# Manual velocity command (forward)
ros2 topic pub /cmd_vel geometry_msgs/msg/Twist \
  '{linear: {x: 0.3}, angular: {z: 0.0}}' --rate 10

# Stop robot
ros2 topic pub /cmd_vel geometry_msgs/msg/Twist \
  '{linear: {x: 0.0}, angular: {z: 0.0}}' --once
```

---

## 8. Package Structure

```
mobile_robot_ws/
├── mobile_robot.code-workspace    ← Open this in VS Code
├── README.md
└── src/
    └── mobile_robot/
        ├── CMakeLists.txt
        ├── package.xml
        ├── urdf/
        │   ├── mobile_robot.urdf.xacro  ← Main robot file
        │   ├── materials.xacro          ← Visual materials
        │   ├── macros.xacro             ← Helper macros
        │   └── gazebo.xacro             ← Sensors + plugins
        ├── launch/
        │   ├── display.launch.py        ← RViz2 only
        │   ├── gazebo.launch.py         ← Full simulation
        │   └── teleop.launch.py         ← Keyboard control
        ├── config/
        │   ├── ros2_controllers.yaml    ← Diff drive + JSB config
        │   ├── robot_params.yaml        ← Robot parameters
        │   ├── ekf.yaml                 ← Localization config
        │   └── ros_gz_bridge.yaml       ← Gazebo↔ROS bridge
        ├── rviz/
        │   └── mobile_robot.rviz        ← Pre-configured RViz2
        └── worlds/
            └── empty_world.sdf          ← Gazebo world
```

---

## 9. Troubleshooting

**"xacro: command not found"**
```bash
sudo apt install -y ros-jazzy-xacro
```

**"No module named 'launch'"**
```bash
source /opt/ros/jazzy/setup.bash
```

**Robot not moving after teleop**
```bash
ros2 control list_controllers
# Both diff_drive_controller and joint_state_broadcaster should show "active"
```

**Gazebo not starting**
```bash
# Ensure Gazebo Harmonic is installed
gz sim --version
# Should show "Gazebo, version 8.x.x"
```

**RViz shows no robot model**
```bash
ros2 topic echo /robot_description --once | head -5
# Should show URDF XML
```
