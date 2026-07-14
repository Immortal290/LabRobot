# BarcodeDetection.msg
# Topic: /aura/barcode_detection
std_msgs/Header header

string barcode_value       # Raw scanned barcode string
string department          # Lab department name
string room                # Room / lab identifier
string nav_goal_name       # Named goal in the navigation map
float64 goal_x             # Map coordinates
float64 goal_y
float64 goal_theta         # Heading at goal
bool    valid              # True if barcode found in DB
string  error_message      # Set if valid=false
