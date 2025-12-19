#!/usr/bin/env python3
import threading
import socket
import serial
import time
import pynmea2
from dataclasses import dataclass, field
from typing import Optional

# -------------- CONFIG --------------

# Change this if your F9P USB appears differently
SERIAL_PORT = "/dev/ttyACM0"
SERIAL_BAUD = 57600      # you said 57600

TCP_HOST = "10.0.0.42"   # your broadcaster
TCP_PORT = 2101          # your broadcaster port

STATUS_PRINT_INTERVAL = 1.0   # seconds
RTCM_STALE_SECONDS = 5.0      # consider RTCM stale after this

# -------------- STATE --------------

@dataclass
class GNSSStatus:
    lat: Optional[float] = None
    lon: Optional[float] = None
    fix_quality: int = 0
    fix_desc: str = "NO FIX"
    num_sats: int = 0
    hdop: Optional[float] = None
    last_gps_time: float = field(default_factory=time.time)

@dataclass
class RTCMStatus:
    total_bytes: int = 0
    last_rx_time: float = 0.0

# -------------- HELPERS --------------

class SerialManager:
    """Thread-safe serial wrapper that auto-reopens on error."""

    def __init__(self, port: str, baud: int, timeout: float = 1.0):
        self._port = port
        self._baud = baud
        self._timeout = timeout
        self._lock = threading.Lock()
        self._ser: Optional[serial.Serial] = None
        self._open_serial(initial=True)

    def _open_serial(self, initial: bool = False):
        while True:
            try:
                print(f"[SERIAL] Opening {self._port} @ {self._baud} ...")
                self._ser = serial.Serial(self._port, self._baud, timeout=self._timeout)
                print("[SERIAL] Serial opened.")
                return
            except serial.SerialException as e:
                phase = "initial open" if initial else "re-open"
                print(f"[SERIAL] {phase} failed: {e}. Retrying in 2s...")
                time.sleep(2.0)

    def _reopen_serial(self):
        with self._lock:
            try:
                if self._ser is not None:
                    self._ser.close()
            except Exception:
                pass
            self._ser = None
        self._open_serial()

    def write(self, data: bytes):
        while True:
            try:
                with self._lock:
                    if self._ser is None:
                        raise serial.SerialException("Serial not open")
                    self._ser.write(data)
                    self._ser.flush()
                return
            except serial.SerialException as e:
                print(f"[SERIAL] Write error: {e}. Reopening port...")
                self._reopen_serial()

    def readline(self) -> bytes:
        while True:
            try:
                with self._lock:
                    if self._ser is None:
                        raise serial.SerialException("Serial not open")
                    return self._ser.readline()
            except serial.SerialException as e:
                print(f"[SERIAL] Read error: {e}. Reopening port...")
                self._reopen_serial()

    def close(self):
        with self._lock:
            if self._ser is not None:
                try:
                    self._ser.close()
                except Exception:
                    pass
                self._ser = None


def fix_quality_to_desc(q: int) -> str:
    mapping = {
        0: "NO FIX",
        1: "GPS",
        2: "DGPS",
        3: "PPS",
        4: "RTK FIXED",
        5: "RTK FLOAT",
        6: "DEAD RECKONING",
        7: "MANUAL",
        8: "SIMULATION",
    }
    return mapping.get(q, f"UNKNOWN({q})")

# -------------- THREADS --------------

def rtcm_forwarder(ser_mgr: SerialManager, rtcm_status: RTCMStatus, stop_event: threading.Event):
    """Connect to your TCP RTCM broadcaster and pump bytes into F9P."""
    while not stop_event.is_set():
        try:
            print(f"[RTCM] Connecting to {TCP_HOST}:{TCP_PORT} ...")
            with socket.create_connection((TCP_HOST, TCP_PORT), timeout=10) as sock:
                sock.settimeout(5.0)
                print("[RTCM] Connected. Receiving RTCM3 and forwarding to F9P...")

                while not stop_event.is_set():
                    try:
                        data = sock.recv(4096)
                        if not data:
                            print("[RTCM] Connection closed by remote.")
                            break
                        # Feed F9P: this is where RTCM3 actually goes into the Helical
                        ser_mgr.write(data)

                        rtcm_status.total_bytes += len(data)
                        rtcm_status.last_rx_time = time.time()
                    except socket.timeout:
                        # No data in this interval; just loop
                        continue
        except (socket.error, OSError) as e:
            print(f"[RTCM] Connection error: {e}. Retrying in 5s...")
            time.sleep(5)


