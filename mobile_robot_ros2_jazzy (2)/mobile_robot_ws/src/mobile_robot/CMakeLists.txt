cmake_minimum_required(VERSION 3.8)
project(mobile_robot)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# ── Dependencies ──────────────────────────────────────────────
find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)

# ── Install Python scripts (if any) ──────────────────────────
# ament_python_install_package(${PROJECT_NAME})

# ── Install directories ───────────────────────────────────────
install(
  DIRECTORY
    urdf
    launch
    config
    rviz
    worlds
  DESTINATION
    share/${PROJECT_NAME}/
)

# ── Testing ───────────────────────────────────────────────────
if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
