# Recommended ROS2 Topics for RViz Navigation System

## 📋 Summary: Topics You Should Implement

Based on your Raspberry Pi 5 + RViz-only navigation setup, here are the **most valuable topics to add** for enhanced functionality:

---

## 🎯 Priority 1: ESSENTIAL (Implement First)

### 1. `/robot_state` (std_msgs/String)
**What it does:** Describes robot's current operational state  
**Values:** `idle`, `moving`, `rotating`, `goal_reached`, `failed`, `stuck`  
**Benefit:** User knows what robot is doing at any moment  
**Difficulty:** ⭐ Easy

```python
# Publish from your autonomous_nav node:
state_msg = String()
state_msg.data = "moving"  # or "rotating", "idle", etc.
robot_state_pub.publish(state_msg)
```

**Use:** Dashboard, logging, autonomous behavior decisions

---

### 2. `/obstacle_detected` (std_msgs/Bool)
**What it does:** Boolean alert when obstacle is within safety distance  
**True/False:** Obstacle nearby / All clear  
**Benefit:** Safety checks, emergency stop triggers  
**Difficulty:** ⭐ Easy (we provided `collision_detector.py`)

```python
# Already implemented in collision_detector.py
# Just run: ros2 run mobile_robot collision_detector
```

**Use:** Safety system, obstacle avoidance, alerts

---

### 3. `/goal_status` (std_msgs/String)  
**What it does:** Real-time feedback on navigation progress  
**Values:** `goal_received`, `navigating`, `goal_reached`, `canceled`, `failed`  
**Benefit:** Know if autonomous navigation is working  
**Difficulty:** ⭐ Easy

```python
# In autonomous_nav.py goal_callback():
status_msg = String()
status_msg.data = "goal_received"
goal_status_pub.publish(status_msg)

# In control_loop() when navigating:
status_msg.data = "navigating"
goal_status_pub.publish(status_msg)

# When goal reached:
status_msg.data = "goal_reached"
goal_status_pub.publish(status_msg)
```

**Use:** User feedback, behavior execution, logging

---

## 🎯 Priority 2: VERY USEFUL (Add Soon)

### 4. `/cmd_vel_debug` (geometry_msgs/Twist)
**What it does:** Echo actual velocity being sent (for debugging)  
**Benefit:** Verify teleop/autonomous commands match expectations  
**Difficulty:** ⭐ Very Easy

```python
# In cmd_vel_to_joints.py, also publish:
self.debug_pub = self.create_publisher(Twist, '/cmd_vel_debug', 10)

# In cmd_vel_callback():
self.debug_pub.publish(msg)  # Echo the received command
```

**Use:** Debugging, verifying control signals

---

### 5. `/distance_to_goal` (std_msgs/Float32)
**What it does:** Meters remaining to destination  
**Benefit:** Progress feedback, goal approach detection  
**Difficulty:** ⭐ Easy

```python
# In autonomous_nav.py control_loop():
distance_msg = Float32()
distance_to_goal = sqrt((self.goal_x - self.x)**2 + (self.goal_y - self.y)**2)
distance_msg.data = distance_to_goal
distance_pub.publish(distance_msg)
```

**Use:** Progress bars, logging, behavior decisions

---

### 6. `/closest_obstacle_distance` (std_msgs/Float32)
**What it does:** Distance to nearest obstacle  
**Benefit:** Autonomously detect if stuck or trapped  
**Difficulty:** ⭐ Easy (we provided this in `collision_detector.py`)

Already included in your collision detection setup!

```bash
ros2 topic echo /closest_obstacle_distance
```

---

### 7. `/path_to_goal` (nav_msgs/Path)
**What it does:** Planned path from current position to goal  
**Benefit:** Visualize planned route in RViz  
**Difficulty:** ⭐⭐ Medium (requires path planning algorithm)

```python
# Publish from path planner:
path_msg = Path()
path_msg.header.frame_id = "map"

for waypoint in planned_waypoints:
    pose_stamped = PoseStamped()
    pose_stamped.pose.position.x = waypoint[0]
    pose_stamped.pose.position.y = waypoint[1]
    path_msg.poses.append(pose_stamped)

path_pub.publish(path_msg)
```

**RViz Display:** Add "Path" display, select `/path_to_goal`

---

## 🎯 Priority 3: NICE TO HAVE (Add Later)

