#!/usr/bin/env python3
"""
Convert a ROS 2 bag directory into "human readable" CSV outputs.

This script reads the bag directly (rosbag2_py) and writes:
- per-topic CSVs with decoded fields (easier than raw JSON blobs)
- a normalized GNSS fix-flag timeline (F/R/D/3D/2D/N) where possible
- a small validity/summary report (topic counts + missing required topics)

Project context:
- README.md defines fix flags as F (RTK Fix), R (RTK Float), D, 3D, 2D, N.
- For F9P Helical, we derive a fix flag from `/gps_rtk_f9p_helical/gps/rtk_status` (String)
  which includes NMEA-derived fix quality (0..8) and RTCM status.
- For Pixhawk "regular GPS", prefer `/pixhawk/gpsstatus/gps1/raw` (mavros_msgs/msg/GPSRAW)
  which includes MAVLink `fix_type` (richer than NavSatFix.status).
  If unavailable, fall back to `/pixhawk/global_position/raw/fix` (NavSatFix) (coarse).

Examples:
  Convert one bag:
    python3 bag_to_human_csv.py /path/to/bag_dir

  Convert one bag and put outputs somewhere specific:
    python3 bag_to_human_csv.py /path/to/bag_dir --out-root /tmp/human

  Convert all bags under Experiment Data:
    python3 bag_to_human_csv.py /home/agilex/agilex_ws/Experiment\\ Data --recursive
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import math
import os
import re
import sys
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import yaml

try:
    import rosbag2_py
    from rclpy.serialization import deserialize_message
    from rosidl_runtime_py.utilities import get_message
    from rosidl_runtime_py import message_to_ordereddict
except ImportError:
    print(
        "Failed to import ROS 2 Python packages.\n"
        "Run inside a ROS 2 environment, e.g.:\n"
        "  source /opt/ros/<distro>/setup.bash\n"
        "  source install/setup.bash (if you have a workspace)\n"
    )
    raise


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


def open_bag_reader(bag_path: str) -> Tuple[rosbag2_py.SequentialReader, Dict[str, str]]:
    if not os.path.isdir(bag_path):
        raise FileNotFoundError(f"Bag path is not a directory: {bag_path}")

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
    return reader, topic_type_map


# ------------------------- parsing + normalization -------------------------


_RTK_STATUS_RE = re.compile(
    r"^FIX:\s*(?P<fix_desc>.*?)\s*"
    r"\(quality=(?P<quality>\d+),\s*sats=(?P<sats>\d+),\s*HDOP=(?P<hdop>[^)]+)\)\s*\|\s*"
    r"Lat=(?P<lat>[^,]+),\s*Lon=(?P<lon>[^|]+)\|\s*"
    r"RTCM:\s*(?P<rtcm_state>ACTIVE|STALE)\s*"
    r"\(bytes=(?P<bytes>\d+),\s*age=(?P<age>[\d.]+)s\)\s*$"
)


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
    m = _RTK_STATUS_RE.match((s or "").strip())
    if not m:
        return None

    fix_desc = m.group("fix_desc").strip()
    quality = _safe_int(m.group("quality"))
    sats = _safe_int(m.group("sats"))

    hdop_raw = m.group("hdop").strip()
    hdop = None if hdop_raw.upper() == "N/A" else _safe_float(hdop_raw)

    lat_raw = m.group("lat").strip()
    lon_raw = m.group("lon").strip()
    lat = None if lat_raw.upper() == "N/A" else _safe_float(lat_raw)
    lon = None if lon_raw.upper() == "N/A" else _safe_float(lon_raw)

    rtcm_state = m.group("rtcm_state").strip().upper()
    rtcm_active = 1 if rtcm_state == "ACTIVE" else 0

    rtcm_bytes = _safe_int(m.group("bytes")) or 0
    rtcm_age_s = _safe_float(m.group("age"))

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
    "/imu",
    "/estop",
]

# Prefer this if present (future bags)
PREFERRED_PIXHAWK_FIX_TOPIC = "/pixhawk/gpsstatus/gps1/raw"


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


def convert_bag(bag_path: str, out_root: Optional[str], desired_flag: str, sustain_s: float) -> str:
    bag_base = os.path.basename(os.path.normpath(bag_path)) or "bag"
    out_root_final = out_root or os.getcwd()
    out_dir = os.path.join(out_root_final, "human_csv", _sanitize_for_filename(bag_base))
    os.makedirs(out_dir, exist_ok=True)

    reader, topic_type_map = open_bag_reader(bag_path)

    # type cache
    msg_type_cache: Dict[str, type] = {}

    # counts
    msg_counts: Dict[str, int] = {t: 0 for t in topic_type_map.keys()}
    total_msgs = 0

    # writers
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
    w_px4_sats = LazyCsv(
        os.path.join(out_dir, "pixhawk_satellites.csv"),
        ["ts_sec", "ts_iso_utc", "satellites"],
    )
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
    w_cmd_raw = LazyCsv(
        os.path.join(out_dir, "motion_cmd_vel_raw.csv"),
        ["ts_sec", "ts_iso_utc", "lin_x", "lin_y", "lin_z", "ang_x", "ang_y", "ang_z"],
    )
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

    trackers = {
        "f9p_helical": RefixTracker("f9p_helical", desired_flag=desired_flag, sustain_s=sustain_s),
        "pixhawk": RefixTracker("pixhawk", desired_flag=desired_flag, sustain_s=sustain_s),
    }

    # If GPSRAW exists, prefer it for pixhawk flag timeline.
    have_px4_gpsraw = PREFERRED_PIXHAWK_FIX_TOPIC in topic_type_map

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

    while reader.has_next():
        topic, data, t_ns = reader.read_next()
        total_msgs += 1
        if topic in msg_counts:
            msg_counts[topic] += 1

        type_str = topic_type_map.get(topic)
        if not type_str:
            continue
        if type_str not in msg_type_cache:
            msg_type_cache[type_str] = get_message(type_str)
        msg_type = msg_type_cache[type_str]

        # Deserialize only for topics we care about (but we already have msg_type; cheap enough).
        try:
            msg_obj = deserialize_message(data, msg_type)
        except Exception:
            continue

        ts_sec = t_ns / 1e9
        ts_iso = _ts_to_iso_utc(ts_sec)
        bag_ts_ns = int(t_ns)

        # Convert to dict so field access is robust across message classes.
        msg = message_to_ordereddict(msg_obj)

        # Header stamp if present
        hdr = msg.get("header") if isinstance(msg, dict) else None
        hdr_stamp = hdr.get("stamp") if isinstance(hdr, dict) else None
        hdr_stamp_sec = _safe_int(hdr_stamp.get("sec")) if isinstance(hdr_stamp, dict) else None
        hdr_stamp_nanosec = _safe_int(hdr_stamp.get("nanosec")) if isinstance(hdr_stamp, dict) else None

        # --- F9P Helical status (best fix flag) ---
        if topic == "/gps_rtk_f9p_helical/gps/rtk_status":
            s = str((msg or {}).get("data", ""))
            parsed = parse_helical_rtk_status(s)
            if parsed:
                last_f9p_fix_flag = parsed["fix_flag"]
                last_f9p_fix_flag_ts = ts_sec
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
            if utc_hhmmss:
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
            trackers["pixhawk"].update(ts_sec, fix_flag)
            continue

        # --- Pixhawk NavSatFix (fallback only, if GPSRAW missing) ---
        if (topic == "/pixhawk/global_position/raw/fix") and (not have_px4_gpsraw):
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
            trackers["pixhawk"].update(ts_sec, fix_flag)
            continue

        # --- Pixhawk satellites ---
        if topic == "/pixhawk/global_position/raw/satellites":
            sats = _safe_int(msg.get("data"))
            if sats is not None:
                pixhawk_sat_samples += 1
                pixhawk_sat_min = sats if pixhawk_sat_min is None else min(pixhawk_sat_min, sats)
                pixhawk_sat_max = sats if pixhawk_sat_max is None else max(pixhawk_sat_max, sats)
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
                w_cmd_raw.write(out_row)
            else:
                w_cmd.write(out_row)
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

    # Write topic counts
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
        notes += "pixhawk_fix_source=NavSatFix(fallback); "
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

    # Metrics
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
        w_f9p_status,
        w_f9p_fix,
        w_px4_fix,
        w_px4_sats,
        w_px4_gpsraw,
        w_cmd,
        w_cmd_raw,
        w_imu,
        w_estop,
        w_timeline,
        w_f9p_nmea_time,
        w_metrics,
        w_counts,
        w_validity,
    ):
        w.close()

    return out_dir


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Convert ros2 bag directories into human-readable CSV outputs.")
    p.add_argument("path", help="Bag directory (contains metadata.yaml) OR a directory containing many bags.")
    p.add_argument("--recursive", action="store_true", help="If PATH is a directory, scan recursively for bag dirs.")
    p.add_argument("--out-root", default=None, help="Output root directory (default: current working directory).")
    p.add_argument("--desired-flag", default="F", help="Desired fix flag for metrics (default: F).")
    p.add_argument("--sustain-s", type=float, default=1.0, help="Sustain time for 'refixed' metric (default: 1.0s).")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    path = args.path

    if _bag_is_dir(path):
        out_dir = convert_bag(path, args.out_root, args.desired_flag, args.sustain_s)
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

    if not bag_dirs:
        print(f"No bag directories found under: {path}", file=sys.stderr)
        return 3

    for bag_dir in bag_dirs:
        try:
            out_dir = convert_bag(bag_dir, args.out_root, args.desired_flag, args.sustain_s)
            print(f"[OK] {bag_dir} -> {out_dir}")
        except Exception as e:
            print(f"[FAIL] {bag_dir}: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


