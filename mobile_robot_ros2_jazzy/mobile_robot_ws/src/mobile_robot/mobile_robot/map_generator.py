#!/usr/bin/env python3
"""
Generate custom map for navigation.
Creates a PGM file with walls and free space.
"""

import os
import numpy as np
from ament_index_python.packages import get_package_share_directory


def generate_custom_map():
    """Generate a custom map with walls and obstacles."""
    
    pkg_dir = get_package_share_directory("mobile_robot")
    maps_dir = os.path.join(pkg_dir, "maps")
    
    # Create maps directory if it doesn't exist
    os.makedirs(maps_dir, exist_ok=True)
    
    # Map dimensions: 200x200 cells (0.05 m/cell = 10m x 10m)
    width = 200
    height = 200
    
    # Create map: 255 = free, 0 = obstacle, 128 = unknown
    map_data = np.ones((height, width), dtype=np.uint8) * 255
    
    # Add walls (perimeter)
    wall_thickness = 5
    map_data[0:wall_thickness, :] = 0  # Top wall
    map_data[-wall_thickness:, :] = 0  # Bottom wall
    map_data[:, 0:wall_thickness] = 0  # Left wall
    map_data[:, -wall_thickness:] = 0  # Right wall
    
    # Add interior walls/obstacles
    # Vertical wall in middle
    map_data[50:150, 95:105] = 0
    
    # Horizontal wall
    map_data[90:100, 30:80] = 0
    
    # Vertical wall on right side
    map_data[30:100, 140:150] = 0
    
    # Small boxes
    map_data[120:135, 50:65] = 0  # Box 1
    map_data[120:135, 140:155] = 0  # Box 2
    
    # L-shaped obstacle
    map_data[40:50, 160:175] = 0  # Horizontal part
    map_data[40:60, 170:180] = 0  # Vertical part
    
    # Save as PGM (binary format)
    pgm_file = os.path.join(maps_dir, "custom_map.pgm")
    with open(pgm_file, 'wb') as f:
        # PGM header
        f.write(b"P5\n")
        f.write(f"# Custom navigation map\n".encode())
        f.write(f"{width} {height}\n".encode())
        f.write(b"255\n")
        # Binary data
        f.write(map_data.tobytes())
    
    # Save YAML metadata
    yaml_file = os.path.join(maps_dir, "custom_map.yaml")
    with open(yaml_file, 'w') as f:
        f.write(f"""image: custom_map.pgm
mode: trinary
resolution: 0.05
origin: [-5.0, -5.0, 0.0]
negate: 0
occupied_thresh: 0.65
free_thresh: 0.25
""")
    
    print(f"Generated map: {pgm_file}")
    print(f"Generated config: {yaml_file}")
    return pgm_file, yaml_file


if __name__ == "__main__":
    generate_custom_map()
