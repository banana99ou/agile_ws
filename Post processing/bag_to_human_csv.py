#!/usr/bin/env python3
"""
Convert a ROS 2 bag directory into "human readable" CSV outputs.

This script reads the bag directly and writes:
- per-topic CSVs with decoded fields (easier than raw JSON blobs)
- a normalized GNSS fix-flag timeline (F/R/D/3D/2D/N) where possible
- a small validity/summary report (topic counts + missing required topics)

Bag reader backend:
- If ROS2 Python packages are available, we can read via `rosbag2_py`.
- Otherwise, we fall back to the pure-Python `rosbags` package (works well on non-ROS machines).

Project context:
- README.md defines fix flags as F (RTK Fix), R (RTK Float), D, 3D, 2D, N.
- For F9P Helical, we derive a fix flag from `/gps_rtk_f9p_helical/gps/rtk_status` (String)
  which includes NMEA-derived fix quality (0..8) and RTCM status.
- For Pixhawk "regular GPS", prefer `/pixhawk/gpsstatus/gps1/raw` (mavros_msgs/msg/GPSRAW)
  which includes MAVLink `fix_type` (richer than NavSatFix.status).
  If unavailable, fall back to `/pixhawk/global_position/raw/fix` (NavSatFix) (coarse).



Arguments:
  - --run PATH: Bag directory (must contain `metadata.yaml`) OR a directory containing many bag directories.
  - --recursive: If `--run` is a directory, scan recursively for bag directories.
  - --bag-prefix PREFIX: If set, only process bag directories whose folder name starts with PREFIX (e.g. `26_0105_`).
  - --out-root DIR: Output root directory (default: current working directory).
  - --desired-flag FLAG: Desired fix flag for debug metrics (default: `F`).
  - --sustain-s SECONDS: Sustain time for "refix" metric (default: `1.0` seconds).
  - --debug / --verbose: Write debug-only CSVs (timelines, counts, raw cmd, etc.).

Outputs:
  - Output directory: `<out-root>/Bag_decoded/<bag_dir_name>/`
  - Always written:
    - `validity_summary.csv` (missing required topics, message totals, satellite stats, notes)
  - Written when the corresponding topic exists / can be decoded (files are created only if at least one row is written):
    - `gnss_f9p_helical_fix.csv` (decoded `/gps_rtk_f9p_helical/gps/fix`)
    - `gnss_pixhawk_navsatfix.csv` (decoded `/pixhawk/global_position/raw/fix`)
    - `pixhawk_gpsraw_gps1.csv` (decoded `/pixhawk/gpsstatus/gps1/raw` when available)
    - `motion_cmd_vel.csv` (decoded `/cmd_vel`)
    - `wheel_odom.csv` (decoded `/wheel/odom`)
    - `imu.csv` (decoded `/imu`)
    - `estop.csv` (decoded `/estop`)
  - Debug-only outputs (enabled via `--debug` / `--verbose`, and created only if at least one row is written):
    - `gnss_f9p_helical_rtk_status.csv` (decoded `/gps_rtk_f9p_helical/gps/rtk_status`)
    - `pixhawk_satellites.csv` (decoded `/pixhawk/global_position/raw/satellites`)
    - `motion_cmd_vel_raw.csv` (decoded `/cmd_vel_raw`)
    - `gnss_timeline.csv` (merged timeline across receivers)
    - `gnss_f9p_helical_nmea_time.csv` (NMEA UTC time/date extraction)
    - `gnss_metrics.csv` (refix metrics; depends on `--desired-flag` and `--sustain-s`)
    - `topic_counts.csv` (message counts per topic/type)
    - `raw_topics/*.csv` (raw JSON dump for every topic currently recorded by `Data_Logger.py`)

Examples:
  Convert one bag:
    python3 bag_to_human_csv.py --run /path/to/bag_dir

  Convert one bag and put outputs somewhere specific:
    python3 bag_to_human_csv.py --run /path/to/bag_dir --out-root /tmp/human

  Convert one bag including debug-only CSVs (topic counts, timelines, raw cmd, etc.):
    python3 bag_to_human_csv.py --run /path/to/bag_dir --debug

  Convert all bags under Experiment Data:
    python3 bag_to_human_csv.py --run /home/agilex/agilex_ws/Experiment\\ Data --recursive
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import math
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import yaml

# ------------------------- rosbag backends -------------------------

HAVE_ROS2_PY = False
try:
    import rosbag2_py  # type: ignore
    from rclpy.serialization import deserialize_message  # type: ignore
    from rosidl_runtime_py.utilities import get_message  # type: ignore
    from rosidl_runtime_py import message_to_ordereddict  # type: ignore

    HAVE_ROS2_PY = True
except Exception:
    HAVE_ROS2_PY = False

HAVE_ROSBAGS = False
try:
    from rosbags.rosbag2 import Reader as RosbagsReader  # type: ignore
    from rosbags.typesys import Stores, get_types_from_msg, get_typestore  # type: ignore

    HAVE_ROSBAGS = True
except Exception:
    HAVE_ROSBAGS = False


def _backend_help() -> str:
    return (
        "Unable to read ROS2 bags: neither ROS2 Python packages (`rosbag2_py`) nor the pure-Python\n"
        "`rosbags` package are available.\n\n"
        "Fix options:\n"
        "- Run inside a ROS2 environment (robot/ROS machine):\n"
        "    source /opt/ros/<distro>/setup.bash\n"
        "    source <your_ws>/install/setup.bash\n"
        "- Or install rosbags into your Python env (non-ROS machine):\n"
        "    pip install rosbags\n"
    )


def message_to_dict(msg: Any) -> Any:
    """Recursively convert a rosbags message object to dict/primitives."""
    if hasattr(msg, "__msgtype__"):
        out: Dict[str, Any] = {}
        for field in dir(msg):
            if not field.startswith("_"):
                out[field] = message_to_dict(getattr(msg, field))
        return out
    if isinstance(msg, (list, tuple)):
        return [message_to_dict(x) for x in msg]
    if isinstance(msg, (int, float, str, bool, bytes)) or msg is None:
        return msg
    if hasattr(msg, "tolist"):  # numpy
        return msg.tolist()
    return msg


# rosbags typestore (includes a minimal custom type for MAVROS GPSRAW)
TYPESTORE = None
if HAVE_ROSBAGS:
    GPSRAW_MSG = """
