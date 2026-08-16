cmake_minimum_required(VERSION 3.8)
project(aura_msgs)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/RobotStatus.msg"
  "msg/DeliveryTask.msg"
  "msg/BarcodeDetection.msg"
  "msg/OTPRequest.msg"
  "msg/ServoCommand.msg"
  "msg/InventoryUpdate.msg"
  "msg/SystemHealth.msg"
  DEPENDENCIES std_msgs
)

ament_package()
