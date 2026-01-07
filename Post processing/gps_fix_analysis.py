#!/usr/bin/env python3
"""
Unified GNSS fix/re-fix analysis for:
- ROS2 bags (via bag_to_human_csv.py)
- Ohcoach cell .ftg logs (via ohcoach_cell_tools.ftg_parser.FtgParser)

This script intentionally *runs/uses* the two existing parsers in this repo:
  - bag_to_human_csv.convert_bag(...)  -> produces human_csv/<bag>/gnss_timeline.csv
  - FtgParser.parse(bytes)             -> yields GPS dataframe with pos_mode (N/A/D)

It then computes per-receiver metrics:
- time_to_first_fix_s (TTFF): first sustained desired fix segment start - first sample time
- total_fix_time_s: sum of sustained desired-fix segment durations
- num_fix_segments: number of sustained desired-fix segments
- num_refix_events: number of times the receiver re-entered desired fix after losing it
- refix_time statistics: durations between end of a fix segment and start of the next

Project fix flags (from README.md):
  F (RTK Fix), R (RTK Float), D (Differential), 3D, 2D, N (No fix)

Ohcoach mapping (best-effort, based on ohcoach-cell-tools README + pos_mode field):
  pos_mode == 'N' -> N
  pos_mode == 'D' -> D
  pos_mode == 'A' -> 3D
  else            -> U

Examples:
  Analyze a ROS2 bag and write outputs under its human_csv folder:
    python3 gps_fix_analysis.py --bag /path/to/bag_dir

  Analyze Ohcoach .ftg files (file or directory):
    python3 gps_fix_analysis.py --ftg /path/to/file.ftg --out-root /tmp/out
    python3 gps_fix_analysis.py --ftg /path/to/dir_with_ftg --recursive
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


# ------------------------- shared helpers -------------------------


def _ts_to_iso_utc(ts_sec: float) -> str:
    try:
        return _dt.datetime.utcfromtimestamp(ts_sec).isoformat() + "Z"
    except Exception:
        return ""


def _safe_float(x: object) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def _safe_int(x: object) -> Optional[int]:
    try:
        if x is None:
            return None
        return int(x)
    except Exception:
        return None


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


class LazyCsv:
    def __init__(self, path: str, fieldnames: List[str]):
        self.path = path
        self.fieldnames = fieldnames
        self._fh = None
        self._writer = None

    def write(self, row: Dict[str, object]) -> None:
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


@dataclass(frozen=True)
class TimelineRow:
    ts_sec: float
    ts_iso_utc: str
    receiver: str
    fix_flag: str
    lat: str = ""
    lon: str = ""
    alt: str = ""
    detail: str = ""


@dataclass(frozen=True)
class FixSegment:
    receiver: str
    index: int
    start_ts: float
    end_ts: float

    @property
    def duration_s(self) -> float:
        return max(0.0, self.end_ts - self.start_ts)


def _compute_segments_and_refix(
    rows: List[TimelineRow],
    desired_flag: str,
    sustain_s: float,
) -> Tuple[List[FixSegment], List[Tuple[float, float, float]]]:
    """
    Returns:
      segments: sustained desired-flag segments (>= sustain_s)
      refix_intervals: list of (loss_end_ts, refix_start_ts, refix_time_s) for segments after the first
    """
    if not rows:
        return [], []
    rows_sorted = sorted(rows, key=lambda r: r.ts_sec)

    segments: List[FixSegment] = []
    refix_intervals: List[Tuple[float, float, float]] = []

    in_desired = False
    candidate_start: Optional[float] = None
    seg_start: Optional[float] = None
    last_desired_ts: Optional[float] = None

    for r in rows_sorted:
        ts = r.ts_sec
        if r.fix_flag == desired_flag:
            last_desired_ts = ts
            if not in_desired:
                if candidate_start is None:
                    candidate_start = ts
                # Enter desired only after sustaining for >= sustain_s.
                if (ts - candidate_start) >= sustain_s:
                    in_desired = True
                    seg_start = candidate_start
                    segments.append(
                        FixSegment(receiver=r.receiver, index=len(segments), start_ts=seg_start, end_ts=seg_start)
                    )
        else:
            candidate_start = None
            if in_desired and seg_start is not None:
                # End at the last timestamp where desired was actually observed (avoids overcounting).
                seg_end = last_desired_ts if last_desired_ts is not None else ts
                seg = segments[-1]
                segments[-1] = FixSegment(receiver=seg.receiver, index=seg.index, start_ts=seg.start_ts, end_ts=seg_end)
            in_desired = False
            seg_start = None
            last_desired_ts = None

    # Finalize if still in desired
    if in_desired and seg_start is not None and last_desired_ts is not None:
        seg = segments[-1]
        segments[-1] = FixSegment(receiver=seg.receiver, index=seg.index, start_ts=seg.start_ts, end_ts=last_desired_ts)

    # Refix intervals between segments
    for i in range(1, len(segments)):
        loss_end = segments[i - 1].end_ts
        refix_start = segments[i].start_ts
        refix_intervals.append((loss_end, refix_start, max(0.0, refix_start - loss_end)))

    return segments, refix_intervals


def compute_fix_metrics(
    rows: List[TimelineRow],
    desired_flag: str,
    sustain_s: float,
) -> Tuple[Dict[str, object], List[FixSegment], List[Tuple[float, float, float]]]:
    if not rows:
        return (
            {
                "receiver": "",
                "desired_flag": desired_flag,
                "sustain_s": sustain_s,
                "samples": 0,
                "first_ts": "",
                "last_ts": "",
                "span_s": "",
                "time_to_first_fix_s": "",
                "first_fix_ts": "",
                "total_fix_time_s": 0.0,
                "fix_fraction": "",
                "num_fix_segments": 0,
                "num_refix_events": 0,
                "refix_time_mean_s": "",
                "refix_time_min_s": "",
                "refix_time_max_s": "",
            },
            [],
            [],
        )

    rows_sorted = sorted(rows, key=lambda r: r.ts_sec)
    receiver = rows_sorted[0].receiver
    first_ts = rows_sorted[0].ts_sec
    last_ts = rows_sorted[-1].ts_sec
    span_s = max(0.0, last_ts - first_ts)

    segments, refix_intervals = _compute_segments_and_refix(rows_sorted, desired_flag=desired_flag, sustain_s=sustain_s)

    total_fix_time_s = sum(s.duration_s for s in segments)
    fix_fraction = "" if span_s <= 0 else f"{(total_fix_time_s / span_s):.6f}"

    first_fix_ts = segments[0].start_ts if segments else None
    ttff = "" if first_fix_ts is None else f"{max(0.0, first_fix_ts - first_ts):.3f}"

    refix_times = [x[2] for x in refix_intervals]
    if refix_times:
        refix_mean = sum(refix_times) / len(refix_times)
        refix_min = min(refix_times)
        refix_max = max(refix_times)
        refix_mean_s = f"{refix_mean:.3f}"
        refix_min_s = f"{refix_min:.3f}"
        refix_max_s = f"{refix_max:.3f}"
    else:
        refix_mean_s = ""
        refix_min_s = ""
        refix_max_s = ""

    metrics = {
        "receiver": receiver,
        "desired_flag": desired_flag,
        "sustain_s": sustain_s,
        "samples": len(rows_sorted),
        "first_ts": f"{first_ts:.9f}",
        "last_ts": f"{last_ts:.9f}",
        "span_s": f"{span_s:.3f}",
        "time_to_first_fix_s": ttff,
        "first_fix_ts": "" if first_fix_ts is None else f"{first_fix_ts:.9f}",
        "total_fix_time_s": f"{total_fix_time_s:.3f}",
        "fix_fraction": fix_fraction,
        "num_fix_segments": len(segments),
        "num_refix_events": max(0, len(segments) - 1),
        "refix_time_mean_s": refix_mean_s,
        "refix_time_min_s": refix_min_s,
        "refix_time_max_s": refix_max_s,
    }

    return metrics, segments, refix_intervals


# ------------------------- bag pathway (ROS2) -------------------------


def convert_and_load_bag_timeline(
    bag_dir: str,
    out_root: Optional[str],
    desired_flag: str,
    sustain_s: float,
) -> Tuple[str, List[TimelineRow]]:
    try:
        import bag_to_human_csv  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "Failed to import bag_to_human_csv.py. Ensure you're running from the repo root and that dependencies "
            "(e.g., 'rosbags') are installed."
        ) from e

    # bag_to_human_csv.convert_bag requires a 'debug' flag; we enable it here so the
    # converter emits its timeline + per-receiver quick metrics (useful for inspection).
    #
    # NOTE: Even if timeline is missing for some reason, we can synthesize it from other CSVs below.
    out_dir = bag_to_human_csv.convert_bag(bag_dir, out_root, desired_flag, sustain_s, debug=True)
    timeline_path = os.path.join(out_dir, "gnss_timeline.csv")
    if not os.path.exists(timeline_path):
        # Fallback: the bag converter uses lazy CSV writers; if no timeline rows were written,
        # gnss_timeline.csv won't be created. Try to synthesize a timeline from other CSVs.
        synthesized: List[TimelineRow] = []

        def _read_csv_rows(path: str) -> Iterable[Dict[str, str]]:
            if not os.path.exists(path):
                return []
            with open(path, "r", newline="") as f:
                yield from csv.DictReader(f)

        # F9P helical (best source)
        for r in _read_csv_rows(os.path.join(out_dir, "gnss_f9p_helical_rtk_status.csv")):
            ts = _safe_float(r.get("ts_sec"))
            if ts is None:
                continue
            synthesized.append(
                TimelineRow(
                    ts_sec=ts,
                    ts_iso_utc=str(r.get("ts_iso_utc") or ""),
                    receiver="f9p_helical",
                    fix_flag=str(r.get("fix_flag") or ""),
                    lat=str(r.get("lat") or ""),
                    lon=str(r.get("lon") or ""),
                    alt="",
                    detail=f"{r.get('fix_desc','')}; q={r.get('quality','')}; sats={r.get('sats','')}; hdop={r.get('hdop','')}; rtcm_active={r.get('rtcm_active','')}",
                )
            )

        # Pixhawk GPSRAW (preferred)
        for r in _read_csv_rows(os.path.join(out_dir, "pixhawk_gpsraw_gps1.csv")):
            ts = _safe_float(r.get("ts_sec"))
            if ts is None:
                continue
            synthesized.append(
                TimelineRow(
                    ts_sec=ts,
                    ts_iso_utc=str(r.get("ts_iso_utc") or ""),
                    receiver="pixhawk",
                    fix_flag=str(r.get("fix_flag") or ""),
                    lat=str(r.get("lat_deg") or ""),
                    lon=str(r.get("lon_deg") or ""),
                    alt=str(r.get("alt_m") or ""),
                    detail=f"GPSRAW.fix_type={r.get('fix_type','')}",
                )
            )

        # Pixhawk NavSatFix fallback (only if present)
        for r in _read_csv_rows(os.path.join(out_dir, "gnss_pixhawk_navsatfix.csv")):
            ts = _safe_float(r.get("ts_sec"))
            if ts is None:
                continue
            synthesized.append(
                TimelineRow(
                    ts_sec=ts,
                    ts_iso_utc=str(r.get("ts_iso_utc") or ""),
                    receiver="pixhawk",
                    fix_flag=str(r.get("fix_flag") or ""),
                    lat=str(r.get("lat") or ""),
                    lon=str(r.get("lon") or ""),
                    alt=str(r.get("alt") or ""),
                    detail=f"NavSatFix.status={r.get('navsat_status','')}",
                )
            )

        if synthesized:
            # Write it for inspection and return it.
            write_timeline_csv(out_dir, "gnss_timeline.csv", synthesized)
            return out_dir, synthesized

        # Still nothing: return empty and let caller decide how to proceed.
        return out_dir, []

    rows: List[TimelineRow] = []
    with open(timeline_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            ts = _safe_float(r.get("ts_sec"))
            if ts is None:
                continue
            rows.append(
                TimelineRow(
                    ts_sec=ts,
                    ts_iso_utc=str(r.get("ts_iso_utc") or ""),
                    receiver=str(r.get("receiver") or ""),
                    fix_flag=str(r.get("fix_flag") or ""),
                    lat=str(r.get("lat") or ""),
                    lon=str(r.get("lon") or ""),
                    alt=str(r.get("alt") or ""),
                    detail=str(r.get("detail") or ""),
                )
            )

    return out_dir, rows


def _bag_is_dir(bag_path: str) -> bool:
    return os.path.isdir(bag_path) and os.path.exists(os.path.join(bag_path, "metadata.yaml"))


def find_bag_dirs(root: str) -> List[str]:
    out: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        if "metadata.yaml" in filenames:
            out.append(dirpath)
            dirnames[:] = []
    return sorted(out)


def read_bag_time_window_epoch_s(bag_dir: str) -> Tuple[float, float]:
    """
    Reads ROS2 bag start and end time from metadata.yaml, as epoch seconds.
    Expects typical Humble/Foxy metadata.yaml structure:
      rosbag2_bagfile_information:
        starting_time:
          nanoseconds_since_epoch: <int>
        duration:
          nanoseconds: <int>
    """
    meta_path = os.path.join(bag_dir, "metadata.yaml")
    if not os.path.exists(meta_path):
        raise FileNotFoundError(f"metadata.yaml not found: {meta_path}")

    try:
        import yaml  # type: ignore
    except Exception as e:
        raise RuntimeError("Missing dependency 'pyyaml'. Install it (or use the same env as bag_to_human_csv.py).") from e

    with open(meta_path, "r") as f:
        meta = yaml.safe_load(f)

    info = (meta or {}).get("rosbag2_bagfile_information") or {}
    starting_time = info.get("starting_time") or {}
    duration = info.get("duration") or {}

    start_ns = _safe_int(starting_time.get("nanoseconds_since_epoch"))
    dur_ns = _safe_int(duration.get("nanoseconds"))
    if start_ns is None or dur_ns is None:
        raise ValueError(f"Could not parse starting_time/duration from: {meta_path}")

    start_s = start_ns / 1e9
    end_s = (start_ns + dur_ns) / 1e9
    return float(start_s), float(end_s)


# ------------------------- ftg pathway (Ohcoach) -------------------------


def _ensure_ohcoach_importable(repo_root: str) -> None:
    # ohcoach-cell-tools is a sibling directory of this script in the repo root.
    ohcoach_root = os.path.join(repo_root, "ohcoach-cell-tools")
    if os.path.isdir(ohcoach_root) and ohcoach_root not in sys.path:
        sys.path.insert(0, ohcoach_root)


def _ohcoach_pos_mode_to_fix_flag(pos_mode: str) -> str:
    v = (pos_mode or "").strip().upper()
    if v == "N":
        return "N"
    if v == "D":
        return "D"
    if v == "A":
        # autonomous fix (no RTK info); treat as 3D best-effort
        return "3D"
    return "U"


def iter_ftg_files(path: str, recursive: bool) -> List[str]:
    if os.path.isfile(path):
        return [path]
    if not os.path.isdir(path):
        return []
    out: List[str] = []
    if not recursive:
        for name in sorted(os.listdir(path)):
            p = os.path.join(path, name)
            if os.path.isfile(p) and p.lower().endswith(".ftg"):
                out.append(p)
        return out
    for dirpath, _, filenames in os.walk(path):
        for fn in filenames:
            if fn.lower().endswith(".ftg"):
                out.append(os.path.join(dirpath, fn))
    return sorted(out)


def parse_ftg_to_timeline_rows(ftg_path: str, receiver: str = "ohcoach_cell") -> List[TimelineRow]:
    repo_root = str(Path(__file__).resolve().parent)
    _ensure_ohcoach_importable(repo_root)

    try:
        from ohcoach_cell_tools.ftg_parser.ftg_parser import FtgParser  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "Failed to import ohcoach_cell_tools. If you're not using Poetry, ensure deps are installed "
            "(pandas/numpy/etc) and that 'ohcoach-cell-tools/' is present."
        ) from e

    with open(ftg_path, "rb") as f:
        contents = f.read()

    rows: List[TimelineRow] = []
    # FtgParser yields multiple cycles; each row has an absolute datetime (UTC) from GNSS.
    # We'll convert that datetime to epoch seconds so we can align it to the ROS bag window.
    for cycle_idx, (_start, gps_df, _imu_df, _bs_df, _end, _errors) in enumerate(FtgParser.parse(contents)):
        if gps_df is None or getattr(gps_df, "empty", True):
            continue

        for _, r in gps_df.iterrows():  # type: ignore[attr-defined]
            dt = r.get("datetime")
            try:
                dt_py = dt.to_pydatetime()  # type: ignore[attr-defined]
            except Exception:
                dt_py = dt
            if not isinstance(dt_py, _dt.datetime):
                continue

            # dt_py is built by date_time_utc_to_datetime() (naive datetime). Treat it as UTC.
            dt_utc = dt_py.replace(tzinfo=_dt.timezone.utc)
            ts_epoch_s = dt_utc.timestamp()

            pos_mode = str(r.get("pos_mode") or "")
            fix_flag = _ohcoach_pos_mode_to_fix_flag(pos_mode)
            lat = r.get("latitude")
            lon = r.get("longitude")

            rows.append(
                TimelineRow(
                    ts_sec=float(ts_epoch_s),
                    ts_iso_utc=dt_utc.isoformat().replace("+00:00", "Z"),
                    receiver=receiver,
                    fix_flag=fix_flag,
                    lat="" if lat is None else str(lat),
                    lon="" if lon is None else str(lon),
                    alt="",
                    detail=f"ftg={os.path.basename(ftg_path)}; cycle={cycle_idx}; pos_mode={pos_mode}; gps_valid={r.get('gps_valid','')}",
                )
            )

    return rows


def rebase_rows_to_start(rows: List[TimelineRow], start_epoch_s: float) -> List[TimelineRow]:
    out: List[TimelineRow] = []
    for r in rows:
        out.append(
            TimelineRow(
                ts_sec=float(r.ts_sec - start_epoch_s),
                ts_iso_utc=r.ts_iso_utc,
                receiver=r.receiver,
                fix_flag=r.fix_flag,
                lat=r.lat,
                lon=r.lon,
                alt=r.alt,
                detail=r.detail,
            )
        )
    return out


def filter_rows_by_epoch_window(
    rows: List[TimelineRow],
    start_epoch_s: float,
    end_epoch_s: float,
    margin_s: float,
) -> List[TimelineRow]:
    lo = start_epoch_s - margin_s
    hi = end_epoch_s + margin_s
    return [r for r in rows if lo <= r.ts_sec <= hi]


def filter_rows_by_epoch_window_with_offset(
    rows: List[TimelineRow],
    start_epoch_s: float,
    end_epoch_s: float,
    margin_s: float,
    offset_s: float,
) -> List[TimelineRow]:
    """
    Like filter_rows_by_epoch_window(), but treats each row timestamp as (ts_sec + offset_s).

    This is useful when one data source is recorded/logged in local time while another is
    recorded in UTC epoch time. For Korea, KST is UTC+9, so a common mismatch can be fixed by
    applying offset_s in {+9h, -9h} and picking the best overlap.
    """
    lo = start_epoch_s - margin_s
    hi = end_epoch_s + margin_s
    out: List[TimelineRow] = []
    for r in rows:
        ts = float(r.ts_sec) + float(offset_s)
        if lo <= ts <= hi:
            out.append(
                TimelineRow(
                    ts_sec=ts,
                    ts_iso_utc=r.ts_iso_utc,
                    receiver=r.receiver,
                    fix_flag=r.fix_flag,
                    lat=r.lat,
                    lon=r.lon,
                    alt=r.alt,
                    detail=r.detail,
                )
            )
    return out


# ------------------------- outputs -------------------------


def write_analysis_outputs(
    out_dir: str,
    all_rows: List[TimelineRow],
    desired_flag: str,
    sustain_s: float,
    prefix: str,
) -> None:
    # Group by receiver
    by_receiver: Dict[str, List[TimelineRow]] = {}
    for r in all_rows:
        if not r.receiver:
            continue
        by_receiver.setdefault(r.receiver, []).append(r)

    w_metrics = LazyCsv(
        os.path.join(out_dir, f"{prefix}gnss_fix_metrics_summary.csv"),
        [
            "receiver",
            "desired_flag",
            "sustain_s",
            "samples",
            "first_ts",
            "last_ts",
            "span_s",
            "time_to_first_fix_s",
            "first_fix_ts",
            "total_fix_time_s",
            "fix_fraction",
            "num_fix_segments",
            "num_refix_events",
            "refix_time_mean_s",
            "refix_time_min_s",
            "refix_time_max_s",
        ],
    )
    w_segments = LazyCsv(
        os.path.join(out_dir, f"{prefix}gnss_fix_segments.csv"),
        ["receiver", "desired_flag", "sustain_s", "segment_index", "start_ts", "end_ts", "duration_s"],
    )
    w_refix = LazyCsv(
        os.path.join(out_dir, f"{prefix}gnss_refix_intervals.csv"),
        ["receiver", "desired_flag", "sustain_s", "refix_index", "loss_end_ts", "refix_start_ts", "refix_time_s"],
    )

    try:
        for receiver, rows in sorted(by_receiver.items(), key=lambda x: x[0]):
            metrics, segments, refix_intervals = compute_fix_metrics(rows, desired_flag=desired_flag, sustain_s=sustain_s)
            metrics["receiver"] = receiver
            w_metrics.write(metrics)

            for seg in segments:
                w_segments.write(
                    {
                        "receiver": receiver,
                        "desired_flag": desired_flag,
                        "sustain_s": sustain_s,
                        "segment_index": seg.index,
                        "start_ts": f"{seg.start_ts:.9f}",
                        "end_ts": f"{seg.end_ts:.9f}",
                        "duration_s": f"{seg.duration_s:.3f}",
                    }
                )

            for i, (loss_end, refix_start, dt_s) in enumerate(refix_intervals):
                w_refix.write(
                    {
                        "receiver": receiver,
                        "desired_flag": desired_flag,
                        "sustain_s": sustain_s,
                        "refix_index": i,
                        "loss_end_ts": f"{loss_end:.9f}",
                        "refix_start_ts": f"{refix_start:.9f}",
                        "refix_time_s": f"{dt_s:.3f}",
                    }
                )
    finally:
        w_metrics.close()
        w_segments.close()
        w_refix.close()


def write_timeline_csv(out_dir: str, filename: str, rows: List[TimelineRow]) -> None:
    w = LazyCsv(
        os.path.join(out_dir, filename),
        ["ts_sec", "ts_iso_utc", "receiver", "fix_flag", "lat", "lon", "alt", "detail"],
    )
    try:
        for r in sorted(rows, key=lambda x: x.ts_sec):
            w.write(
                {
                    "ts_sec": f"{r.ts_sec:.9f}",
                    "ts_iso_utc": r.ts_iso_utc,
                    "receiver": r.receiver,
                    "fix_flag": r.fix_flag,
                    "lat": r.lat,
                    "lon": r.lon,
                    "alt": r.alt,
                    "detail": r.detail,
                }
            )
    finally:
        w.close()


# ------------------------- CLI -------------------------


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Compute GNSS fix/re-fix metrics from ROS2 bags and/or Ohcoach .ftg logs.")
    p.add_argument("--bag", default=None, help="ROS2 bag directory (contains metadata.yaml).")
    p.add_argument("--ftg", default=None, help="Ohcoach .ftg file OR directory containing .ftg files.")
    p.add_argument("--recursive", action="store_true", help="If --ftg is a directory, scan recursively.")
    p.add_argument(
        "--bag-recursive",
        action="store_true",
        help="If --bag is a directory of many bags, scan recursively for bag dirs (contains metadata.yaml).",
    )
    p.add_argument("--out-root", default=None, help="Output root directory (default: for bag uses its own human_csv; for ftg uses cwd).")
    p.add_argument("--desired-flag", default="F", help="Desired fix flag for metrics (default: F).")
    p.add_argument("--sustain-s", type=float, default=1.0, help="Sustain time to count a fix/refix (default: 1.0s).")
    p.add_argument(
        "--match-margin-s",
        type=float,
        default=60.0,
        help="When matching FTG to a bag run by time, include this margin (seconds) around the bag window (default: 60s).",
    )
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    if not args.bag and not args.ftg:
        print("Error: provide at least one of --bag or --ftg", file=sys.stderr)
        return 2

    desired_flag = str(args.desired_flag).strip()
    sustain_s = float(args.sustain_s)

    # Parse FTG once (if provided), then reuse for all bag runs.
    all_ftg_rows_epoch: List[TimelineRow] = []
    ftg_sources: List[str] = []
    if args.ftg:
        ftg_path = args.ftg
        ftg_files = iter_ftg_files(ftg_path, recursive=bool(args.recursive))
        if not ftg_files:
            print(f"Error: no .ftg files found at: {ftg_path}", file=sys.stderr)
            return 3
        ftg_sources = ftg_files
        for fp in ftg_files:
            all_ftg_rows_epoch.extend(parse_ftg_to_timeline_rows(fp, receiver="ohcoach_cell"))

    # BAG(s)
    if args.bag:
        bag_path = args.bag
        bag_dirs: List[str]
        if _bag_is_dir(bag_path):
            bag_dirs = [bag_path]
        else:
            if not os.path.isdir(bag_path):
                print(f"Error: --bag is not a bag dir and not a directory: {bag_path}", file=sys.stderr)
                return 4
            bag_dirs = find_bag_dirs(bag_path) if bool(args.bag_recursive) else [
                os.path.join(bag_path, name)
                for name in sorted(os.listdir(bag_path))
                if _bag_is_dir(os.path.join(bag_path, name))
            ]
            if not bag_dirs:
                print(f"Error: no bag directories found under: {bag_path}", file=sys.stderr)
                return 5

        for bag_dir in bag_dirs:
            try:
                bag_start_epoch_s, bag_end_epoch_s = read_bag_time_window_epoch_s(bag_dir)
                out_dir, bag_rows_epoch = convert_and_load_bag_timeline(
                    bag_dir=bag_dir, out_root=args.out_root, desired_flag=desired_flag, sustain_s=sustain_s
                )

                # Bag rows are epoch-based; rebase to run start for per-run analysis.
                bag_rows_run = rebase_rows_to_start(bag_rows_epoch, start_epoch_s=bag_start_epoch_s) if bag_rows_epoch else []

                merged_rows_run = list(bag_rows_run)
                if all_ftg_rows_epoch:
                    margin_s = float(args.match_margin_s)
                    # FTG datetime can be effectively "local time" (or otherwise offset) while
                    # bag metadata is epoch UTC. If there is no overlap, try common offsets and
                    # pick the one that yields the most rows in the bag window.
                    candidates = [
                        (0.0, filter_rows_by_epoch_window_with_offset(all_ftg_rows_epoch, bag_start_epoch_s, bag_end_epoch_s, margin_s, 0.0)),
                        (+9.0 * 3600.0, filter_rows_by_epoch_window_with_offset(all_ftg_rows_epoch, bag_start_epoch_s, bag_end_epoch_s, margin_s, +9.0 * 3600.0)),
                        (-9.0 * 3600.0, filter_rows_by_epoch_window_with_offset(all_ftg_rows_epoch, bag_start_epoch_s, bag_end_epoch_s, margin_s, -9.0 * 3600.0)),
                    ]
                    best_offset_s, ftg_window = max(candidates, key=lambda x: len(x[1]))

                    if ftg_window:
                        # Annotate that we shifted the FTG epoch for alignment.
                        if best_offset_s != 0.0:
                            for i, r in enumerate(ftg_window):
                                ftg_window[i] = TimelineRow(
                                    ts_sec=r.ts_sec,
                                    ts_iso_utc=r.ts_iso_utc,
                                    receiver=r.receiver,
                                    fix_flag=r.fix_flag,
                                    lat=r.lat,
                                    lon=r.lon,
                                    alt=r.alt,
                                    detail=f"{r.detail}; applied_epoch_offset_s={best_offset_s:+.0f}",
                                )
                        merged_rows_run.extend(rebase_rows_to_start(ftg_window, start_epoch_s=bag_start_epoch_s))

                # Emit a merged timeline for the run (run-relative seconds).
                write_timeline_csv(out_dir, "gnss_timeline_run.csv", merged_rows_run)
                write_analysis_outputs(
                    out_dir=out_dir,
                    all_rows=merged_rows_run,
                    desired_flag=desired_flag,
                    sustain_s=sustain_s,
                    prefix="run_",
                )

                note = ""
                if all_ftg_rows_epoch:
                    # best_offset_s is defined only in the bag loop when all_ftg_rows_epoch is set.
                    try:
                        off = f"{best_offset_s:+.0f}"
                    except Exception:
                        off = ""
                    suffix = f", epoch_offset_s={off}" if off else ""
                    note = f" (matched FTG rows from {len(ftg_sources)} file(s), margin={float(args.match_margin_s)}s{suffix})"
                if not bag_rows_epoch:
                    note = (note + " " if note else " ") + "(WARN: no bag GNSS timeline rows; check topics/decoder)"
                print(f"[OK] Run analysis outputs written to: {out_dir}{note}")
            except Exception as e:
                print(f"[FAIL] {bag_dir}: {e}", file=sys.stderr)
                continue

    # FTG-only mode (no bag): keep behavior but write under out_root/human_csv/<ftgname>
    if args.ftg and not args.bag:
        out_root = args.out_root or os.getcwd()
        # If multiple ftg files, analyze each independently.
        for fp in ftg_sources:
            base = os.path.splitext(os.path.basename(fp))[0] or "ftg"
            out_dir = os.path.join(out_root, "human_csv", _sanitize_for_filename(base))
            os.makedirs(out_dir, exist_ok=True)
            rows_epoch = parse_ftg_to_timeline_rows(fp, receiver="ohcoach_cell")
            # Rebase to first sample time (epoch) so outputs remain small/relative.
            if rows_epoch:
                start_epoch = min(r.ts_sec for r in rows_epoch)
                rows_rel = rebase_rows_to_start(rows_epoch, start_epoch_s=start_epoch)
            else:
                rows_rel = []
            write_timeline_csv(out_dir, "gnss_timeline.csv", rows_rel)
            write_analysis_outputs(out_dir, rows_rel, desired_flag=desired_flag, sustain_s=sustain_s, prefix="")
            print(f"[OK] FTG-only analysis outputs written to: {out_dir} (source={fp})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


