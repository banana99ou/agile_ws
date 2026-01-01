#!/bin/bash

# --- CONFIGURATION ---
CON_NAME="LIMO_AP"
# Find the Wi-Fi interface automatically (usually wlo1 or wlan0)
WIFI_IF=$(nmcli -t -f DEVICE,TYPE device | grep ":wifi" | cut -d: -f1 | head -n1)

echo "--- Starting $CON_NAME on $WIFI_IF ---"

# 1. Ensure Wi-Fi hardware is on
nmcli radio wifi on

# 2. Force apply the Apple-compatibility fix (PMF=1 means disabled)
# This acts as a 'safety check' in case the settings were ever reset.
sudo nmcli connection modify "$CON_NAME" 802-11-wireless-security.pmf 1
sudo iw reg set KR
# 3. Bring the connection up
# We use 'down' first to ensure a fresh handshake
sudo nmcli connection down "$CON_NAME" 2>/dev/null
sudo nmcli connection up "$CON_NAME"

echo "Hotspot $CON_NAME is now ACTIVE."
