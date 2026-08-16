#!/usr/bin/env bash
# =============================================================================
#  AURA — Master Startup Script
#  /home/sam/Desktop/labass/LabRobot/startup/aura_start.sh
#
#  Usage:
#    ./startup/aura_start.sh             # Full production stack
#    ./startup/aura_start.sh --mock      # Mock mode (no hardware required)
#    ./startup/aura_start.sh --ros-only  # Skip Docker, only launch ROS2 nodes
#    ./startup/aura_start.sh --docker    # Launch Docker stack only
#
#  This script:
#    1. Validates environment (Ubuntu 24.04, ROS 2 Jazzy, Python 3.12)
#    2. Sources ROS2 workspace
#    3. Verifies PostgreSQL / Docker
#    4. Starts Docker compose stack (backend + DB + frontend)
#    5. Waits for backend health check
#    6. Verifies serial connections (Arduino, LiDAR)
#    7. Launches all ROS2 nodes via ros2 launch
#    8. Opens the kiosk browser in full-screen
#    9. Provides a live monitoring view
# =============================================================================

set -euo pipefail

# ── Colour helpers ─────────────────────────────────────────────────────────────
RED='\033[0;31m';  GREEN='\033[0;32m';  YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m';      RESET='\033[0m'

ok()   { echo -e "${GREEN}  ✓${RESET}  $*"; }
fail() { echo -e "${RED}  ✗${RESET}  $*"; }
info() { echo -e "${CYAN}  ▸${RESET}  $*"; }
warn() { echo -e "${YELLOW}  ⚠${RESET}  $*"; }
hdr()  { echo -e "\n${BOLD}${CYAN}═══ $* ═══${RESET}"; }

# ── Parse arguments ────────────────────────────────────────────────────────────
MOCK=false
ROS_ONLY=false
DOCKER_ONLY=false

for arg in "$@"; do
  case $arg in
    --mock)        MOCK=true        ;;
    --ros-only)    ROS_ONLY=true    ;;
    --docker)      DOCKER_ONLY=true ;;
    *) warn "Unknown argument: $arg" ;;
  esac
done

# ── Configuration ──────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ROS2_WS="$PROJECT_DIR/ros2_ws"
ROS2_INSTALL="$ROS2_WS/install"
LOG_DIR="$PROJECT_DIR/logs"
BACKEND_URL="http://localhost:8000/api/v1"
FRONTEND_URL="http://localhost:3000/robot-display"
ARDUINO_PORT="${ARDUINO_PORT:-/dev/ttyUSB0}"
LIDAR_PORT="${LIDAR_PORT:-/dev/ttyUSB1}"

mkdir -p "$LOG_DIR"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/aura_startup_$TIMESTAMP.log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   AURA — Lab Delivery Robot Startup System  ║"
echo "║   $(date '+%Y-%m-%d %H:%M:%S')                     ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── Step 1: Environment validation ─────────────────────────────────────────────
hdr "Step 1: Environment Validation"

if [[ "$(uname -s)" != "Linux" ]]; then
  fail "This script requires Linux (Ubuntu 24.04)."
  exit 1
fi
ok "Linux detected"

if command -v ros2 &>/dev/null; then
  ROS_VER=$(ros2 --version 2>&1 | head -1)
  ok "ROS2 available: $ROS_VER"
else
  fail "ROS2 not found. Install ROS 2 Jazzy first."
  if ! $MOCK; then exit 1; fi
  warn "Continuing in MOCK mode without ROS2"
fi

if command -v python3 &>/dev/null; then
  PY_VER=$(python3 --version)
  ok "Python: $PY_VER"
else
  fail "python3 not found"; exit 1
fi

if command -v docker &>/dev/null; then
  ok "Docker: $(docker --version | cut -d' ' -f3)"
else
  fail "Docker not found"; exit 1
fi

if command -v docker compose &>/dev/null; then
  ok "docker compose available"
else
  fail "docker compose not found"; exit 1
fi

# ── Step 2: Source ROS2 workspace ──────────────────────────────────────────────
hdr "Step 2: ROS2 Workspace"

ROS2_SETUP="/opt/ros/jazzy/setup.bash"
if [[ -f "$ROS2_SETUP" ]]; then
  # shellcheck disable=SC1090
  source "$ROS2_SETUP"
  ok "Sourced ROS2 Jazzy: $ROS2_SETUP"
else
  warn "ROS2 Jazzy setup.bash not found at $ROS2_SETUP"
fi

if [[ -f "$ROS2_INSTALL/setup.bash" ]]; then
  # shellcheck disable=SC1090
  source "$ROS2_INSTALL/setup.bash"
  ok "Sourced local workspace: $ROS2_INSTALL/setup.bash"
else
  info "Local workspace not yet built — building now…"
  cd "$ROS2_WS"
  if colcon build --symlink-install --packages-select aura_msgs aura_robot 2>&1; then
    # shellcheck disable=SC1090
    source "$ROS2_INSTALL/setup.bash"
    ok "Workspace built and sourced."
  else
    warn "Workspace build failed. Nodes will run from source directly."
  fi
  cd "$PROJECT_DIR"
fi

