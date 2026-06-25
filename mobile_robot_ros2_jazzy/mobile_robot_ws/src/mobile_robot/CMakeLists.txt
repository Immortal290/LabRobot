cmake_minimum_required(VERSION 3.8)
project(mobile_robot)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# ── Dependencies ──────────────────────────────────────────────
find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)

# ── Install Python package ──────────────────────────────────
ament_python_install_package(mobile_robot)

# ── Install directories ───────────────────────────────────────
install(
  DIRECTORY
    urdf
    launch
    config
    rviz
    worlds
    maps
  DESTINATION
    share/${PROJECT_NAME}/
)

# ── Install Python executables ───────────────────────────────
install(
  PROGRAMS
    mobile_robot/cmd_vel_to_joints.py
  DESTINATION
    lib/${PROJECT_NAME}
  RENAME cmd_vel_to_joints
)

install(
  PROGRAMS
    mobile_robot/autonomous_nav.py
  DESTINATION
    lib/${PROJECT_NAME}
  RENAME autonomous_nav
)

install(
  PROGRAMS
    mobile_robot/simulated_lidar.py
  DESTINATION
    lib/${PROJECT_NAME}
  RENAME simulated_lidar
)

install(
  PROGRAMS
    mobile_robot/simulated_camera.py
  DESTINATION
    lib/${PROJECT_NAME}
  RENAME simulated_camera
)

install(
  PROGRAMS
    mobile_robot/real_camera.py
  DESTINATION
    lib/${PROJECT_NAME}
  RENAME real_camera
)

install(
  PROGRAMS
    scripts/imu_serial_node.py
  DESTINATION
    lib/${PROJECT_NAME}
  RENAME imu_serial_node.py
)

install(
  PROGRAMS
    scripts/wheel_odom_node.py
  DESTINATION
    lib/${PROJECT_NAME}
  RENAME wheel_odom_node.py
)

install(
  PROGRAMS
    scripts/encoder_serial_bridge.py
  DESTINATION
    lib/${PROJECT_NAME}
  RENAME encoder_serial_bridge.py
)

install(
  PROGRAMS
    scripts/encoder_serial_node.py
  DESTINATION
    lib/${PROJECT_NAME}
  RENAME encoder_serial_node.py
)

# ── Testing ───────────────────────────────────────────────────
if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
