# InventoryUpdate.msg
# Topic: /aura/inventory_update
std_msgs/Header header

int32  item_id
string item_name
int32  quantity_before
int32  quantity_after
string action              # "dispense" | "restock" | "adjust"
int32  delivery_id
int32  rack_id
bool   success
string message
