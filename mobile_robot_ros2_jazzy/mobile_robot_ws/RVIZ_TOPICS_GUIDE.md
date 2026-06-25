# RViz Navigation System - ROS2 Topics Guide

## Overview
This guide documents all ROS2 topics for your lightweight RViz-based navigation system on Raspberry Pi 5, including:
- Core navigation topics
- Sensor topics
- Control topics
- Visualization & debugging topics

---

## 1. CORE NAVIGATION TOPICS

### `/cmd_vel` (geometry_msgs/Twist)
**Purpose:** Robot velocity commands (linear + angular)  
**Publisher:** Teleop keyboard or autonomous nav controller  
**Subscriber:** `cmd_vel_to_joints` node  
**Message Format:**
```
linear:
  x: 0.5      # Forward velocity (m/s, positive=forward)
  y: 0.0      # Lateral (unused for differential drive)
  z: 0.0
angular:
  x: 0.0
  y: 0.0
  z: 0.3      # Rotation (rad/s, positive=counter-clockwise)
```
**Usage:** `ros2 topic pub /cmd_vel geometry_msgs/Twist "{linear: {x: 0.5}, angular: {z: 0.0}}"`

---

### `/odom` (nav_msgs/Odometry)
**Purpose:** Robot odometry (position, velocity, covariance)  
**Publisher:** `cmd_vel_to_joints` node  
**Subscriber:** Navigation, localization, RViz  
**Contains:**
- Position (x, y) in odom frame
- Orientation (quaternion)
- Linear & angular velocities
- Pose covariance (uncertainty)

**Monitor:** `ros2 topic echo /odom`

---

### `/joint_states` (sensor_msgs/JointState)
**Purpose:** Wheel joint angles and velocities  
**Publisher:** `cmd_vel_to_joints`, `joint_state_publisher`  
**Subscriber:** `robot_state_publisher`  
**For:**
- Wheel rotation visualization in RViz
- Odometry calculation
- Motor speed feedback (if available from hardware)

**Monitor:** `ros2 topic echo /joint_states`

---

### `/tf` & `/tf_static` (geometry_msgs/TransformStamped)
**Purpose:** Coordinate frame relationships  
**Key Frames:**
- `odom` → `base_link`: Robot pose relative to map
- `base_link` → `front_left_wheel`: Wheel positions
- `map` → `odom`: Localization drift correction

**Broadcaster:** `robot_state_publisher`, `cmd_vel_to_joints`  
**Visualize:** RViz → "TF" display

---

## 2. MAP & LOCALIZATION TOPICS

### `/map` (nav_msgs/OccupancyGrid)
**Purpose:** Static occupancy grid map  
**Publisher:** `map_server`  
**Subscriber:** RViz, costmap servers, planners  
**Properties:**
- Resolution: 0.1 m/cell
- Size: 20m × 20m
- Origin: [-10, -10, 0]

**Monitor:** `ros2 topic echo /map`

---

### `/map_metadata` (nav_msgs/MapMetaData)
**Purpose:** Map information (resolution, size, origin)  
**Publisher:** `map_server`  
**Used by:** Nav2, costmaps

---

## 3. NAVIGATION & PLANNING TOPICS (Nav2)

### `/goal_pose` (geometry_msgs/PoseStamped)
**Purpose:** Single goal position for autonomous navigation  
**Publishing Options:**
- RViz "2D Goal Pose" tool (visual)
- Command line: `ros2 topic pub /goal_pose geometry_msgs/PoseStamped ...`
- Your autonomous navigation node

**Message Format:**
```
header:
  stamp: {sec: 0, nsec: 0}    # Timestamp
  frame_id: "map"
pose:
  position:
    x: 5.0      # Goal X (meters)
    y: 3.0      # Goal Y (meters)
    z: 0.0
  orientation:
    x: 0.0
    y: 0.0
    z: 0.707    # Yaw rotation (quaternion)
    w: 0.707
```

**Example:**
```bash
ros2 topic pub /goal_pose geometry_msgs/PoseStamped \
  "{header: {frame_id: 'map'}, pose: {position: {x: 5, y: 3, z: 0}, orientation: {z: 0.707, w: 0.707}}}"
```

---

### `/path` (nav_msgs/Path) *(Optional - if using Nav2)*
**Purpose:** Planned path from current position to goal  
**Publisher:** Path planner (if enabled)  
**Subscriber:** RViz visualization  
**Shows:** Red line on map showing robot's planned route

---

## 4. SENSOR TOPICS (If Adding Real Sensors)

### `/scan` (sensor_msgs/LaserScan)
**Purpose:** LiDAR or laser scanner data  
**If Available:** Connect real LiDAR for dynamic collision avoidance
```bash
# Monitor LiDAR
ros2 topic echo /scan
```

### `/camera/image_raw` (sensor_msgs/Image)
**Purpose:** Camera feed (for CV-based navigation, optional)  
**Visualize in RViz:** Add "Image" display, select this topic

### `/imu` (sensor_msgs/Imu)
**Purpose:** Inertial data (gyro, accel) for better odometry

---

## 5. DEBUGGING & MONITORING TOPICS

### `/diagnostics` (diagnostic_msgs/DiagnosticArray)
**Purpose:** System health status  
**Monitor:** `ros2 topic echo /diagnostics`

### `/tf_tree` (Visualization)
**View TF relationships:** `ros2 run rqt_tf_tree rqt_tf_tree`

### `/graph` (Node connections)
**View node graph:** `ros2 run rqt_graph rqt_graph`

---

## 6. RECOMMENDED ADDITIONAL TOPICS TO IMPLEMENT

