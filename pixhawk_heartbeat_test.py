#!/usr/bin/env python3
from pymavlink import mavutil

DEVICE = "/dev/ttyACM0"  # change to ACM1/ACM2 if needed
BAUD = 115200

print(f"Connecting to {DEVICE} @ {BAUD}...")
m = mavutil.mavlink_connection(DEVICE, baud=BAUD)

print("Waiting for heartbeat (10s timeout)...")
msg = m.recv_match(type="HEARTBEAT", blocking=True, timeout=10)

if msg is None:
    print("❌ No heartbeat received. Check device path, power, permissions, ModemManager, etc.")
else:
    print("✅ Heartbeat received:")
    print(msg)

