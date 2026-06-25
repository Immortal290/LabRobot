# RobotStatus.msg — Published by: aura_health_monitor
# Topic: /aura/robot_status
std_msgs/Header header

# Core identity
string robot_name          # "AURA"
string firmware_version

# Operational state
string state               # idle|navigating|arrived|panel_open|error|charging
string mission             # human-readable current mission description
string current_destination # map frame goal label

# Position
float64 pos_x
float64 pos_y
float64 heading            # radians, 0 = North

# Power
float32 battery_percent
bool    is_charging

# Hardware health
bool    arduino_ok
bool    lidar_ok
bool    db_ok
bool    nav_ok
string  arduino_port

# Performance
float32 cpu_usage          # 0-100 %
float32 ram_usage          # 0-100 %
float32 cpu_temp           # Celsius

# Delivery context
int32   active_delivery_id
string  active_delivery_status
int32   active_rack_id

# Timestamps
builtin_interfaces/Time last_updated