def nmea_reader(ser_mgr: SerialManager, gnss_status: GNSSStatus, stop_event: threading.Event):
    """Read NMEA from F9P and update GNSS status."""
    while not stop_event.is_set():
        try:
            line_bytes = ser_mgr.readline()
            if not line_bytes:
                continue

            # NMEA sentences are ASCII starting with '$'
            line = line_bytes.decode("ascii", errors="ignore").strip()
            if not line.startswith("$"):
                # probably UBX or other binary, ignore
                continue

            # Uncomment for debugging raw NMEA:
            # print(f"[NMEA] {line}")

            try:
                msg = pynmea2.parse(line, check=True)
            except Exception:
                continue

            now = time.time()
            gnss_status.last_gps_time = now

            if isinstance(msg, pynmea2.types.talker.GGA):
                gnss_status.lat = msg.latitude if msg.latitude != "" else None
                gnss_status.lon = msg.longitude if msg.longitude != "" else None

                try:
                    q = int(msg.gps_qual)
                except (ValueError, TypeError):
                    q = 0
                gnss_status.fix_quality = q
                gnss_status.fix_desc = fix_quality_to_desc(q)

                try:
                    gnss_status.num_sats = int(msg.num_sats) if msg.num_sats else 0
                except (ValueError, TypeError):
                    gnss_status.num_sats = 0

                try:
                    gnss_status.hdop = float(msg.horizontal_dil) if msg.horizontal_dil else None
                except (ValueError, TypeError):
                    gnss_status.hdop = None

        except Exception as e:
            # Catch-all to avoid killing the thread on unexpected errors
            print(f"[NMEA] Unexpected error: {e}")
            time.sleep(1.0)


def status_printer(gnss_status: GNSSStatus, rtcm_status: RTCMStatus, stop_event: threading.Event):
    """Print GPS fix flag, RTCM status, and basic health."""
    while not stop_event.is_set():
        time.sleep(STATUS_PRINT_INTERVAL)
        now = time.time()

        # RTCM
        if rtcm_status.last_rx_time > 0:
            rtcm_age = now - rtcm_status.last_rx_time
            rtcm_active = rtcm_age < RTCM_STALE_SECONDS
        else:
            rtcm_age = float("inf")
            rtcm_active = False

        # GNSS
        lat = gnss_status.lat
        lon = gnss_status.lon
        lat_str = f"{lat:.8f}" if lat is not None else "N/A"
        lon_str = f"{lon:.8f}" if lon is not None else "N/A"
        hdop_str = f"{gnss_status.hdop:.2f}" if gnss_status.hdop is not None else "N/A"

        print(
            f"[STATUS] FIX: {gnss_status.fix_desc} "
            f"(quality={gnss_status.fix_quality}, sats={gnss_status.num_sats}, HDOP={hdop_str}) | "
            f"Lat={lat_str}, Lon={lon_str} | "
            f"RTCM: {'ACTIVE' if rtcm_active else 'STALE'} "
            f"(bytes={rtcm_status.total_bytes}, age={rtcm_age:.1f}s)"
        )

# -------------- MAIN --------------

def main():
    ser_mgr = SerialManager(SERIAL_PORT, SERIAL_BAUD, timeout=1)

    gnss_status = GNSSStatus()
    rtcm_status = RTCMStatus()
    stop_event = threading.Event()

    threads = [
        threading.Thread(target=rtcm_forwarder, args=(ser_mgr, rtcm_status, stop_event), daemon=True),
        threading.Thread(target=nmea_reader, args=(ser_mgr, gnss_status, stop_event), daemon=True),
        threading.Thread(target=status_printer, args=(gnss_status, rtcm_status, stop_event), daemon=True),
    ]
    for t in threads:
        t.start()

    print("Running. Ctrl+C to stop.")
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("Stopping...")
        stop_event.set()
        time.sleep(1.0)
        ser_mgr.close()

if __name__ == "__main__":
    main()