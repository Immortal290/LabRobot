#!/usr/bin/env python3
"""
generate_lab_map.py
─────────────────────────────────────────────────────────────
Generates a PGM occupancy grid map of the lab world.

Lab world (matches lab_world.sdf):
  - 10 × 10 m space centred at (0, 0)
  - Outer walls (0.2 m thick)
  - Table 1  at (2, 2),   size 1.0 × 0.6 m
  - Table 2  at (-2, 2),  size 1.0 × 0.6 m
  - Box 1    at (0, 1),   size 0.4 × 0.4 m
  - Box 2    at (2, -1),  size 0.4 × 0.4 m
  - Cylinder at (-2, -2), radius 0.3 m

Resolution: 0.05 m/pixel  →  200 × 200 pixels
"""

import struct
import math
import os

# ── Map parameters ────────────────────────────────────────────
RESOLUTION = 0.05       # metres per pixel
WIDTH      = 200        # pixels  (200 * 0.05 = 10 m)
HEIGHT     = 200
ORIGIN_X   = -5.0       # world X of bottom-left pixel
ORIGIN_Y   = -5.0       # world Y of bottom-left pixel

FREE     = 254          # white  (free space)
OCCUPIED = 0            # black  (obstacle)
UNKNOWN  = 127          # grey   (unknown)

# ── Coordinate helpers ────────────────────────────────────────

def w2p(wx, wy):
    """World → pixel  (px, py) — py=0 is BOTTOM row."""
    px = int((wx - ORIGIN_X) / RESOLUTION)
    py = int((wy - ORIGIN_Y) / RESOLUTION)
    return px, py

def p_idx(px, py):
    """Pixel → array index  (row 0 = BOTTOM in this grid)."""
    # PGM row 0 is the TOP of the image, so we flip py
    row = (HEIGHT - 1) - py
    col = px
    return row * WIDTH + col

# ── Build grid ────────────────────────────────────────────────
grid = [FREE] * (WIDTH * HEIGHT)

def fill_rect(cx, cy, hw, hh, value=OCCUPIED):
    """Fill a rectangle centred at (cx,cy) with half-widths hw, hh."""
    for wx in [cx + (i - 0.5) * RESOLUTION for i in range(
            int((cx - hw - ORIGIN_X) / RESOLUTION),
            int((cx + hw - ORIGIN_X) / RESOLUTION) + 2)]:
        for wy in [cy + (j - 0.5) * RESOLUTION for j in range(
                int((cy - hh - ORIGIN_Y) / RESOLUTION),
                int((cy + hh - ORIGIN_Y) / RESOLUTION) + 2)]:
            px, py = w2p(wx, wy)
            if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                grid[p_idx(px, py)] = value

def fill_rect_v2(cx, cy, hw, hh, value=OCCUPIED):
    """Fill a rectangle by pixel range."""
    px0, py0 = w2p(cx - hw, cy - hh)
    px1, py1 = w2p(cx + hw, cy + hh)
    for py in range(max(0, py0), min(HEIGHT, py1 + 1)):
        for px in range(max(0, px0), min(WIDTH, px1 + 1)):
            grid[p_idx(px, py)] = value

def fill_circle(cx, cy, radius, value=OCCUPIED):
    """Fill a circle centred at (cx, cy) with given radius."""
    r_px = int(radius / RESOLUTION) + 1
    pcx, pcy = w2p(cx, cy)
    for dy in range(-r_px, r_px + 1):
        for dx in range(-r_px, r_px + 1):
            if dx * dx + dy * dy <= (radius / RESOLUTION) ** 2:
                px = pcx + dx
                py = pcy + dy
                if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                    grid[p_idx(px, py)] = value

WALL_T = 0.15   # wall half-thickness (m)

# Outer walls
fill_rect_v2(-5.0 + WALL_T, 0.0,  WALL_T, 5.0)   # left wall
fill_rect_v2( 5.0 - WALL_T, 0.0,  WALL_T, 5.0)   # right wall
fill_rect_v2( 0.0, -5.0 + WALL_T, 5.0,  WALL_T)  # bottom wall
fill_rect_v2( 0.0,  5.0 - WALL_T, 5.0,  WALL_T)  # top wall

# Tables
fill_rect_v2( 2.0,  2.0, 0.5, 0.3)   # Table 1
fill_rect_v2(-2.0,  2.0, 0.5, 0.3)   # Table 2

# Boxes
fill_rect_v2( 0.0,  1.0, 0.2, 0.2)   # Box 1 (red)
fill_rect_v2( 2.0, -1.0, 0.2, 0.2)   # Box 2 (green)

# Cylinder
fill_circle(-2.0, -2.0, 0.3)         # Yellow cylinder

# ── Write PGM (P5 binary) ─────────────────────────────────────
out_dir = os.path.join(os.path.dirname(__file__),
                       "..", "maps")
out_dir = os.path.abspath(out_dir)
os.makedirs(out_dir, exist_ok=True)

pgm_path  = os.path.join(out_dir, "lab_world_map.pgm")
yaml_path = os.path.join(out_dir, "lab_world_map.yaml")

with open(pgm_path, "wb") as f:
    # P5 header
    header = f"P5\n{WIDTH} {HEIGHT}\n255\n"
    f.write(header.encode("ascii"))
    f.write(bytes(grid))

print(f"✓ PGM written: {pgm_path}")

# ── Write YAML map descriptor ─────────────────────────────────
yaml_content = f"""image: lab_world_map.pgm
resolution: {RESOLUTION}
origin: [{ORIGIN_X}, {ORIGIN_Y}, 0.0]
negate: 0
occupied_thresh: 0.65
free_thresh: 0.196
"""
with open(yaml_path, "w") as f:
    f.write(yaml_content)

print(f"✓ YAML written: {yaml_path}")
print(f"  Map size : {WIDTH} × {HEIGHT} px  ({WIDTH*RESOLUTION:.1f} × {HEIGHT*RESOLUTION:.1f} m)")
print(f"  Origin   : ({ORIGIN_X}, {ORIGIN_Y})")
print(f"  Resolution: {RESOLUTION} m/px")
