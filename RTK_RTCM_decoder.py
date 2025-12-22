#!/usr/bin/env python3
import serial
import struct

PORT = "/dev/ttyACM0"   # rover F9P
BAUD = 115200

SYNC1 = 0xB5
SYNC2 = 0x62
NAV_CLASS = 0x01
NAV_PVT_ID = 0x07

def ubx_checksum(data: bytes):
    ck_a = 0
    ck_b = 0
    for b in data:
        ck_a = (ck_a + b) & 0xFF
        ck_b = (ck_b + ck_a) & 0xFF
    return ck_a, ck_b

def read_ubx_nav_pvt(ser):
    while True:
        b = ser.read(1)
        if not b:
            return None
        if b[0] != SYNC1:
            continue

        b2 = ser.read(1)
        if not b2 or b2[0] != SYNC2:
            continue

        hdr = ser.read(4)
        if len(hdr) < 4:
            return None

        msg_class, msg_id, length = hdr[0], hdr[1], hdr[2] | (hdr[3] << 8)

        payload = ser.read(length)
        if len(payload) < length:
            return None

        ck = ser.read(2)
        if len(ck) < 2:
            return None
        ck_a_rx, ck_b_rx = ck[0], ck[1]

        # verify checksum over class+id+len+payload
        ck_a_calc, ck_b_calc = ubx_checksum(bytes([msg_class, msg_id, hdr[2], hdr[3]]) + payload)
        if ck_a_calc != ck_a_rx or ck_b_calc != ck_b_rx:
            # bad frame; skip
            continue

        if msg_class == NAV_CLASS and msg_id == NAV_PVT_ID:
            return payload

def parse_nav_pvt(payload):
    if len(payload) < 36:
        return None

    iTOW, year, month, day, hour, minute, second, valid = struct.unpack_from("<I H B B B B B B", payload, 0)
    fixType = payload[20]
    flags = payload[21]
    flags2 = payload[22]
    numSV = payload[23]
    lon, lat, height, hMSL = struct.unpack_from("<iiii", payload, 24)

    lat_deg = lat / 1e7
    lon_deg = lon / 1e7
    h_m = hMSL / 1000.0

    carrSoln = (flags2 >> 3) & 0x03  # 0=no, 1=float, 2=fixed

    return {
        "time": (hour, minute, second),
        "fixType": fixType,
        "carrSoln": carrSoln,
        "numSV": numSV,
        "lat": lat_deg,
        "lon": lon_deg,
        "h": h_m,
    }

def describe_fix(fixType, carrSoln):
    base = {
        0: "no fix",
        2: "2D",
        3: "3D",
        4: "GNSS+DR",
        5: "time only"
    }.get(fixType, f"unknown({fixType})")

    # If there is no valid position fix, don’t claim RTK
    if fixType < 3:
        return f"{base}, no RTK"

    if carrSoln == 0:
        rtk = "no RTK"
    elif carrSoln == 1:
        rtk = "RTK float"
    elif carrSoln == 2:
        rtk = "RTK fixed"
    else:
        rtk = f"carrSoln={carrSoln}"

    return f"{base}, {rtk}"

def main():
    ser = serial.Serial(PORT, BAUD, timeout=1)
    print(f"Listening for UBX-NAV-PVT on {PORT} @ {BAUD}...")
    while True:
        payload = read_ubx_nav_pvt(ser)
        if not payload:
            continue
        n = parse_nav_pvt(payload)
        if not n:
            continue
        hh, mm, ss = n["time"]
        desc = describe_fix(n["fixType"], n["carrSoln"])
        print(f"{hh:02d}:{mm:02d}:{ss:02d} | {desc} | SV={n['numSV']} | "
              f"lat={n['lat']:.7f}, lon={n['lon']:.7f}, h={n['h']:.2f} m")

if __name__ == "__main__":
    main()
