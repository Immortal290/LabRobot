# ServoCommand.msg
# Topic: /aura/servo_command
std_msgs/Header header

int32  rack_id             # 1-4
string action              # "open" | "close"
bool   acknowledged        # Set to true by hardware node after ACK from Arduino
string error_message       # Non-empty if hardware rejected command
