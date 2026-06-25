#!/usr/bin/env python3
"""
Optimized Map Generator for Raspberry Pi 5
──────────────────────────────────────────────────────────
Creates a lightweight, RViz-friendly map with:
  • Reduced resolution (0.1 m/cell for smaller file size)
  • Strategic walls and obstacles (simulating a building layout)
  • Clear free space for robot navigation
  • Collision zones marked for costmap computation

Map is 20m x 20m (200x200 cells @ 0.1 m/cell)

Usage:
    python3 optimized_map_generator.py
    
Or auto-generate in launch file.
"""

import os
import numpy as np
from ament_index_python.packages import get_package_share_directory


def generate_optimized_map():
    """Generate optimized map for RViz + Raspberry Pi."""
    
    pkg_dir = get_package_share_directory("mobile_robot")
    maps_dir = os.path.join(pkg_dir, "maps")
    
    # Create maps directory if it doesn't exist
    os.makedirs(maps_dir, exist_ok=True)
    
    # Map dimensions: 200x200 cells (0.1 m/cell = 20m x 20m)
    # Smaller than before = better performance on Pi
    width = 200
    height = 200
    
    # Initialize map: 255 = free space, 0 = obstacle, 128 = unknown
    map_data = np.ones((height, width), dtype=np.uint8) * 255
    
    # ─────────────────────────────────────────────────────────
    # PERIMETER WALLS (simulating building boundary)
    # ─────────────────────────────────────────────────────────
    wall_thickness = 4
    map_data[0:wall_thickness, :] = 0           # Top wall
    map_data[-wall_thickness:, :] = 0           # Bottom wall
    map_data[:, 0:wall_thickness] = 0           # Left wall
    map_data[:, -wall_thickness:] = 0           # Right wall
    
    # ─────────────────────────────────────────────────────────
    # INTERIOR WALLS (creating navigation corridors)
    # ─────────────────────────────────────────────────────────
    
    # Vertical wall separating left and right sections
    map_data[40:160, 95:105] = 0  # Main divider wall
    
    # Horizontal wall in upper left section
    map_data[40:50, 20:80] = 0   # Creates upper-left enclosed area
    
    # Horizontal wall in lower section
    map_data[145:155, 50:150] = 0  # Divides lower area
    
    # Vertical wall on right side
    map_data[60:130, 140:150] = 0  # Creates right-side corridor
    
    # ─────────────────────────────────────────────────────────
    # OBSTACLES (simulating furniture/equipment)
    # ─────────────────────────────────────────────────────────
    
    # Office desk/obstacle in top-left area
    map_data[50:65, 25:40] = 0
    
    # Obstacle in middle-left
    map_data[85:100, 30:45] = 0
    
    # Obstacle in middle-right  
    map_data[85:100, 155:170] = 0
    
    # Obstacle in bottom-left
    map_data[160:175, 25:50] = 0
    
    # Obstacle in bottom-right
    map_data[160:175, 155:175] = 0
    
    # ─────────────────────────────────────────────────────────
    # COLUMNS/PILLARS (simulating support structures)
    # ─────────────────────────────────────────────────────────
    pillar_size = 6
    pillars = [
        (60, 130),
        (120, 60),
        (130, 160),
    ]
    for py, px in pillars:
        map_data[py:py+pillar_size, px:px+pillar_size] = 0
    
    # ─────────────────────────────────────────────────────────
    # SAVE MAP AS PGM (Portable Gray Map binary format)
    # ─────────────────────────────────────────────────────────
    pgm_file = os.path.join(maps_dir, "rviz_navigation_map.pgm")
    with open(pgm_file, 'wb') as f:
        # PGM header (P5 = binary format)
        f.write(b"P5\n")
        f.write(f"# RViz-optimized navigation map for Raspberry Pi\n".encode())
        f.write(f"{width} {height}\n".encode())
        f.write(b"255\n")  # Max pixel value
        # Write binary image data
        f.write(map_data.tobytes())
    
    # ─────────────────────────────────────────────────────────
    # SAVE YAML METADATA (map configuration)
    # ─────────────────────────────────────────────────────────
    yaml_file = os.path.join(maps_dir, "rviz_navigation_map.yaml")
    with open(yaml_file, 'w') as f:
        f.write("""# RViz Navigation Map Configuration
# For use with nav2_map_server

image: rviz_navigation_map.pgm
mode: trinary
resolution: 0.1                # 10cm per cell (good balance: detail vs performance)
origin: [-10.0, -10.0, 0.0]   # Map origin in meters (x, y, theta)
negate: 0                      # 0 = white is free, black is occupied
occupied_thresh: 0.65          # Probability above this = occupied
free_thresh: 0.25              # Probability below this = free
""")
    
    print(f"✓ Generated optimized map: {pgm_file}")
    print(f"✓ Generated config: {yaml_file}")
    print(f"  Map size: 20m x 20m (200x200 cells @ 0.1m/cell)")
    print(f"  File size: ~{os.path.getsize(pgm_file) / 1024:.1f} KB")
    
    return pgm_file, yaml_file


if __name__ == "__main__":
    generate_optimized_map()
