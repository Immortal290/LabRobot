# Mobile Robot - Gazebo Lab World + Autonomous Navigation Testing

## Overview

Your robot now has:
- ✅ **Lab world** - realistic environment with walls, tables, obstacles
- ✅ **Gazebo simulation** - full physics and sensor simulation
- ✅ **ROS 2 Jazzy** - complete ROS 2 integration
- ✅ **Autonomous navigation** - goal-based movement
- ✅ **Multiple sensors** - LiDAR, IMU, wheel encoders
- ✅ **Keyboard teleop** - manual control

---

## Quick Start - Test Everything

### **Terminal 1 - Gazebo with Lab World:**
```bash
cd ~/Desktop/AURA/mobile_robot_ros2_jazzy/mobile_robot_ws
source install/setup.bash
ros2 launch mobile_robot gazebo_lab_world.launch.py
```

**What you'll see:**
- Gazebo window with lab environment
- RViz window showing robot + sensor data
- 10x10m lab with walls, tables, and colored obstacles

---

### **Terminal 2 - Keyboard Teleop (Manual Control):**
```bash
cd ~/Desktop/AURA/mobile_robot_ros2_jazzy/mobile_robot_ws
source install/setup.bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

**Control the robot:**

| Key | Action |
|-----|--------|
| **i** | Move forward |
| **,** | Move backward |
| **j** | Turn left |
| **l** | Turn right |
| **k** | Stop |
| **u/o** | Diagonal forward |
| **m/.** | Diagonal backward |

---

### **Terminal 3 - Autonomous Navigation:**
```bash
cd ~/Desktop/AURA/mobile_robot_ros2_jazzy/mobile_robot_ws
source install/setup.bash
ros2 run mobile_robot autonomous_nav
```

This starts the autonomous navigation node. It will listen for goal poses.

---

## Testing Autonomous Movement

### **Send a Navigation Goal (Terminal 4):**

**Goal 1 - Move forward 2 meters:**
```bash
ros2 topic pub /goal_pose geometry_msgs/PoseStamped \
  "{header: {stamp: {sec: 0, nanosec: 0}, frame_id: 'odom'}, 
    pose: {position: {x: 2.0, y: 0.0, z: 0}, 
           orientation: {x: 0, y: 0, z: 0, w: 1}}}" -1
```

Watch the robot move to (2, 0) in the Gazebo window!

**Goal 2 - Move to table location:**
```bash
ros2 topic pub /goal_pose geometry_msgs/PoseStamped \
  "{header: {stamp: {sec: 0, nanosec: 0}, frame_id: 'odom'}, 
    pose: {position: {x: 2.0, y: 2.0, z: 0}, 
           orientation: {x: 0, y: 0, z: 0, w: 1}}}" -1
```

**Goal 3 - Move to obstacle and around it:**
```bash
ros2 topic pub /goal_pose geometry_msgs/PoseStamped \
  "{header: {stamp: {sec: 0, nanosec: 0}, frame_id: 'odom'}, 
    pose: {position: {x: 1.5, y: -2.0, z: 0}, 
           orientation: {x: 0, y: 0, z: 0, w: 1}}}" -1
```

---

## Monitoring Topics (Terminal 4)

### **Watch Robot Odometry (Position):**
```bash
ros2 topic echo /odom
```

You'll see:
- Position: x, y, z
- Orientation: quaternion
- Linear velocity
- Angular velocity

### **Watch LiDAR Data:**
```bash
ros2 topic echo /scan --no-arr
```

Shows 360° laser scan measurements.

### **Watch Command Velocity:**
```bash
ros2 topic echo /cmd_vel
```

Shows what commands are being sent to the robot.

### **Watch Joint States (Wheel Rotation):**
```bash
ros2 topic echo /joint_states --no-arr
```

---

## Lab World Description

The generated lab world includes:

| Obstacle | Location | Purpose |
|----------|----------|---------|
| **Walls** (4) | Perimeter | Lab boundaries |
| **Table 1** | (2, 2) | Desk/Workbench |
| **Table 2** | (-2, 2) | Lab Equipment |
| **Box 1** (Red) | (0, 1) | Obstacle for navigation |
| **Box 2** (Green) | (2, -1) | Rotated obstacle |
| **Cylinder** (Yellow) | (-2, -2) | Cylindrical obstacle |

---

## Advanced Testing - Multiple Goals

### **Create a loop through waypoints (Terminal 4):**

```bash
# Start at origin
ros2 topic pub -1 /goal_pose geometry_msgs/PoseStamped \
  "{header: {frame_id: 'odom'}, pose: {position: {x: 0, y: 0}, orientation: {w: 1}}}"