### A. COLLISION/OBSTACLE DETECTION
**Topic Name:** `/obstacles_detected` (std_msgs/Bool)
- Publishes `true` if costmap detects obstacle within safety radius
- Useful for safety checks before autonomous nav

**Implementation:**
```python
# In collision detection node
if costmap_cost > threshold:
    pub.publish(Bool(data=True))
```

---

### B. ROBOT STATE FEEDBACK
**Topic Name:** `/robot_state` (std_msgs/String)
- States: `idle`, `moving`, `rotating`, `goal_reached`, `stuck`
- Helps user understand current mode

---

### C. GOAL STATUS
**Topic Name:** `/goal_status` (std_msgs/String)
- Values: `goal_received`, `navigating`, `goal_reached`, `canceled`, `failed`
- Real-time feedback on autonomous navigation progress

---

### D. TARGET WAYPOINTS (Multi-goal)
**Topic Name:** `/waypoints` (nav_msgs/Path)
- Array of sequential goals to visit
- Useful for patrol or delivery routes

**Message:**
```
poses:
  - {header: ..., pose: {position: {x: 2, y: 2}}}
  - {header: ..., pose: {position: {x: 5, y: 5}}}
  - {header: ..., pose: {position: {x: 2, y: 8}}}
```

---

### E. COSTMAP VISUALIZATION
**Topic Name:** `/costmap` (nav_msgs/OccupancyGrid)
- Shows inflated obstacles and collision costs
- Useful for debugging navigation behavior

---

### F. BATTERY STATUS
**Topic Name:** `/battery_status` (sensor_msgs/BatteryState)
- Battery level, voltage, temperature
- Critical for Pi operation

---

### G. MOTION QUALITY METRICS
**Topic Names:**
- `/traveled_distance` (std_msgs/Float32) - Total distance traveled
- `/avg_speed` (std_msgs/Float32) - Average movement speed
- `/angular_velocity` (std_msgs/Float32) - Current rotation rate

---

## 7. QUICK REFERENCE COMMANDS

### Teleop with Keyboard
```bash
# In separate terminal:
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

### Set Goal (Command Line)
```bash
ros2 topic pub /goal_pose geometry_msgs/PoseStamped \
  "{header: {frame_id: 'map'}, pose: {position: {x: 5.0, y: 3.0, z: 0.0}}}"
```

### Monitor All Navigation Topics
```bash
# Terminal 1: Monitor odometry
ros2 topic echo /odom

# Terminal 2: Monitor map
ros2 topic echo /map

# Terminal 3: View RViz
# (Already running from launch)
```

### Record Bag (for playback/debugging)
```bash
ros2 bag record /odom /map /cmd_vel /joint_states -o my_navigation_session
```

### Replay Bag
```bash
ros2 bag play my_navigation_session/
```

---

## 8. SYSTEM ARCHITECTURE (ROS2 Topics Flow)

```
USER INPUTS
├─ RViz "2D Goal Pose" tool → /goal_pose
├─ Keyboard teleop → /cmd_vel
└─ Autonomy commands → /goal_pose

CORE NODES
├─ cmd_vel_to_joints:
│   ├─ INPUT:  /cmd_vel
│   ├─ OUTPUT: /joint_states, /odom, TF (odom → base_link)
│
├─ robot_state_publisher:
│   ├─ INPUT:  /joint_states
│   ├─ OUTPUT: TF (base_link → wheels), RViz visualization
│
├─ map_server:
│   └─ OUTPUT: /map, /map_metadata
│
└─ autonomous_nav (optional):
    ├─ INPUT:  /odom, /goal_pose
    ├─ OUTPUT: /cmd_vel
    └─ Drives robot to goals

VISUALIZATION
└─ RViz2:
    ├─ Displays: Robot model, map, goal, path
    ├─ Inputs:  TF, /map, /path
    └─ Outputs: /goal_pose (via "2D Goal Pose" tool)
```

---

## 9. PERFORMANCE OPTIMIZATION FOR RASPBERRY PI 5

**Reduce Topic Rates:**
- `/joint_states`: 50 Hz (currently good)
- `/odom`: 20 Hz (reduce if CPU high)
- `/map`: 1 Hz (map rarely changes)
- RViz update: 30 Hz max

**Disable Expensive Features:**
- Dynamic obstacle layers (use static map only)
- 3D visualization (use 2D only)
- Multiple simultaneous displays

**Monitor Performance:**
```bash
ros2 run rqt_monitor rqt_monitor
```

---

## 10. QUICK START: FULL AUTONOMOUS NAVIGATION PIPELINE

```bash
# Terminal 1: Launch everything
ros2 launch mobile_robot rviz_navigation_teleop.launch.py

# Terminal 2 (OPTIONAL: Manual control via keyboard)
ros2 run teleop_twist_keyboard teleop_twist_keyboard

# Terminal 3 (OPTIONAL: Monitor state)
ros2 topic echo /odom

# In RViz (when ready for autonomous):
# 1. Click "2D Goal Pose" tool (top toolbar)
# 2. Click/drag on map to place goal
# 3. Robot autonomously navigates!
```

---

## Troubleshooting

**Robot doesn't move:**
- Check `/cmd_vel` is being published: `ros2 topic echo /cmd_vel`
- Verify `/odom` is being published
- Check `cmd_vel_to_joints` node is running

**Goal not reached:**
- Verify goal is in free space (not in obstacle)
- Check `/map` is loaded correctly
- Monitor `/path` for planned route

**RViz crashes/slow:**
- Reduce RViz update frequency
- Disable TF display if not needed
- Monitor CPU with `top`

---

**Generated:** 2026-06-11  
**For:** Raspberry Pi 5 + ROS 2 Jazzy + RViz Only (No Gazebo)