### 8. `/traveled_distance` (std_msgs/Float32)
**What it does:** Total cumulative distance traveled  
**Benefit:** Navigation statistics, battery estimation  
**Difficulty:** ⭐⭐ Easy-Medium

```python
# In cmd_vel_to_joints.py, accumulate distance:
self.total_distance = 0.0

def publish_states(self):
    # Every 20ms (50 Hz):
    distance_increment = sqrt(dx**2 + dy**2)
    self.total_distance += distance_increment
    
    traveled_msg = Float32()
    traveled_msg.data = self.total_distance
    traveled_pub.publish(traveled_msg)
```

---

### 9. `/current_speed` (std_msgs/Float32)
**What it does:** Real-time linear velocity (m/s)  
**Benefit:** Speed monitoring, debugging  
**Difficulty:** ⭐ Easy

```python
# In cmd_vel_to_joints.py:
speed_msg = Float32()
speed_msg.data = msg.linear.x  # Current linear velocity
current_speed_pub.publish(speed_msg)
```

---

### 10. `/waypoints_remaining` (std_msgs/Int32)
**What it does:** Number of goals left in multi-point navigation  
**Benefit:** Progress feedback for patrol/delivery routes  
**Difficulty:** ⭐⭐ Medium

```python
# In autonomous_nav.py:
remaining_msg = Int32()
remaining_msg.data = len(waypoint_queue)
waypoints_remaining_pub.publish(remaining_msg)
```

---

## 🎯 Priority 4: ADVANCED (Optional Enhancements)

### 11. `/battery_status` (sensor_msgs/BatteryState)
**What it does:** Battery voltage, percentage, temperature  
**Benefit:** Monitor Pi power, warn on low battery  
**Difficulty:** ⭐⭐⭐ Medium (requires hardware interface)

```python
# If you add a battery monitoring hardware:
from sensor_msgs.msg import BatteryState

battery_msg = BatteryState()
battery_msg.voltage = 5.0  # volts
battery_msg.percentage = 0.85  # 85%
battery_msg.temperature = 45.0  # Celsius
battery_msg.present = True
battery_pub.publish(battery_msg)
```

---

### 12. `/costmap_inflated` (nav_msgs/OccupancyGrid)
**What it does:** Inflated costmap showing safety margins  
**Benefit:** Visualize how close robot can get to walls  
**Difficulty:** ⭐⭐⭐ Hard (requires costmap computation)

---

### 13. `/tf_performance` (std_msgs/Float32)
**What it does:** TF broadcast latency (milliseconds)  
**Benefit:** Performance monitoring, debugging delays  
**Difficulty:** ⭐⭐ Medium

---

## 📊 Topic Implementation Checklist

| Topic | Priority | Difficulty | Status |
|-------|----------|-----------|--------|
| `/robot_state` | 🔴 1 | ⭐ | ☐ Implement |
| `/obstacle_detected` | 🔴 1 | ⭐ | ✅ Provided |
| `/goal_status` | 🔴 1 | ⭐ | ☐ Implement |
| `/cmd_vel_debug` | 🟡 2 | ⭐ | ☐ Implement |
| `/distance_to_goal` | 🟡 2 | ⭐ | ☐ Implement |
| `/closest_obstacle_distance` | 🟡 2 | ⭐ | ✅ Provided |
| `/path_to_goal` | 🟡 2 | ⭐⭐ | ☐ Implement |
| `/traveled_distance` | 🟢 3 | ⭐⭐ | ☐ Implement |
| `/current_speed` | 🟢 3 | ⭐ | ☐ Implement |
| `/waypoints_remaining` | 🟢 3 | ⭐⭐ | ☐ Implement |
| `/battery_status` | 🟣 4 | ⭐⭐⭐ | ☐ Implement |
| `/costmap_inflated` | 🟣 4 | ⭐⭐⭐ | ☐ Implement |

---

## 🔧 Implementation Guide

### For Priority 1 (Essential) Topics:

**Step 1:** Add to autonomous_nav.py

