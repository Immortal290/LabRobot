# SystemHealth.msg
# Topic: /aura/system_health
std_msgs/Header header

bool    arduino_connected
bool    lidar_connected
bool    db_connected
bool    nav_stack_ok
bool    ros_bridge_ok

string  arduino_port
string  lidar_port
float32 cpu_temp
float32 cpu_usage
float32 ram_usage
float32 battery_percent

# Per-node health
string[]  active_nodes
string[]  failed_nodes

string    overall_status    # "healthy" | "degraded" | "critical"
string    message           # Human-readable summary
