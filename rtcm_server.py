#!/usr/bin/env python3
import argparse
import serial
import socket
import threading
import time
import random

SERIAL_PORT_DEFAULT = "/dev/tty.usbmodem1101"  # base F9P
BAUD_DEFAULT = 115200

TCP_HOST_DEFAULT = "0.0.0.0"
TCP_PORT_DEFAULT = 2101

clients = set()
lock = threading.Lock()

# Status-related globals
status_lock = threading.Lock()
last_data_time = None

rtcm_buf = bytearray()
last_rtcm_time = None
last_rtcm_types = set()

nmea_buf = ""
last_sats_in_view = None    # from GSV
last_fix_quality  = None    # from GGA (0 = no fix, 1 = GPS, 4/5 = RTK, etc.)
last_sats_used    = None    # from GGA
last_nmea_time    = None


# ---------------------------
# RTCM helpers (CRC-24Q)
# ---------------------------
CRC24Q_POLY = 0x1864CFB

def crc24q(data: bytes) -> int:
    crc = 0
    for b in data:
        crc ^= (b << 16) # ^= is XOR operator. << is left shift operator.
        for _ in range(8):
            crc <<= 1 # <<= is left shift assignment operator.
            if crc & 0x1000000: # & is bitwise AND operator.
                crc ^= CRC24Q_POLY # ^= is XOR assignment operator.
            crc &= 0xFFFFFF # &= is bitwise AND assignment operator.
    return crc # return the crc value.

def build_rtcm3_frame(msg_type: int, payload_len: int = 40) -> bytes:
    payload_len = max(6, min(payload_len, 900)) # payload is at least 6 bytes and at most 900 bytes.
    payload = bytearray(payload_len) # the bytearray is a list of bytes.

    # First 12 bits = msg type
    payload[0] = (msg_type >> 4) & 0xFF # >> is right shift operator. this line means the first 4 bits of the msg_type are the first 4 bits of the payload.
    payload[1] = ((msg_type & 0x0F) << 4) & 0xF0 # << is left shift operator. this line means the last 4 bits of the msg_type are the last 4 bits of the payload.

    # Fill rest with random bytes (NOT a valid correction payload) to make the payload length exactly payload_len.
    for i in range(2, payload_len):
        payload[i] = random.randrange(0, 256)

    length = payload_len
    hdr = bytearray(3) # header
    hdr[0] = 0xD3 # 0xD3 is the preamble.
    hdr[1] = (length >> 8) & 0x03 # this line means the first 8 bits of the length are the first 8 bits of the header.
    hdr[2] = length & 0xFF # & is bitwise AND operator. this line means the last 8 bits of the length are the last 8 bits of the header.

    frame_wo_crc = bytes(hdr + payload) # bytes(hdr + payload) is the frame without the crc.
    crc = crc24q(frame_wo_crc) # crc is the crc value of the frame without the crc.
    crc_bytes = bytes([(crc >> 16) & 0xFF, (crc >> 8) & 0xFF, crc & 0xFF]) # bytes([(crc >> 16) & 0xFF, (crc >> 8) & 0xFF, crc & 0xFF]) is the crc bytes.
    return frame_wo_crc + crc_bytes


def _find_rtcm_messages(data_buf):
    """Minimal RTCM3 frame scanner: returns (msgs, leftover_buf).

    msgs: list of (msg_type, length)
    """
    i = 0
    n = len(data_buf)
    results = []

    while i + 6 <= n:  # need at least preamble + length + crc
        # search for 0xD3 preamble
        if data_buf[i] != 0xD3:
            i += 1
            continue

        if i + 3 > n:
            break  # not enough data for length yet

        length = ((data_buf[i + 1] & 0x03) << 8) | data_buf[i + 2]
        frame_len = 3 + length + 3  # header + payload + 3-byte CRC

        if i + frame_len > n:
            break  # wait for more bytes

        # RTCM3 message header starts after 3 bytes (preamble+length)
        header0 = data_buf[i + 3]
        header1 = data_buf[i + 4]
        # message number: first 12 bits of header
        msg_type = ((header0 << 4) | (header1 >> 4)) & 0x0FFF

        results.append((msg_type, length))
        i += frame_len

    leftover = data_buf[i:]
    return results, leftover


def _update_nmea_status(data):
    """Very lightweight NMEA parsing, only for status info."""
    global nmea_buf, last_sats_in_view, last_fix_quality, last_sats_used, last_nmea_time

    # Decode as ASCII-ish, drop non-text (RTCM/UBX) bytes
    try:
        text = data.decode("ascii", errors="ignore")
    except Exception:
        return

    if not text:
        return

    nmea_buf += text
    lines = nmea_buf.split("\r\n")
    nmea_buf = lines[-1]  # leftover partial line

    for line in lines[:-1]:
        if not line.startswith("$"):
            continue

        # Strip checksum if present
        if "*" in line:
            line_no_cs = line.split("*", 1)[0]
        else:
            line_no_cs = line

        fields = line_no_cs.split(",")
        talker = fields[0]
        now = time.time()

        # GSV: satellites in view
        if talker in ("$GPGSV", "$GLGSV", "$GAGSV", "$GBGSV", "$GQGSV", "$GNGSV"):
            if len(fields) >= 4 and fields[3].isdigit():
                with status_lock:
                    last_sats_in_view = int(fields[3])
                    last_nmea_time = now

        # GGA: fix quality + satellites used
        elif talker in ("$GPGGA", "$GNGGA"):
            # 6: fix quality, 7: number of sats used
            if len(fields) >= 8:
                fix_q = fields[6]
                sats_used = fields[7]
                with status_lock:
                    last_fix_quality = fix_q if fix_q != "" else None
                    last_sats_used = int(sats_used) if sats_used.isdigit() else None
                    last_nmea_time = now