```python
# Import at top
from std_msgs.msg import String, Float32

# In __init__:
self.robot_state_pub = self.create_publisher(String, '/robot_state', 10)
self.goal_status_pub = self.create_publisher(String, '/goal_status', 10)
self.distance_pub = self.create_publisher(Float32, '/distance_to_goal', 10)

# In goal_callback():
status_msg = String()
status_msg.data = "goal_received"
self.goal_status_pub.publish(status_msg)

# In control_loop():
# Update robot state
state_msg = String()
if distance_to_goal < 0.1:
    state_msg.data = "idle"
else:
    state_msg.data = "moving"
self.robot_state_pub.publish(state_msg)

# Update distance
distance_msg = Float32()
distance_msg.data = distance_to_goal
self.distance_pub.publish(distance_msg)

# Update goal status
status_msg = String()
if distance_to_goal < 0.1:
    status_msg.data = "goal_reached"
else:
    status_msg.data = "navigating"
self.goal_status_pub.publish(status_msg)
```

**Step 2:** Rebuild
```bash
cd ~/Desktop/AURA/mobile_robot_ros2_jazzy/mobile_robot_ws
colcon build --packages-select mobile_robot
```

**Step 3:** Monitor in RViz
```bash
ros2 topic echo /robot_state
ros2 topic echo /goal_status
ros2 topic echo /distance_to_goal
```

---

## 📊 Data Flow with Recommended Topics

```
┌─────────────────────────────────────────────────────────┐
│                    AUTONOMOUS NAVIGATION                 │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  /goal_pose (from RViz) → autonomous_nav.py            │
│                            ├─ Publish: /goal_status     │
│                            ├─ Publish: /robot_state     │
│                            ├─ Publish: /distance_to_goal│
│                            ├─ Publish: /cmd_vel         │
│                            └─ Publish: /path_to_goal    │
│                              │                          │
│                              ▼                          │
│                        cmd_vel_to_joints.py             │
│                              ├─ Publish: /odom          │
│                              ├─ Publish: /joint_states  │
│                              ├─ Publish: /cmd_vel_debug │
│                              ├─ Publish: /traveled_dist │
│                              └─ Publish: /current_speed │
│                              │                          │
│                              ▼                          │
│                        collision_detector.py            │
│                              ├─ Publish: /obstacle_detected
│                              └─ Publish: /closest_distance
│                              │                          │
│                              ▼                          │
│                          RViz Visualization             │
│                              ├─ Map (/map)             │
│                              ├─ Robot (/tf)            │
│                              ├─ Path (/path_to_goal)   │
│                              ├─ Status (/goal_status)  │
│                              └─ Obstacles (/costmap)   │
│                                                        │
└─────────────────────────────────────────────────────────┘
```

---

## ✅ Quick Implementation Timeline

**Week 1:** Implement Priority 1 topics
- `/robot_state` - 15 min
- `/goal_status` - 15 min  
- `/obstacle_detected` - Already provided ✓

**Week 2:** Add Priority 2 topics
- `/distance_to_goal` - 10 min
- `/path_to_goal` - 1-2 hours (requires path planning)

**Week 3+:** Polish with Priority 3 & 4 topics
- Performance monitoring
- Advanced feedback systems

---

## 🎬 Example: Full Topic Monitoring Dashboard

```bash
# Terminal 1: Launch system
ros2 launch mobile_robot rviz_navigation_teleop.launch.py

# Terminal 2: View robot state
watch -n 0.5 "echo '=== ROBOT STATE ===' && \
  ros2 topic echo /robot_state --once && \
  echo '=== GOAL STATUS ===' && \
  ros2 topic echo /goal_status --once && \
  echo '=== DISTANCE ===' && \
  ros2 topic echo /distance_to_goal --once && \
  echo '=== SPEED ===' && \
  ros2 topic echo /current_speed --once"
```

---

## 🎓 Learning Resources

To understand these topics better:
- ROS 2 standard message types: `ros2 interface show <msg_type>`
- Topic monitoring: `ros2 topic echo <topic_name>`
- Message definitions: `/opt/ros/jazzy/share/<package>/msg/`

Example:
```bash
ros2 interface show geometry_msgs/msg/Twist
ros2 interface show nav_msgs/msg/Path
ros2 interface show std_msgs/msg/String
```

---

**Summary:**
- ✅ **Collision detection** is ready (we provided the node)
- ✅ **Map visualization** is ready
- ✅ **Teleop + autonomous nav** infrastructure is in place
- 📝 **Next:** Implement Priority 1 topics for better feedback and safety
- 🚀 **Goal:** Full autonomous navigation with real-time monitoring on Pi 5

**Questions?** Check `RVIZ_TOPICS_GUIDE.md` for complete details