# ── Step 3: Docker stack ───────────────────────────────────────────────────────
if ! $ROS_ONLY; then
  hdr "Step 3: Docker Stack (DB + Backend + Frontend)"

  cd "$PROJECT_DIR"
  info "Starting Docker compose services…"
  docker compose up -d db backend frontend ros_bridge hardware 2>&1 | tail -5
  ok "Docker services started."

  # Wait for backend to be ready (up to 60 s)
  info "Waiting for backend health…"
  DEADLINE=$(( $(date +%s) + 60 ))
  BACKEND_UP=false
  while [[ $(date +%s) -lt $DEADLINE ]]; do
    if curl -sf "$BACKEND_URL/config" -o /dev/null 2>/dev/null; then
      BACKEND_UP=true; break
    fi
    printf "."
    sleep 2
  done
  echo ""

  if $BACKEND_UP; then
    ok "Backend is healthy at $BACKEND_URL"
  else
    warn "Backend did not respond in 60 s — proceeding anyway."
  fi
fi

if $DOCKER_ONLY; then
  info "Docker-only mode — skipping ROS2 launch."
  hdr "Done"
  ok "Docker stack running. Frontend: $FRONTEND_URL"
  exit 0
fi

# ── Step 4: Hardware verification ─────────────────────────────────────────────
hdr "Step 4: Hardware Verification"

# Arduino
if [[ -e "$ARDUINO_PORT" ]]; then
  ok "Arduino detected: $ARDUINO_PORT"
elif [[ -e "/dev/ttyACM0" ]]; then
  ARDUINO_PORT="/dev/ttyACM0"
  ok "Arduino detected (auto): $ARDUINO_PORT"
else
  warn "Arduino Nano not found. Servo control will run in mock mode."
fi

# LiDAR
if [[ -e "$LIDAR_PORT" ]]; then
  ok "YDLIDAR X4 detected: $LIDAR_PORT"
else
  warn "LiDAR not found at $LIDAR_PORT. Navigation may be limited."
fi

# PostgreSQL via Docker
PG_OK=false
if docker exec labrobot_db pg_isready -U robot_user -d labrobot &>/dev/null 2>&1; then
  PG_OK=true; ok "PostgreSQL ready inside Docker container."
elif command -v pg_isready &>/dev/null && pg_isready -h localhost -p 5435 -U robot_user -d labrobot &>/dev/null 2>&1; then
  PG_OK=true; ok "PostgreSQL ready on localhost:5435."
else
  warn "PostgreSQL not reachable — database features may be degraded."
fi

# ── Step 5: Launch ROS2 nodes ──────────────────────────────────────────────────
hdr "Step 5: ROS2 Node Launch"

LAUNCH_ARGS="mock:=$MOCK"
LAUNCH_ARGS="$LAUNCH_ARGS arduino_port:=$ARDUINO_PORT"
LAUNCH_ARGS="$LAUNCH_ARGS lidar_port:=$LIDAR_PORT"
LAUNCH_ARGS="$LAUNCH_ARGS db_url:=postgresql://robot_user:robot_password@localhost:5435/labrobot"
LAUNCH_ARGS="$LAUNCH_ARGS backend_url:=ws://localhost:8000/ws/bridge"
LAUNCH_ARGS="$LAUNCH_ARGS backend_api_url:=http://localhost:8000/api/v1"

ROS2_LOG="$LOG_DIR/ros2_nodes_$TIMESTAMP.log"

info "Launching: ros2 launch aura_robot aura_full_system.launch.py $LAUNCH_ARGS"

# Launch in background, redirect to log
ros2 launch aura_robot aura_full_system.launch.py \
  $LAUNCH_ARGS \
  > "$ROS2_LOG" 2>&1 &
ROS2_PID=$!
ok "ROS2 nodes launched (PID $ROS2_PID). Log: $ROS2_LOG"

# Wait for bridge to announce itself
sleep 6

# ── Step 6: Open kiosk GUI ────────────────────────────────────────────────────
hdr "Step 6: Kiosk GUI"

BROWSER_CMD=""
for cmd in chromium-browser chromium google-chrome firefox; do
  if command -v "$cmd" &>/dev/null; then
    BROWSER_CMD="$cmd"; break
  fi
done

if [[ -n "$BROWSER_CMD" ]]; then
  # Full-screen kiosk mode — no borders, no address bar, no cursor
  info "Opening kiosk: $FRONTEND_URL"
  DISPLAY="${DISPLAY:-:0}" $BROWSER_CMD \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --disable-restore-session-state \
    --no-first-run \
    --start-fullscreen \
    --app="$FRONTEND_URL" \
    &>/dev/null &
  ok "Kiosk opened in $BROWSER_CMD"
else
  warn "No browser found — open $FRONTEND_URL manually."
fi

# ── Step 7: Status summary & live monitoring ──────────────────────────────────
hdr "System Online"
echo ""
echo "  🤖  Robot:       AURA — Lab Delivery Robot"
echo "  🌐  Frontend:    $FRONTEND_URL"
echo "  🔧  Backend API: $BACKEND_URL"
echo "  📄  Startup log: $LOG_FILE"
echo "  📄  ROS2 log:    $ROS2_LOG"
echo ""
echo "  Press Ctrl+C to shut down all services."
echo ""

# ── Cleanup on exit ───────────────────────────────────────────────────────────
cleanup() {
  echo ""
  hdr "Shutting Down AURA"
  if [[ -n "${ROS2_PID:-}" ]]; then
    kill "$ROS2_PID" 2>/dev/null && ok "ROS2 nodes stopped."
  fi
  if ! $ROS_ONLY; then
    cd "$PROJECT_DIR"
    docker compose stop && ok "Docker services stopped."
  fi
  ok "Goodbye."
}
trap cleanup EXIT INT TERM

# Keep script alive — tail ROS2 log for live monitoring
tail -f "$ROS2_LOG" 2>/dev/null || wait $ROS2_PID
