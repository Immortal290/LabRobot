#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
#  AURA Map Saving Utility
#  Saves the map in both:
#    1. Standard Nav2 format (.pgm image + .yaml configuration)
#    2. SLAM Toolbox serialization format (.posegraph + .data)
# ═══════════════════════════════════════════════════════════════════════════

set -e

# Setup ROS environment
source /opt/ros/jazzy/setup.bash
source /home/lab/Desktop/AURA/mobile_robot_ros2_jazzy/mobile_robot_ws/install/setup.bash

MAP_DIR="/home/lab/Desktop/AURA/maps"
MAP_NAME="lab_map"
MAP_PATH="${MAP_DIR}/${MAP_NAME}"

echo "=================================================="
echo "          AURA Rover: Saving Map..."
echo "=================================================="
echo "Destination: ${MAP_PATH}"
echo ""

# Ensure directory exists
mkdir -p "${MAP_DIR}"

# 1. Save standard Nav2 (.pgm + .yaml) map
echo "[1/2] Saving static Nav2 map image (.pgm + .yaml)..."
if ros2 run nav2_map_server map_saver_cli -f "${MAP_PATH}" --free 0.25 --occupied 0.65; then
    echo "✓ Nav2 map files successfully written."
else
    echo "✗ Failed to save via map_saver_cli. Checking if topic is alive..."
fi

echo ""

# 2. Serialize SLAM Toolbox pose graph (.posegraph + .data)
echo "[2/2] Serializing SLAM Toolbox pose graph..."
if ros2 service call /slam_toolbox/save_map slam_toolbox/srv/SaveMap "{name: {data: '${MAP_PATH}'}}"; then
    echo "✓ SLAM Toolbox pose graph serialized."
else
    echo "✗ Failed to call SLAM Toolbox save_map service."
fi

echo ""
echo "=================================================="
echo "  Done! Saved files in ${MAP_DIR}:"
ls -la "${MAP_DIR}"
echo "=================================================="
