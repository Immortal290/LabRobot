cmake_minimum_required(VERSION 3.8)
project(mobile_robot_mapping)

find_package(ament_cmake REQUIRED)

install(DIRECTORY
  launch
  config
  rviz
  DESTINATION share/${PROJECT_NAME}
)

install(PROGRAMS
  scripts/check_odom_calibration.py
  scripts/gimp_clean_map.sh
  DESTINATION lib/${PROJECT_NAME}
)

# Install scripts into the share directory too, or just install them as programs.
# Let's keep them matching CMake install patterns.
install(FILES
  scripts/gimp_clean_map.scm
  DESTINATION share/${PROJECT_NAME}/scripts
)

ament_package()
