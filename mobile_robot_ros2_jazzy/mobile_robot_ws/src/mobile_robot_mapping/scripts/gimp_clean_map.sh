#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
#  gimp_clean_map.sh — despeckle + re-quantize a saved SLAM map, no GUI.
#
#  USAGE:
#    ./gimp_clean_map.sh <input_map.pgm> <output_map_clean.pgm> \
#                         [despeckle_radius] [black_cutoff] [white_cutoff]
#
#  EXAMPLE:
#    ./gimp_clean_map.sh maps/lab_map.pgm maps/lab_map_clean.pgm 2
#
#  Also copies/updates the paired .yaml so the cleaned map is immediately
#  usable with Nav2 (image: field repointed to the new filename; resolution,
#  origin, thresholds all carried over unchanged).
#
#  REQUIRES: GIMP installed with Script-Fu (standard on any GIMP install).
#    sudo apt install gimp
# ═══════════════════════════════════════════════════════════════════════════
set -e

if [ -z "$1" ] || [ -z "$2" ]; then
  echo "Usage: $0 <input_map.pgm> <output_map_clean.pgm> [despeckle_radius] [black_cutoff] [white_cutoff]"
  exit 1
fi

IN="$1"
OUT="$2"
RADIUS="${3:-2}"      # despeckle radius in px — raise if noise is coarser, lower to preserve fine detail
BLACK="${4:--1}"      # -1 = use full range (see .scm comments)
WHITE="${5:-256}"     # 256 = use full range

if [ ! -f "$IN" ]; then
  echo "ERROR: input map not found: $IN"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/gimp_clean_map.scm" ]; then
  SCM_FILE="$SCRIPT_DIR/gimp_clean_map.scm"
elif [ -f "$SCRIPT_DIR/../../share/mobile_robot_mapping/scripts/gimp_clean_map.scm" ]; then
  SCM_FILE="$SCRIPT_DIR/../../share/mobile_robot_mapping/scripts/gimp_clean_map.scm"
else
  echo "ERROR: gimp_clean_map.scm not found!"
  exit 1
fi

echo "Running GIMP batch cleanup on: $IN"
echo "  despeckle_radius=$RADIUS"

gimp -i -b "(load \"$SCM_FILE\") (clean-map-batch \"$IN\" \"$OUT\" $RADIUS $BLACK $WHITE) (gimp-quit 0)"

echo "Cleaned map written to: $OUT"

# ── Keep the paired YAML in sync ────────────────────────────────────────────
YAML_IN="${IN%.*}.yaml"
YAML_OUT="${OUT%.*}.yaml"

if [ -f "$YAML_IN" ]; then
  sed "s#image: .*#image: $(basename "$OUT")#" "$YAML_IN" > "$YAML_OUT"
  echo "Updated YAML written to: $YAML_OUT (image: field repointed to $(basename "$OUT"))"
else
  echo "WARNING: no paired YAML found at $YAML_IN — copy/edit one manually before using this map in Nav2."
fi

echo ""
echo "Tip: open both $IN and $OUT side by side in an image viewer before"
echo "trusting the cleaned version — over-aggressive despeckling can erase"
echo "thin real features (doorways, chair/table legs) along with noise."