# Wait ~5 seconds, then next goal...

# Goal 1: Move right
ros2 topic pub -1 /goal_pose geometry_msgs/PoseStamped \
  "{header: {frame_id: 'odom'}, pose: {position: {x: 3, y: 0}, orientation: {w: 1}}}"

# Goal 2: Move forward
ros2 topic pub -1 /goal_pose geometry_msgs/PoseStamped \
  "{header: {frame_id: 'odom'}, pose: {position: {x: 3, y: 3}, orientation: {w: 1}}}"

# Goal 3: Move left
ros2 topic pub -1 /goal_pose geometry_msgs/PoseStamped \
  "{header: {frame_id: 'odom'}, pose: {position: {x: 0, y: 3}, orientation: {w: 1}}}"

# Goal 4: Return to origin
ros2 topic pub -1 /goal_pose geometry_msgs/PoseStamped \
  "{header: {frame_id: 'odom'}, pose: {position: {x: 0, y: 0}, orientation: {w: 1}}}"
```

---

## Understanding the Navigation Algorithm

The `autonomous_nav` node uses simple proportional control:

1. **Calculate distance** to goal
2. **Calculate angle** to goal
3. **Rotate towards goal** (if angle error > threshold)
4. **Move forward** while adjusting heading
5. **Stop** when distance < 0.1m and heading error < 0.2 rad

**Parameters** (in `autonomous_nav.py`):
- `max_linear_vel`: 0.5 m/s
- `max_angular_vel`: 1.0 rad/s
- `dist_tolerance`: 0.1 m
- `angle_tolerance`: 0.2 rad (~11°)

---

## Sensor Data Available

### **LiDAR (/scan)**
- Range: 0.12m - 12.0m
- Field of View: 360°
- Update Rate: 10 Hz
- Type: `sensor_msgs/msg/LaserScan`

### **IMU (/imu/data)**
- Angular velocity (gyro)
- Linear acceleration (accel)
- Update Rate: 100 Hz
- Type: `sensor_msgs/msg/Imu`

### **Wheel Encoders (/joint_states)**
- Joint angles (wheel rotation)
- Joint velocities
- Update Rate: 50 Hz
- Type: `sensor_msgs/msg/JointState`

### **Odometry (/odom)**
- Robot pose in world frame
- Velocities
- Update Rate: 50 Hz
- Type: `nav_msgs/msg/Odometry`

---

## Troubleshooting

### **"Gazebo can't load world"**
- Check world file exists: `ls src/mobile_robot/worlds/lab_world.sdf`
- Verify SDF syntax: `xmllint --noout src/mobile_robot/worlds/lab_world.sdf`

### **Robot doesn't move in Gazebo**
- Check `/cmd_vel` is being published
- Verify diff_drive_controller is loaded: `ros2 service call /controller_manager/list_controllers controller_manager_msgs/srv/ListControllers`

### **Autonomous nav not working**
- Check odom topic: `ros2 topic echo /odom`
- Verify goal_pose is published: `ros2 topic list | grep goal_pose`
- Check node output: `ros2 node list`

### **LiDAR not visible in RViz**
- Ensure LaserScan display is enabled in RViz
- Check `/scan` topic exists: `ros2 topic list`
- Verify frame_id matches RViz fixed frame

---

## Next Steps

1. **Add SLAM** - Use `slam_toolbox` for real-time mapping
2. **Add Navigation** - Integrate `nav2` for full autonomous navigation
3. **Add Costmaps** - Generate occupancy grids from LiDAR
4. **Add Path Planning** - Use `nav2` planners for obstacle avoidance
5. **Modify World** - Edit `lab_world.sdf` to add more obstacles/furniture

---

## Important Topics Summary

| Topic | Type | Direction | Use |
|-------|------|-----------|-----|
| `/cmd_vel` | Twist | ROS→Gazebo | Send movement commands |
| `/odom` | Odometry | Gazebo→ROS | Get robot position |
| `/scan` | LaserScan | Gazebo→ROS | LiDAR sensor data |
| `/imu/data` | Imu | Gazebo→ROS | IMU sensor data |
| `/joint_states` | JointState | Gazebo→ROS | Wheel encoder data |
| `/goal_pose` | PoseStamped | ROS→Nav | Send navigation goals |
| `/tf` | TFMessage | Broadcast | Transform frames |

---

## Performance Notes

- **Gazebo physics:** Real-time on modern hardware
- **LiDAR update rate:** 10 Hz (configurable)
- **ROS 2 control:** 50 Hz
- **CPU load:** ~40-60% (Gazebo)
- **Memory:** ~1-2 GB

Enjoy testing your autonomous mobile robot! 🤖
