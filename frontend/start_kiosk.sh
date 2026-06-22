#!/bin/bash
# ==============================================================================
#  Lab Buddy — Raspberry Pi Kiosk Startup Script
#  Run this script on Raspberry Pi boot to start the Robot Display GUI
#  in a locked-down Chromium fullscreen mode.
# ==============================================================================

# 1. Disable screensaver, blanking, and display power management (DPMS)
echo "Configuring display settings..."
xset s noblank
xset s off
xset -dpms

# 2. Hide mouse cursor after 0.5s of inactivity (requires unclutter package)
if command -v unclutter &> /dev/null; then
    echo "Hiding mouse cursor..."
    unclutter -idle 0.5 -root &
else
    echo "Warning: 'unclutter' is not installed. Mouse cursor will remain visible."
fi

# 3. Clean up Chromium crash states (prevents 'Chrome did not shut down correctly' alerts)
echo "Cleaning up Chromium crash preferences..."
PREFS_FILE="$HOME/.config/chromium/Default/Preferences"
if [ -f "$PREFS_FILE" ]; then
    sed -i 's/"exit_type":"Crashed"/"exit_type":"Normal"/' "$PREFS_FILE"
    sed -i 's/"exited_cleanly":false/"exited_cleanly":true/' "$PREFS_FILE"
fi

# 4. Wait for local backend/frontend services to become available (checks port 3000)
echo "Waiting for Lab Buddy UI to load..."
until $(curl --output /dev/null --silent --head --fail http://localhost:3000/robot-display); do
    printf '.'
    sleep 2
done
echo "Lab Buddy UI detected!"

# 5. Launch Chromium in Kiosk Mode pointing to the display page
echo "Launching Chromium in kiosk mode..."
chromium-browser \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --disable-pinch \
    --overscroll-history-navigation=0 \
    --check-for-update-interval=31536000 \
    --incognito \
    http://localhost:3000/robot-display