std_msgs/Header header
uint8 fix_type
int32 lat
int32 lon
int32 alt
uint16 eph
uint16 epv
uint16 vel
uint16 cog
uint8 satellites_visible
uint8 dgps_numch
uint32 dgps_age
"""
    TYPEMAP = get_types_from_msg(GPSRAW_MSG, "mavros_msgs/msg/GPSRAW")
    TYPESTORE = get_typestore(Stores.ROS2_HUMBLE)
    TYPESTORE.register(TYPEMAP)


# ------------------------- filename + time helpers -------------------------


def _sanitize_for_filename(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return "unknown"
    value = value.lstrip(".")
    if not value:
        return "unknown"
    out_chars: List[str] = []
    for ch in value:
        if ch.isalnum() or ch in ("-", "_", "."):
            out_chars.append(ch)
        else:
            out_chars.append("_")
    out = "".join(out_chars)
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("_") or "unknown"


def _ts_to_iso_utc(ts_sec: float) -> str:
    try:
        return _dt.datetime.utcfromtimestamp(ts_sec).isoformat() + "Z"
    except Exception:
        # bag timestamps may be sim time; best-effort only
        return ""


def _safe_int(x: Any) -> Optional[int]:
    try:
        if x is None:
            return None
        return int(x)
    except Exception:
        return None


def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


# ------------------------- rosbag open helpers -------------------------


def _detect_storage_id(bag_path: str) -> str:
    """Detect storage backend from metadata.yaml; fallback to sqlite3."""
    meta_path = os.path.join(bag_path, "metadata.yaml")
    if not os.path.exists(meta_path):
        return "sqlite3"
    try:
        with open(meta_path, "r") as f:
            meta = yaml.safe_load(f) or {}
    except Exception:
        return "sqlite3"

    storage_id = meta.get("storage_identifier") or meta.get("storage_id") or meta.get("storage")
    if not storage_id:
        info = meta.get("rosbag2_bagfile_information", {})
        storage_id = info.get("storage_identifier") or info.get("storage_id") or info.get("storage")
    return storage_id or "sqlite3"


def open_bag_reader(bag_path: str) -> Tuple[str, Any, Dict[str, str]]:
    if not os.path.isdir(bag_path):
        raise FileNotFoundError(f"Bag path is not a directory: {bag_path}")

    # Prefer ROS2 native reader when available; otherwise use rosbags.
    if HAVE_ROS2_PY:
        storage_id = _detect_storage_id(bag_path)
        storage_options = rosbag2_py.StorageOptions(uri=bag_path, storage_id=storage_id)
        converter_options = rosbag2_py.ConverterOptions("", "")

        reader = rosbag2_py.SequentialReader()
        try:
            reader.open(storage_options, converter_options)
        except RuntimeError as e:
            raise RuntimeError(
                f"Failed to open bag at '{bag_path}' with storage_id '{storage_id}'.\n"
                f"Original error: {e}\n"
                f"- Ensure this is a bag directory containing metadata.yaml\n"
            ) from e

        topic_type_map: Dict[str, str] = {}
        for t in reader.get_all_topics_and_types():
            topic_type_map[t.name] = t.type
        return "rosbag2_py", reader, topic_type_map

    if HAVE_ROSBAGS:
        if TYPESTORE is None:
            raise RuntimeError("rosbags typestore was not initialized (unexpected).")
        r = RosbagsReader(Path(bag_path))
        r.open()
        topic_type_map = {c.topic: c.msgtype for c in r.connections}
        return "rosbags", r, topic_type_map

    raise RuntimeError(_backend_help())


# ------------------------- parsing + normalization -------------------------


_RTK_STATUS_FIX_DESC_RE = re.compile(r"^\s*FIX:\s*(?P<fix_desc>.*?)\s*\(", re.IGNORECASE)


def normalize_fix_flag_from_f9p_status(fix_desc: str, quality: Optional[int]) -> str:
    """
    Map Helical F9P status into project flags F/R/D/3D/2D/N.
    The producer uses NMEA GGA fix_quality mapped to:
      0 NO FIX, 1 GPS, 2 DGPS, 4 RTK FIXED, 5 RTK FLOAT, ...
    """
    desc = (fix_desc or "").upper()
    if "NO FIX" in desc or quality == 0:
        return "N"
    if "RTK FIXED" in desc or quality == 4:
        return "F"
    if "RTK FLOAT" in desc or quality == 5:
        return "R"
    if "DGPS" in desc or quality == 2:
        return "D"
    if "GPS" in desc or quality == 1:
        # F9P status string doesn't include 2D vs 3D; treat GPS as 3D best-effort
        return "3D"
    return "U"


def parse_helical_rtk_status(s: str) -> Optional[Dict[str, Any]]:
    """
    Parse `/gps_rtk_f9p_helical/gps/rtk_status` strings.

    The producer format has changed over time. Examples seen in the wild:
      - `FIX: RTK FIXED (quality=4, sats=12, HDOP=0.59) | Lat=.., Lon=.. | RTCM: ACTIVE (bytes=..., age=0.6s)`
      - `FIX: RTK FIXED (quality=4, sats=12, HDOP=0.59, rate=6.0Hz) | Lat=.., Lon=.. | RTCM: ACTIVE (bytes=..., fwd_age=0.6s, net_age=0.6s)`

    We therefore parse using tolerant regex searches instead of a single strict full-match.
    """
    txt = (s or "").strip()
    if not txt:
        return None

    m_desc = _RTK_STATUS_FIX_DESC_RE.search(txt)
    if not m_desc:
        return None
    fix_desc = (m_desc.group("fix_desc") or "").strip()

    quality = _safe_int(_first_group(txt, r"quality\s*=\s*(\d+)"))
    sats = _safe_int(_first_group(txt, r"sats\s*=\s*(\d+)"))

    hdop_raw = (_first_group(txt, r"HDOP\s*=\s*([0-9.]+|N/A)") or "").strip()
    hdop = None if not hdop_raw or hdop_raw.upper() == "N/A" else _safe_float(hdop_raw)

    lat_raw = (_first_group(txt, r"Lat\s*=\s*([^,|]+)") or "").strip()
    lon_raw = (_first_group(txt, r"Lon\s*=\s*([^|]+)") or "").strip()
    lat = None if not lat_raw or lat_raw.upper() == "N/A" else _safe_float(lat_raw)
    lon = None if not lon_raw or lon_raw.upper() == "N/A" else _safe_float(lon_raw)

    rtcm_state = (_first_group(txt, r"RTCM\s*:\s*(ACTIVE|STALE)", flags=re.IGNORECASE) or "").strip().upper()
    rtcm_active = 1 if rtcm_state == "ACTIVE" else 0

    rtcm_bytes = _safe_int(_first_group(txt, r"bytes\s*=\s*(\d+)")) or 0

    # Older format: age=0.6s. Newer format: fwd_age=0.6s, net_age=0.6s.
    age = _safe_float(_first_group(txt, r"\bage\s*=\s*([\d.]+)s", flags=re.IGNORECASE))
    fwd_age = _safe_float(_first_group(txt, r"\bfwd_age\s*=\s*([\d.]+)s", flags=re.IGNORECASE))
    net_age = _safe_float(_first_group(txt, r"\bnet_age\s*=\s*([\d.]+)s", flags=re.IGNORECASE))

    # Preserve a single `rtcm_age_s` column for backward compatibility:
    # prefer `age`, else `net_age`, else `fwd_age`.
    rtcm_age_s = age if age is not None else (net_age if net_age is not None else fwd_age)

    fix_flag = normalize_fix_flag_from_f9p_status(fix_desc=fix_desc, quality=quality)

    return {
        "fix_flag": fix_flag,
        "fix_desc": fix_desc,
        "quality": "" if quality is None else quality,
        "sats": "" if sats is None else sats,
        "hdop": "" if hdop is None else hdop,
        "lat": "" if lat is None else lat,
        "lon": "" if lon is None else lon,
        "rtcm_active": rtcm_active,
        "rtcm_bytes": rtcm_bytes,
        "rtcm_age_s": "" if rtcm_age_s is None else rtcm_age_s,
    }


def _first_group(s: str, pattern: str, flags: int = 0) -> Optional[str]:
    m = re.search(pattern, s, flags)
    if not m:
        return None
    try:
        return m.group(1)
    except Exception:
        return None


def normalize_fix_flag_from_navsat_status(status: Optional[int]) -> str:
    """
    NavSatStatus.status is coarse. Best-effort mapping:
    - NO_FIX (<0) -> N
    - FIX (0) -> 3D
    - SBAS_FIX (1) / GBAS_FIX (2) -> D
    """
    if status is None:
        return "U"
    if status < 0:
        return "N"
    if status == 0:
        return "3D"
    if status in (1, 2):
        return "D"
    return "U"


def normalize_fix_flag_from_mavros_gpsraw_fix_type(fix_type: Optional[int]) -> str:
    """
    MAVLink GPS_FIX_TYPE (exposed via mavros_msgs/msg/GPSRAW.fix_type).
    Common values:
      0/1: no fix, 2: 2D, 3: 3D, 4: DGPS, 5: RTK float, 6/7: RTK fixed/static, 8: PPP
    """
    if fix_type is None:
        return "U"
    if fix_type in (0, 1):
        return "N"
    if fix_type == 2:
        return "2D"
    if fix_type == 3:
        return "3D"
    if fix_type == 4:
        return "D"
    if fix_type == 5:
        return "R"
    if fix_type in (6, 7):
        return "F"
    if fix_type == 8:
        return "3D"
    return "U"


def _deg1e7_to_deg(v: Any) -> Optional[float]:
    x = _safe_float(v)
    return None if x is None else (x / 1e7)


def _mm_to_m(v: Any) -> Optional[float]:
    x = _safe_float(v)
    return None if x is None else (x / 1000.0)


def _cmps_to_mps(v: Any) -> Optional[float]:
    x = _safe_float(v)
    return None if x is None else (x / 100.0)


def _cdeg_to_deg(v: Any) -> Optional[float]:
    x = _safe_float(v)
    return None if x is None else (x / 100.0)


# ------------------------- IMU helpers -------------------------


def _quat_to_yaw_rad(qx: float, qy: float, qz: float, qw: float) -> float:
    """
    Quaternion -> yaw (Z axis, ENU).
    yaw = atan2(2*(w*z + x*y), 1 - 2*(y^2 + z^2))
    """
    siny_cosp = 2.0 * (qw * qz + qx * qy)
    cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)
    return math.atan2(siny_cosp, cosy_cosp)


# ------------------------- NMEA time helpers -------------------------


def _parse_nmea_utc_hhmmss(raw: str) -> Optional[str]:
    """
    Extract UTC time-of-day from common NMEA sentences (GGA/RMC).
    Returns string like "061948.00" (as present in NMEA).
    """
    if not raw or not raw.startswith("$"):
        return None
    parts = raw.split(",")
    if not parts:
        return None
    head = parts[0].upper()
    # GGA: field[1]=UTC time
    if head.endswith("GGA") and len(parts) > 1 and parts[1]:
        return parts[1]
    # RMC: field[1]=UTC time
    if head.endswith("RMC") and len(parts) > 1 and parts[1]:
        return parts[1]
    return None


def _parse_nmea_date_ddmmyy(raw: str) -> Optional[str]:
    """Extract date from RMC (field[9]=ddmmyy)."""
    if not raw or not raw.startswith("$"):
        return None
    parts = raw.split(",")
    if not parts:
        return None
    head = parts[0].upper()
    if head.endswith("RMC") and len(parts) > 9 and parts[9]:
        return parts[9]
    return None


def _nmea_date_time_to_iso_utc(ddmmyy: str, hhmmss: str) -> Optional[str]:
    """
    Convert NMEA ddmmyy + hhmmss.sss into ISO UTC string.
    If parsing fails, return None.
    """
    try:
        if not ddmmyy or not hhmmss:
            return None
        dd = int(ddmmyy[0:2])
        mm = int(ddmmyy[2:4])
        yy = int(ddmmyy[4:6])
        year = 2000 + yy if yy < 80 else 1900 + yy
        # hhmmss may include decimals
        hh = int(hhmmss[0:2])
        mi = int(hhmmss[2:4])
        ss = float(hhmmss[4:])
        sec = int(ss)
        usec = int(round((ss - sec) * 1e6))
        dt = _dt.datetime(year, mm, dd, hh, mi, sec, usec, tzinfo=_dt.timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    except Exception:
        return None


# ------------------------- writers + metrics -------------------------


class LazyCsv:
    """
    called lazycsv because it is a lazy writer, it will not write to the file until the close() method is called.
    """
    def __init__(self, path: str, fieldnames: List[str]):
        self.path = path
        self.fieldnames = fieldnames
        self._fh = None
        self._writer = None

    def write(self, row: Dict[str, Any]) -> None:
        if self._writer is None:
            os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
            self._fh = open(self.path, "w", newline="")
            self._writer = csv.DictWriter(self._fh, fieldnames=self.fieldnames, extrasaction="ignore")
            self._writer.writeheader()
        self._writer.writerow(row)

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None
            self._writer = None


@dataclass
class RefixTracker:
    receiver: str
    desired_flag: str = "F"
    sustain_s: float = 1.0

    first_desired_ts: Optional[float] = None
    total_desired_s: float = 0.0
    num_segments: int = 0
    num_refix_events: int = 0

    _in_desired: bool = False
    _candidate_start: Optional[float] = None
    _segment_start: Optional[float] = None
    _last_ts: Optional[float] = None

    def update(self, ts: float, flag: str) -> None:
        self._last_ts = ts
        if flag == self.desired_flag:
            if self.first_desired_ts is None:
                self.first_desired_ts = ts
            if not self._in_desired:
                if self._candidate_start is None:
                    self._candidate_start = ts
                if (ts - self._candidate_start) >= self.sustain_s:
                    self._in_desired = True
                    self._segment_start = self._candidate_start
                    self.num_segments += 1
                    self.num_refix_events += 1
        else:
            self._candidate_start = None
            if self._in_desired and self._segment_start is not None:
                self.total_desired_s += max(0.0, ts - self._segment_start)
            self._in_desired = False
            self._segment_start = None

    def finalize(self) -> None:
        if self._in_desired and self._segment_start is not None and self._last_ts is not None:
            self.total_desired_s += max(0.0, self._last_ts - self._segment_start)
        self._in_desired = False
        self._candidate_start = None
        self._segment_start = None


# ------------------------- conversion logic -------------------------


REQUIRED_TOPICS = [
    "/gps_rtk_f9p_helical/gps/rtk_status",
    "/gps_rtk_f9p_helical/gps/fix",
    "/pixhawk/global_position/raw/fix",
    "/pixhawk/global_position/raw/satellites",
    "/cmd_vel",
    "/cmd_vel_raw",
    "/wheel/odom",
    "/imu",
    "/estop",
]

# Prefer this if present (future bags)
PREFERRED_PIXHAWK_FIX_TOPIC = "/pixhawk/gpsstatus/gps1/raw"

# IMPORTANT: Manual snapshot of what `Data_Logger.py` records *today*.
# This intentionally avoids any runtime import/introspection of Data_Logger.
DATA_LOGGER_TOPICS = [
    "/gps_rtk_f9p_helical/gps/fix",
    "/gps_rtk_f9p_helical/gps/nmea",
    "/gps_rtk_f9p_helical/gps/rtk_status",
    "/pixhawk/global_position/raw/satellites",
    "/pixhawk/global_position/raw/fix",
    "/pixhawk/gpsstatus/gps1/raw",
    "/cmd_vel",
    "/cmd_vel_raw",
    "/wheel/odom",
    "/imu",
    "/estop",
]


def _bag_is_dir(bag_path: str) -> bool:
    return os.path.isdir(bag_path) and os.path.exists(os.path.join(bag_path, "metadata.yaml"))


def find_bag_dirs(root: str) -> List[str]:
    out: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        if "metadata.yaml" in filenames:
            out.append(dirpath)
            # don't recurse into bag subdirs
            dirnames[:] = []
    return sorted(out)


def convert_bag(bag_path: str, out_root: Optional[str], desired_flag: str, sustain_s: float, debug: bool) -> str:
    """
    Convert a single ROS 2 bag directory into human-readable CSV files.

    Args:
        bag_path (str): Path to the bag directory (should contain metadata.yaml).
        out_root (Optional[str]): Optional root directory for output. If None, use current working directory.
        desired_flag (str): Desired fix flag used for metrics calculations (e.g., 'F').
        sustain_s (float): Sustain time (in seconds) for metrics regarding "refix" events.
        debug (bool): If True, write extra debug-only CSVs (timelines, counts, raw cmd, etc.).

    Returns:
        str: Path to the output directory containing the generated human-readable CSVs.

    Steps performed:
        - Creates/ensures the output directory exists.
        - Opens the bag reader and determines message types present.
        - Initializes CSV writers for different required topics.
        - Reads messages, decodes them topic-by-topic, and writes out to appropriately formatted CSVs.
        - Calculates and writes extra summary/metrics information.
        - Optionally outputs debug CSVs if requested.
        - Closes all writers/resources and returns the output directory path.
    """
    bag_base = os.path.basename(os.path.normpath(bag_path)) or "bag" # get the base name of the bag directory
    out_root_final = out_root or os.getcwd() # get the output root directory
    out_dir = os.path.join(out_root_final, "Bag_csv", _sanitize_for_filename(bag_base)) # create the output directory path
    os.makedirs(out_dir, exist_ok=True) # create the output directory if it doesn't exist

    backend, reader, topic_type_map = open_bag_reader(bag_path) # open the bag reader and get the backend, reader, and topic type map

    # type cache (rosbag2_py only)
    msg_type_cache: Dict[str, type] = {}

    # counts
    msg_counts: Dict[str, int] = {t: 0 for t in topic_type_map.keys()}
    total_msgs = 0

    # writers
    #
    # Some CSVs are debug-only to avoid cluttering default outputs.
    # Enable with --debug / --verbose.
    w_f9p_status: Optional[LazyCsv] = None
    w_f9p_fix = LazyCsv(
        os.path.join(out_dir, "gnss_f9p_helical_fix.csv"),
        [
            "ts_sec",
            "ts_iso_utc",
            "bag_ts_ns",
            "hdr_stamp_sec",
            "hdr_stamp_nanosec",
            "lat",
            "lon",
            "alt",
            "navsat_status",
            "navsat_service",
            "fix_flag",
            "fix_flag_source",
        ],
    )
    w_px4_fix = LazyCsv(
        os.path.join(out_dir, "gnss_pixhawk_navsatfix.csv"),
        [
            "ts_sec",
            "ts_iso_utc",
            "bag_ts_ns",
            "hdr_stamp_sec",
            "hdr_stamp_nanosec",
            "lat",
            "lon",
            "alt",
            "navsat_status",
            "navsat_service",
            "fix_flag",
        ],
    )
    w_px4_sats: Optional[LazyCsv] = None
    w_px4_gpsraw = LazyCsv(
        os.path.join(out_dir, "pixhawk_gpsraw_gps1.csv"),
        [
            "ts_sec",
            "ts_iso_utc",
            "bag_ts_ns",
            "hdr_stamp_sec",
            "hdr_stamp_nanosec",
            "fix_type",
            "fix_flag",
            "lat_deg",
            "lon_deg",
            "alt_m",
            "vel_mps",
            "cog_deg",
            "satellites_visible",
            "eph",
            "epv",
        ],
    )
    w_cmd = LazyCsv(
        os.path.join(out_dir, "motion_cmd_vel.csv"),
        ["ts_sec", "ts_iso_utc", "lin_x", "lin_y", "lin_z", "ang_x", "ang_y", "ang_z"],
    )
    w_wheel_odom = LazyCsv(
        os.path.join(out_dir, "wheel_odom.csv"),
        [
            "ts_sec",
            "ts_iso_utc",
            "bag_ts_ns",
            "hdr_stamp_sec",
            "hdr_stamp_nanosec",
            "frame_id",
            "child_frame_id",
            "pos_x",
            "pos_y",
            "pos_z",
            "yaw_deg",
            "lin_vel_x",
            "lin_vel_y",
            "lin_vel_z",
            "ang_vel_x",
            "ang_vel_y",
            "ang_vel_z",
        ],
    )
    w_cmd_raw: Optional[LazyCsv] = None
    w_imu = LazyCsv(
        os.path.join(out_dir, "imu.csv"),
        [
            "ts_sec",
            "ts_iso_utc",
            "bag_ts_ns",
            "hdr_stamp_sec",
            "hdr_stamp_nanosec",
            "yaw_deg",
            "accel_x",
            "accel_y",
            "accel_z",
            "accel_norm",
        ],
    )
    w_estop = LazyCsv(os.path.join(out_dir, "estop.csv"), ["ts_sec", "ts_iso_utc", "estop"])
    w_timeline: Optional[LazyCsv] = None
    w_f9p_nmea_time: Optional[LazyCsv] = None
    w_metrics: Optional[LazyCsv] = None
    w_counts: Optional[LazyCsv] = None
    w_validity = LazyCsv(
        os.path.join(out_dir, "validity_summary.csv"),
        [
            "bag_path",
            "bag_name",
            "missing_required_topics",
            "total_messages",
            "pixhawk_sat_min",
            "pixhawk_sat_max",
            "pixhawk_sat_samples",
            "pixhawk_gpsraw_sat_min",
            "pixhawk_gpsraw_sat_max",
            "pixhawk_gpsraw_sat_samples",
            "notes",
        ],
    )

    trackers: Optional[Dict[str, RefixTracker]] = None
    raw_topic_writers: Optional[Dict[str, LazyCsv]] = None
    raw_writer_for = None

    if debug:
        w_f9p_status = LazyCsv(
            os.path.join(out_dir, "gnss_f9p_helical_rtk_status.csv"),
            [
                "ts_sec",
                "ts_iso_utc",
                "bag_ts_ns",
                "hdr_stamp_sec",
                "hdr_stamp_nanosec",
                "fix_flag",
                "fix_desc",
                "quality",
                "sats",
                "hdop",
                "lat",
                "lon",
                "rtcm_active",
                "rtcm_bytes",
                "rtcm_age_s",
                "raw",
            ],
        )
        w_px4_sats = LazyCsv(
            os.path.join(out_dir, "pixhawk_satellites.csv"),
            ["ts_sec", "ts_iso_utc", "satellites"],
        )
        w_cmd_raw = LazyCsv(
            os.path.join(out_dir, "motion_cmd_vel_raw.csv"),
            ["ts_sec", "ts_iso_utc", "lin_x", "lin_y", "lin_z", "ang_x", "ang_y", "ang_z"],
        )
        w_timeline = LazyCsv(
            os.path.join(out_dir, "gnss_timeline.csv"),
            ["ts_sec", "ts_iso_utc", "receiver", "fix_flag", "lat", "lon", "alt", "detail"],
        )
        w_f9p_nmea_time = LazyCsv(
            os.path.join(out_dir, "gnss_f9p_helical_nmea_time.csv"),
            [
                "ts_sec",
                "ts_iso_utc",
                "bag_ts_ns",
                "utc_time_hhmmss",
                "utc_date_ddmmyy",
                "gps_iso_utc",
                "sentence_type",
            ],
        )
        w_metrics = LazyCsv(
            os.path.join(out_dir, "gnss_metrics.csv"),
            [
                "receiver",
                "desired_flag",
                "sustain_s",
                "first_desired_ts",
                "total_desired_s",
                "num_segments",
                "num_refix_events",
            ],
        )
        w_counts = LazyCsv(os.path.join(out_dir, "topic_counts.csv"), ["topic", "type", "messages"])
        trackers = {
            "f9p_helical": RefixTracker("f9p_helical", desired_flag=desired_flag, sustain_s=sustain_s),
            "pixhawk": RefixTracker("pixhawk", desired_flag=desired_flag, sustain_s=sustain_s),
        }
        raw_topic_writers = {}

        def _raw_writer_for(topic_name: str) -> LazyCsv:
            assert raw_topic_writers is not None
            if topic_name in raw_topic_writers:
                return raw_topic_writers[topic_name]
            fname = _sanitize_for_filename(topic_name.strip("/").replace("/", "__") or "root")
            w = LazyCsv(
                os.path.join(out_dir, "raw_topics", f"{fname}.csv"),
                [
                    "ts_sec",
                    "ts_iso_utc",
                    "bag_ts_ns",
                    "hdr_stamp_sec",
                    "hdr_stamp_nanosec",
                    "type",
                    "decode_ok",
                    "json",
                ],
            )
            raw_topic_writers[topic_name] = w
            return w

        raw_writer_for = _raw_writer_for

    # If GPSRAW exists, prefer it for pixhawk flag timeline.
    # NOTE: Some environments cannot deserialize this message type; detect and fall back.
    have_px4_gpsraw = PREFERRED_PIXHAWK_FIX_TOPIC in topic_type_map
    px4_gpsraw_broken = False
    px4_gpsraw_first_error: Optional[str] = None

    # Track last-known F9P fix flag from rtk_status so NavSatFix rows don't mislabel RTK as "D".
    last_f9p_fix_flag: Optional[str] = None
    last_f9p_fix_flag_ts: Optional[float] = None

    # NMEA time tracking (UTC date comes from RMC; time-of-day from GGA/RMC)
    last_nmea_date_ddmmyy: Optional[str] = None

    # Satellites sanity stats
    pixhawk_sat_min: Optional[int] = None
    pixhawk_sat_max: Optional[int] = None
    pixhawk_sat_samples = 0
    pixhawk_gpsraw_sat_min: Optional[int] = None
    pixhawk_gpsraw_sat_max: Optional[int] = None
    pixhawk_gpsraw_sat_samples = 0

    def iter_decoded_messages() -> Iterable[Tuple[str, int, Optional[Dict[str, Any]]]]:
        """
        Yield (topic, t_ns, msg_dict|None) for every message in the bag.
        msg_dict is None when deserialization fails; counters should still advance.
        """
        nonlocal px4_gpsraw_broken, px4_gpsraw_first_error

        if backend == "rosbag2_py":
            while reader.has_next():
                topic, data, t_ns = reader.read_next()

                type_str = topic_type_map.get(topic)
                if not type_str:
                    yield topic, int(t_ns), None
                    continue
                if type_str not in msg_type_cache:
                    msg_type_cache[type_str] = get_message(type_str)
                msg_type = msg_type_cache[type_str]

                try:
                    msg_obj = deserialize_message(data, msg_type)
                    msg = message_to_ordereddict(msg_obj)
                    yield topic, int(t_ns), msg
                except Exception as e:
                    if topic == PREFERRED_PIXHAWK_FIX_TOPIC:
                        px4_gpsraw_broken = True
                        if px4_gpsraw_first_error is None:
                            px4_gpsraw_first_error = f"{type(e).__name__}: {e}"
                    yield topic, int(t_ns), None
            return

        if backend == "rosbags":
            for connection, t_ns, data in reader.messages():
                topic = connection.topic
                try:
                    assert TYPESTORE is not None
                    msg_obj = TYPESTORE.deserialize_cdr(data, connection.msgtype)
                    msg = message_to_dict(msg_obj)
                    yield topic, int(t_ns), msg
                except Exception as e:
                    if topic == PREFERRED_PIXHAWK_FIX_TOPIC:
                        px4_gpsraw_broken = True
                        if px4_gpsraw_first_error is None:
                            px4_gpsraw_first_error = f"{type(e).__name__}: {e}"
                    yield topic, int(t_ns), None
            return

        raise RuntimeError(f"Unknown bag backend: {backend}")

    for topic, t_ns, msg in iter_decoded_messages():
        total_msgs += 1
        if topic in msg_counts:
            msg_counts[topic] += 1
        ts_sec = t_ns / 1e9
        ts_iso = _ts_to_iso_utc(ts_sec)
        bag_ts_ns = int(t_ns)

        # Header stamp if present
        hdr = msg.get("header") if isinstance(msg, dict) else None
        hdr_stamp = hdr.get("stamp") if isinstance(hdr, dict) else None
        hdr_stamp_sec = _safe_int(hdr_stamp.get("sec")) if isinstance(hdr_stamp, dict) else None
        hdr_stamp_nanosec = _safe_int(hdr_stamp.get("nanosec")) if isinstance(hdr_stamp, dict) else None

        # --- Debug raw dump for every topic Data_Logger records ---
        if debug and (raw_writer_for is not None) and (topic in DATA_LOGGER_TOPICS):
            type_str = topic_type_map.get(topic, "")
            try:
                json_blob = "" if msg is None else json.dumps(msg, ensure_ascii=False, default=str)
            except Exception:
                json_blob = ""
            raw_writer_for(topic).write(
                {
                    "ts_sec": f"{ts_sec:.9f}",
                    "ts_iso_utc": ts_iso,
                    "bag_ts_ns": bag_ts_ns,
                    "hdr_stamp_sec": "" if hdr_stamp_sec is None else hdr_stamp_sec,
                    "hdr_stamp_nanosec": "" if hdr_stamp_nanosec is None else hdr_stamp_nanosec,
                    "type": type_str,
                    "decode_ok": 0 if msg is None else 1,
                    "json": json_blob,
                }
            )

        if msg is None:
            continue

        # --- F9P Helical status (best fix flag) ---
        if topic == "/gps_rtk_f9p_helical/gps/rtk_status":
            s = str((msg or {}).get("data", ""))
            parsed = parse_helical_rtk_status(s)
            if parsed:
                last_f9p_fix_flag = parsed["fix_flag"]
                last_f9p_fix_flag_ts = ts_sec
                if w_f9p_status is not None:
                    w_f9p_status.write(
                        {
                            "ts_sec": f"{ts_sec:.9f}",
                            "ts_iso_utc": ts_iso,
                            "bag_ts_ns": bag_ts_ns,
                            "hdr_stamp_sec": "" if hdr_stamp_sec is None else hdr_stamp_sec,
                            "hdr_stamp_nanosec": "" if hdr_stamp_nanosec is None else hdr_stamp_nanosec,
                            **parsed,
                            "raw": s,
                        }
                    )
                if w_timeline is not None:
                    w_timeline.write(
                        {
                            "ts_sec": f"{ts_sec:.9f}",
                            "ts_iso_utc": ts_iso,
                            "receiver": "f9p_helical",
                            "fix_flag": parsed["fix_flag"],
                            "lat": parsed.get("lat", ""),
                            "lon": parsed.get("lon", ""),
                            "alt": "",
                            "detail": f"{parsed.get('fix_desc','')}; q={parsed.get('quality','')}; sats={parsed.get('sats','')}; hdop={parsed.get('hdop','')}; rtcm_active={parsed.get('rtcm_active','')}",
                        }
                    )
                if trackers is not None:
                    trackers["f9p_helical"].update(ts_sec, parsed["fix_flag"])
            continue

        # --- F9P Helical NavSatFix (coarse) ---
        if topic == "/gps_rtk_f9p_helical/gps/fix":
            lat = _safe_float(msg.get("latitude"))
            lon = _safe_float(msg.get("longitude"))
            alt = _safe_float(msg.get("altitude"))
            navsat_status = _safe_int(((msg.get("status") or {}).get("status")))
            navsat_service = _safe_int(((msg.get("status") or {}).get("service")))
            fix_flag_source = "navsat_status"
            fix_flag = normalize_fix_flag_from_navsat_status(navsat_status)
            # Prefer rtk_status-derived flag if we have it reasonably close in time.
            if last_f9p_fix_flag is not None and last_f9p_fix_flag_ts is not None:
                if abs(ts_sec - last_f9p_fix_flag_ts) <= 2.0:
                    fix_flag = last_f9p_fix_flag
                    fix_flag_source = "rtk_status"
            w_f9p_fix.write(
                {
                    "ts_sec": f"{ts_sec:.9f}",
                    "ts_iso_utc": ts_iso,
                    "bag_ts_ns": bag_ts_ns,
                    "hdr_stamp_sec": "" if hdr_stamp_sec is None else hdr_stamp_sec,
                    "hdr_stamp_nanosec": "" if hdr_stamp_nanosec is None else hdr_stamp_nanosec,
                    "lat": "" if lat is None else lat,
                    "lon": "" if lon is None else lon,
                    "alt": "" if alt is None else alt,
                    "navsat_status": "" if navsat_status is None else navsat_status,
                    "navsat_service": "" if navsat_service is None else navsat_service,
                    "fix_flag": fix_flag,
                    "fix_flag_source": fix_flag_source,
                }
            )
            continue

        # --- F9P Helical NMEA: extract GPS UTC time-of-day (and date when RMC is present) ---
        if topic == "/gps_rtk_f9p_helical/gps/nmea":
            raw = str((msg or {}).get("data", ""))
            date_ddmmyy = _parse_nmea_date_ddmmyy(raw)
            if date_ddmmyy:
                last_nmea_date_ddmmyy = date_ddmmyy
            utc_hhmmss = _parse_nmea_utc_hhmmss(raw)
            if utc_hhmmss and w_f9p_nmea_time is not None:
                gps_iso = _nmea_date_time_to_iso_utc(last_nmea_date_ddmmyy or "", utc_hhmmss)
                sent_type = raw.split(",")[0] if raw else ""
                w_f9p_nmea_time.write(
                    {
                        "ts_sec": f"{ts_sec:.9f}",
                        "ts_iso_utc": ts_iso,
                        "bag_ts_ns": bag_ts_ns,
                        "utc_time_hhmmss": utc_hhmmss,
                        "utc_date_ddmmyy": last_nmea_date_ddmmyy or "",
                        "gps_iso_utc": gps_iso or "",
                        "sentence_type": sent_type,
                    }
                )
            continue

        # --- Pixhawk GPSRAW (preferred) ---
        if topic == PREFERRED_PIXHAWK_FIX_TOPIC:
            fix_type = _safe_int(msg.get("fix_type"))
            fix_flag = normalize_fix_flag_from_mavros_gpsraw_fix_type(fix_type)
            lat = _deg1e7_to_deg(msg.get("lat"))
            lon = _deg1e7_to_deg(msg.get("lon"))
            alt_m = _mm_to_m(msg.get("alt"))
            vel_mps = _cmps_to_mps(msg.get("vel"))
            cog_deg = _cdeg_to_deg(msg.get("cog"))
            sats_visible = _safe_int(msg.get("satellites_visible"))
            eph = _safe_int(msg.get("eph"))
            epv = _safe_int(msg.get("epv"))
            if sats_visible is not None:
                pixhawk_gpsraw_sat_samples += 1
                pixhawk_gpsraw_sat_min = sats_visible if pixhawk_gpsraw_sat_min is None else min(pixhawk_gpsraw_sat_min, sats_visible)
                pixhawk_gpsraw_sat_max = sats_visible if pixhawk_gpsraw_sat_max is None else max(pixhawk_gpsraw_sat_max, sats_visible)

            w_px4_gpsraw.write(
                {
                    "ts_sec": f"{ts_sec:.9f}",
                    "ts_iso_utc": ts_iso,
                    "bag_ts_ns": bag_ts_ns,
                    "hdr_stamp_sec": "" if hdr_stamp_sec is None else hdr_stamp_sec,
                    "hdr_stamp_nanosec": "" if hdr_stamp_nanosec is None else hdr_stamp_nanosec,
                    "fix_type": "" if fix_type is None else fix_type,
                    "fix_flag": fix_flag,
                    "lat_deg": "" if lat is None else lat,
                    "lon_deg": "" if lon is None else lon,
                    "alt_m": "" if alt_m is None else alt_m,
                    "vel_mps": "" if vel_mps is None else vel_mps,
                    "cog_deg": "" if cog_deg is None else cog_deg,
                    "satellites_visible": "" if sats_visible is None else sats_visible,
                    "eph": "" if eph is None else eph,
                    "epv": "" if epv is None else epv,
                }
            )

            if w_timeline is not None:
                w_timeline.write(
                    {
                        "ts_sec": f"{ts_sec:.9f}",
                        "ts_iso_utc": ts_iso,
                        "receiver": "pixhawk",
                        "fix_flag": fix_flag,
                        "lat": "" if lat is None else lat,
                        "lon": "" if lon is None else lon,
                        "alt": "" if alt_m is None else alt_m,
                        "detail": f"GPSRAW.fix_type={fix_type}",
                    }
                )
            if trackers is not None:
                trackers["pixhawk"].update(ts_sec, fix_flag)
            continue

        # --- Pixhawk NavSatFix (fallback only, if GPSRAW missing) ---
        if (topic == "/pixhawk/global_position/raw/fix") and ((not have_px4_gpsraw) or px4_gpsraw_broken):
            lat = _safe_float(msg.get("latitude"))
            lon = _safe_float(msg.get("longitude"))
            alt = _safe_float(msg.get("altitude"))
            navsat_status = _safe_int(((msg.get("status") or {}).get("status")))
            navsat_service = _safe_int(((msg.get("status") or {}).get("service")))
            fix_flag = normalize_fix_flag_from_navsat_status(navsat_status)
            w_px4_fix.write(
                {
                    "ts_sec": f"{ts_sec:.9f}",
                    "ts_iso_utc": ts_iso,
                    "bag_ts_ns": bag_ts_ns,
                    "hdr_stamp_sec": "" if hdr_stamp_sec is None else hdr_stamp_sec,
                    "hdr_stamp_nanosec": "" if hdr_stamp_nanosec is None else hdr_stamp_nanosec,
                    "lat": "" if lat is None else lat,
                    "lon": "" if lon is None else lon,
                    "alt": "" if alt is None else alt,
                    "navsat_status": "" if navsat_status is None else navsat_status,
                    "navsat_service": "" if navsat_service is None else navsat_service,
                    "fix_flag": fix_flag,
                }
            )
            if w_timeline is not None:
                w_timeline.write(
                    {
                        "ts_sec": f"{ts_sec:.9f}",
                        "ts_iso_utc": ts_iso,
                        "receiver": "pixhawk",
                        "fix_flag": fix_flag,
                        "lat": "" if lat is None else lat,
                        "lon": "" if lon is None else lon,
                        "alt": "" if alt is None else alt,
                        "detail": f"NavSatFix.status={navsat_status}",
                    }
                )
            if trackers is not None:
                trackers["pixhawk"].update(ts_sec, fix_flag)
            continue

        # --- Pixhawk satellites ---
        if topic == "/pixhawk/global_position/raw/satellites":
            sats = _safe_int(msg.get("data"))
            if sats is not None:
                pixhawk_sat_samples += 1
                pixhawk_sat_min = sats if pixhawk_sat_min is None else min(pixhawk_sat_min, sats)
                pixhawk_sat_max = sats if pixhawk_sat_max is None else max(pixhawk_sat_max, sats)
            if w_px4_sats is not None:
                w_px4_sats.write(
                    {
                        "ts_sec": f"{ts_sec:.9f}",
                        "ts_iso_utc": ts_iso,
                        "satellites": "" if sats is None else sats,
                    }
                )
            continue

        # --- cmd_vel + cmd_vel_raw ---
        if topic in ("/cmd_vel", "/cmd_vel_raw"):
            lin = msg.get("linear") or {}
            ang = msg.get("angular") or {}
            out_row = {
                "ts_sec": f"{ts_sec:.9f}",
                "ts_iso_utc": ts_iso,
                "lin_x": _safe_float(lin.get("x")) or 0.0,
                "lin_y": _safe_float(lin.get("y")) or 0.0,
                "lin_z": _safe_float(lin.get("z")) or 0.0,
                "ang_x": _safe_float(ang.get("x")) or 0.0,
                "ang_y": _safe_float(ang.get("y")) or 0.0,
                "ang_z": _safe_float(ang.get("z")) or 0.0,
            }
            if topic == "/cmd_vel_raw":
                if w_cmd_raw is not None:
                    w_cmd_raw.write(out_row)
            else:
                w_cmd.write(out_row)
            continue

        # --- wheel odom (nav_msgs/Odometry) ---
        if topic == "/wheel/odom":
            frame_id = ""
            if isinstance(hdr, dict):
                frame_id = str(hdr.get("frame_id") or "")
            child_frame_id = str(msg.get("child_frame_id") or "")

            pose = (msg.get("pose") or {}).get("pose") if isinstance(msg.get("pose"), dict) else None
            pose = pose if isinstance(pose, dict) else {}
            pos = pose.get("position") if isinstance(pose.get("position"), dict) else {}
            ori = pose.get("orientation") if isinstance(pose.get("orientation"), dict) else {}

            px = _safe_float((pos or {}).get("x"))
            py = _safe_float((pos or {}).get("y"))
            pz = _safe_float((pos or {}).get("z"))

            qx = _safe_float((ori or {}).get("x")) or 0.0
            qy = _safe_float((ori or {}).get("y")) or 0.0
            qz = _safe_float((ori or {}).get("z")) or 0.0
            qw = _safe_float((ori or {}).get("w")) or 1.0
            yaw_deg = math.degrees(_quat_to_yaw_rad(qx, qy, qz, qw))
            yaw_deg = (yaw_deg + 360.0) % 360.0

            tw = (msg.get("twist") or {}).get("twist") if isinstance(msg.get("twist"), dict) else None
            tw = tw if isinstance(tw, dict) else {}
            lin = tw.get("linear") if isinstance(tw.get("linear"), dict) else {}
            ang = tw.get("angular") if isinstance(tw.get("angular"), dict) else {}

            w_wheel_odom.write(
                {
                    "ts_sec": f"{ts_sec:.9f}",
                    "ts_iso_utc": ts_iso,
                    "bag_ts_ns": bag_ts_ns,
                    "hdr_stamp_sec": "" if hdr_stamp_sec is None else hdr_stamp_sec,
                    "hdr_stamp_nanosec": "" if hdr_stamp_nanosec is None else hdr_stamp_nanosec,
                    "frame_id": frame_id,
                    "child_frame_id": child_frame_id,
                    "pos_x": "" if px is None else px,
                    "pos_y": "" if py is None else py,
                    "pos_z": "" if pz is None else pz,
                    "yaw_deg": f"{yaw_deg:.3f}",
                    "lin_vel_x": _safe_float((lin or {}).get("x")) or 0.0,
                    "lin_vel_y": _safe_float((lin or {}).get("y")) or 0.0,
                    "lin_vel_z": _safe_float((lin or {}).get("z")) or 0.0,
                    "ang_vel_x": _safe_float((ang or {}).get("x")) or 0.0,
                    "ang_vel_y": _safe_float((ang or {}).get("y")) or 0.0,
                    "ang_vel_z": _safe_float((ang or {}).get("z")) or 0.0,
                }
            )
            continue

        # --- IMU ---
        if topic in ("/imu", "/pixhawk/imu/data"):
            ori = msg.get("orientation") or {}
            la = msg.get("linear_acceleration") or {}
            qx = _safe_float(ori.get("x")) or 0.0
            qy = _safe_float(ori.get("y")) or 0.0
            qz = _safe_float(ori.get("z")) or 0.0
            qw = _safe_float(ori.get("w")) or 1.0
            yaw_deg = math.degrees(_quat_to_yaw_rad(qx, qy, qz, qw))
            yaw_deg = (yaw_deg + 360.0) % 360.0

            ax = _safe_float(la.get("x")) or 0.0
            ay = _safe_float(la.get("y")) or 0.0
            az = _safe_float(la.get("z")) or 0.0
            a_norm = math.sqrt(ax * ax + ay * ay + az * az)

            w_imu.write(
                {
                    "ts_sec": f"{ts_sec:.9f}",
                    "ts_iso_utc": ts_iso,
                    "bag_ts_ns": bag_ts_ns,
                    "hdr_stamp_sec": "" if hdr_stamp_sec is None else hdr_stamp_sec,
                    "hdr_stamp_nanosec": "" if hdr_stamp_nanosec is None else hdr_stamp_nanosec,
                    "yaw_deg": f"{yaw_deg:.3f}",
                    "accel_x": f"{ax:.6f}",
                    "accel_y": f"{ay:.6f}",
                    "accel_z": f"{az:.6f}",
                    "accel_norm": f"{a_norm:.6f}",
                }
            )
            continue

        # --- E-stop ---
        if topic == "/estop":
            estop = bool(msg.get("data"))
            w_estop.write({"ts_sec": f"{ts_sec:.9f}", "ts_iso_utc": ts_iso, "estop": 1 if estop else 0})
            continue

    # Write topic counts (debug-only)
    if w_counts is not None:
        for topic_name, type_str in sorted(topic_type_map.items()):
            w_counts.write({"topic": topic_name, "type": type_str, "messages": msg_counts.get(topic_name, 0)})

    # Validity summary
    required = list(REQUIRED_TOPICS)
    if have_px4_gpsraw and (PREFERRED_PIXHAWK_FIX_TOPIC not in required):
        # don't require it for backwards compat; but mention it.
        pass
    missing = [t for t in required if t not in topic_type_map]
    notes = ""
    if not have_px4_gpsraw:
        notes += "pixhawk_fix_source=NavSatFix(fallback_missing_gpsraw); "
    else:
        if px4_gpsraw_broken:
            notes += f"pixhawk_fix_source=NavSatFix(fallback_due_to_gpsraw_decode_error={px4_gpsraw_first_error}); "
        else:
            notes += "pixhawk_fix_source=GPSRAW(preferred); "

    w_validity.write(
        {
            "bag_path": bag_path,
            "bag_name": bag_base,
            "missing_required_topics": ";".join(missing),
            "total_messages": total_msgs,
            "pixhawk_sat_min": "" if pixhawk_sat_min is None else pixhawk_sat_min,
            "pixhawk_sat_max": "" if pixhawk_sat_max is None else pixhawk_sat_max,
            "pixhawk_sat_samples": pixhawk_sat_samples,
            "pixhawk_gpsraw_sat_min": "" if pixhawk_gpsraw_sat_min is None else pixhawk_gpsraw_sat_min,
            "pixhawk_gpsraw_sat_max": "" if pixhawk_gpsraw_sat_max is None else pixhawk_gpsraw_sat_max,
            "pixhawk_gpsraw_sat_samples": pixhawk_gpsraw_sat_samples,
            "notes": notes.strip(),
        }
    )

    # Metrics (debug-only)
    if w_metrics is not None and trackers is not None:
        for tr in trackers.values():
            tr.finalize()
            w_metrics.write(
                {
                    "receiver": tr.receiver,
                    "desired_flag": tr.desired_flag,
                    "sustain_s": tr.sustain_s,
                    "first_desired_ts": "" if tr.first_desired_ts is None else f"{tr.first_desired_ts:.9f}",
                    "total_desired_s": f"{tr.total_desired_s:.3f}",
                    "num_segments": tr.num_segments,
                    "num_refix_events": tr.num_refix_events,
                }
            )

    # Close writers
    for w in (
        w_f9p_fix,
        w_px4_fix,
        w_px4_gpsraw,
        w_cmd,
        w_wheel_odom,
        w_imu,
        w_estop,
        w_validity,
    ):
        if w is not None:
            w.close()

    for w in (w_f9p_status, w_px4_sats, w_cmd_raw, w_timeline, w_f9p_nmea_time, w_metrics, w_counts):
        if w is not None:
            w.close()

    if raw_topic_writers is not None:
        for w in raw_topic_writers.values():
            try:
                w.close()
            except Exception:
                pass

    # Close backend reader if needed
    try:
        if hasattr(reader, "close"):
            reader.close()
    except Exception:
        pass

    return out_dir


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Convert ros2 bag directories into human-readable CSV outputs.")
    p.add_argument("--run", required=True, help="Bag directory (contains metadata.yaml) OR a directory containing many bags.")
    p.add_argument("--recursive", action="store_true", help="If --run is a directory, scan recursively for bag dirs.")
    p.add_argument("--bag-prefix", default=None, help="If set, only process bag directories whose folder name starts with this prefix (e.g. '26_0105_').",)
    p.add_argument("--out-root", default=None, help="Output root directory (default: current working directory).")
    p.add_argument("--desired-flag", default="F", help="Desired fix flag for metrics (default: F).")
    p.add_argument("--sustain-s", type=float, default=1.0, help="Sustain time for 'refixed' metric (default: 1.0s).")
    p.add_argument("--debug", action="store_true", help="Write debug-only CSVs (timeline, counts, raw cmd, etc.).")
    p.add_argument("--verbose", action="store_true", help="Alias for --debug.")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    path = args.run
    debug = bool(getattr(args, "debug", False) or getattr(args, "verbose", False))
    bag_prefix = (getattr(args, "bag_prefix", None) or "").strip() or None

    if _bag_is_dir(path):
        out_dir = convert_bag(path, args.out_root, args.desired_flag, args.sustain_s, debug=debug)
        print(f"[OK] Wrote human CSVs to: {out_dir}")
        return 0

    if not os.path.isdir(path):
        print(f"Error: not a bag dir and not a directory: {path}", file=sys.stderr)
        return 2

    if not args.recursive:
        # Non-recursive: treat immediate children that are bags
        bag_dirs = []
        for name in sorted(os.listdir(path)):
            cand = os.path.join(path, name)
            if _bag_is_dir(cand):
                bag_dirs.append(cand)
    else:
        bag_dirs = find_bag_dirs(path)

    if bag_prefix:
        bag_dirs = [d for d in bag_dirs if os.path.basename(os.path.normpath(d)).startswith(bag_prefix)]

    if not bag_dirs:
        print(f"No bag directories found under: {path}", file=sys.stderr)
        return 3

    for bag_dir in bag_dirs:
        try:
            out_dir = convert_bag(bag_dir, args.out_root, args.desired_flag, args.sustain_s, debug=debug)
            print(f"[OK] {bag_dir} -> {out_dir}")
        except Exception as e:
            print(f"[FAIL] {bag_dir}: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