def _update_status(data):
    """Update global status based on incoming serial data."""
    global last_data_time, rtcm_buf, last_rtcm_time, last_rtcm_types

    now = time.time()
    with status_lock:
        last_data_time = now

        # RTCM detection
        rtcm_buf.extend(data)
        msgs, rtcm_buf = _find_rtcm_messages(rtcm_buf)
        if msgs:
            last_rtcm_time = now
            for mt, _ln in msgs:
                last_rtcm_types.add(mt)

    # NMEA parsing can safely run outside the status lock
    _update_nmea_status(data)


def status_printer():
    """Periodically print a human-readable status line."""
    while True:
        time.sleep(1.0)
        now = time.time()

        with status_lock:
            alive = last_data_time is not None and (now - last_data_time) < 3.0
            rtcm_ready = last_rtcm_time is not None and (now - last_rtcm_time) < 5.0
            rtcm_age = (now - last_rtcm_time) if last_rtcm_time is not None else None
            rtcm_types = sorted(last_rtcm_types) if last_rtcm_types else []

            sats_view = last_sats_in_view
            sats_used = last_sats_used
            fix_q = last_fix_quality
            have_nmea_recent = last_nmea_time is not None and (now - last_nmea_time) < 5.0

            num_clients = len(clients)

        sats_visible = sats_view is not None and sats_view > 0 and have_nmea_recent

        rtcm_desc = "NO (none seen yet)"
        if rtcm_ready:
            rtcm_desc = "YES"
            if rtcm_types:
                rtcm_desc += f" types={rtcm_types}"
            if rtcm_age is not None:
                rtcm_desc += f" last_seen={rtcm_age:.1f}s ago"

        fix_desc = "unknown"
        if have_nmea_recent:
            if fix_q is None or fix_q == "0":
                fix_desc = "no fix"
            elif fix_q in ("4", "5"):
                fix_desc = "RTK"
            else:
                fix_desc = f"fix_q={fix_q}"

        print(
            f"[STATUS] alive={alive} "
            f"clients={num_clients} "
            f"sats_visible={sats_visible} (in_view={sats_view}, used={sats_used}) "
            f"fix={fix_desc} "
            f"RTCM_ready={rtcm_desc}"
        )


def _broadcast(data: bytes):
    _update_status(data)
    with lock:
        dead = []
        for c in clients:
            try:
                c.sendall(data)
            except Exception:
                dead.append(c)
        for d in dead:
            clients.discard(d)


def serial_reader(serial_port: str, baud: int):
    ser = serial.Serial(serial_port, baud, timeout=1)
    print(f"[SERVER] Reading RTCM/UBX from {serial_port} @ {baud}")
    while True:
        data = ser.read(4096)
        # print(f"data: {data}")
        if not data:
            continue
        _broadcast(data)


def demo_broadcaster(rate_hz: float, payload_len: int, also_nmea: bool):
    print(f"[DEMO] Broadcasting synthetic RTCM3 frames @ {rate_hz} Hz")
    next_t = time.time()
    demo_types = [1005, 1077, 1087, 1097, 1127, 1230]

    while True:
        now = time.time()
        if now < next_t:
            time.sleep(min(0.05, next_t - now))
            continue
        next_t += 1.0 / max(rate_hz, 0.1)

        mt = random.choice(demo_types)
        frame = build_rtcm3_frame(mt, payload_len=payload_len)
        _broadcast(frame)

        if also_nmea:
            nmea = (
                "$GNGGA,000000.00,3736.75000,N,12659.66000,E,1,12,0.9,100.0,M,18.0,M,,*00\r\n"
                "$GPGSV,1,1,12,01,40,100,30,02,50,110,35,03,60,120,40,04,30,130,25*00\r\n"
            ).encode("ascii", errors="ignore")
            _broadcast(nmea)


def handle_client(conn, addr):
    print(f"[SERVER] Client connected: {addr}")
    with lock:
        clients.add(conn)
    try:
        # We don't expect any data from clients; just keep connection alive
        while True:
            if not conn.recv(1024):
                break
    except Exception:
        pass
    finally:
        print(f"[SERVER] Client disconnected: {addr}")
        with lock:
            clients.discard(conn)
        conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="Run demo RTCM broadcaster (no serial required)")
    parser.add_argument("--host", type=str, default=TCP_HOST_DEFAULT, help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=TCP_PORT_DEFAULT, help="Bind port (default: 2101)")
    parser.add_argument("--serial", type=str, default=SERIAL_PORT_DEFAULT, help="Serial port (non-demo)")
    parser.add_argument("--baud", type=int, default=BAUD_DEFAULT, help="Serial baud (non-demo)")
    parser.add_argument("--demo_rate", type=float, default=2.0, help="Demo frame rate (Hz)")
    parser.add_argument("--demo_len", type=int, default=80, help="Demo payload length (bytes)")
    parser.add_argument("--demo_no_nmea", action="store_true", help="Disable fake NMEA in demo mode")
    args = parser.parse_args()

    threading.Thread(target=status_printer, daemon=True).start()

    if args.demo:
        threading.Thread(
            target=demo_broadcaster,
            args=(args.demo_rate, args.demo_len, not args.demo_no_nmea),
            daemon=True
        ).start()
    else:
        threading.Thread(target=serial_reader, args=(args.serial, args.baud), daemon=True).start()

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((args.host, args.port))
    s.listen(5)
    print(f"[SERVER] Listening for clients on {args.host}:{args.port}")

    while True:
        conn, addr = s.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()


if __name__ == "__main__":
    main()