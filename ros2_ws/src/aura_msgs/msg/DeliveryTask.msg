# DeliveryTask.msg — Published by: aura_delivery_manager
# Topic: /aura/delivery_task
std_msgs/Header header

int32  delivery_id
int32  user_id
string username
int32  item_id
string item_name
int32  rack_id
string destination
string location
string pc_no
string phone_number
string status
string otp
int32  eta_seconds
builtin_interfaces/Time created_at
