#!/usr/bin/env python3
import serial
import socket
import threading
import time

SERIAL_PORT = "/dev/tty.usbmodem1101"  # base F9P
BAUD = 115200

TCP_HOST = "0.0.0.0"
TCP_PORT = 2101

clients = set()
lock = threading.Lock()

# Status-related globals
status_lock = threading.Lock()
last_data_time = None

rtcm_buf = bytearray()
last_rtcm_time = None
last_rtcm_types = set()

nmea_buf = ""
last_sats_in_view = None  # from GSV
last_fix_quality = None   # from GGA (0 = no fix, 1 = GPS, 4/5 = RTK, etc.)
last_sats_used = None     # from GGA
last_nmea_time = None


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
            if len(fields) >= 4:
                total_sats_str = fields[3]
                if total_sats_str.isdigit():
                    with status_lock:
                        last_sats_in_view = int(total_sats_str)
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


def serial_reader():
    ser = serial.Serial(SERIAL_PORT, BAUD, timeout=1)
    print(f"[SERVER] Reading RTCM/UBX from {SERIAL_PORT} @ {BAUD}")
    while True:
        data = ser.read(4096)
        if not data:
            continue

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
    threading.Thread(target=serial_reader, daemon=True).start()
    threading.Thread(target=status_printer, daemon=True).start()

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((TCP_HOST, TCP_PORT))
    s.listen(5)
    print(f"[SERVER] Listening for RTCM clients on {TCP_HOST}:{TCP_PORT}")

    while True:
        conn, addr = s.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()


if __name__ == "__main__":
    main()