#!/usr/bin/env python3
"""
Single-command, ROS-free GNSS fix/re-fix analysis for ROS2 bag runs.

This is the "one code you run" wrapper for the repo's existing offline pipeline:
  - bag_to_human_csv.py : ROS2 bag -> human-readable per-topic CSV + normalized fix flag timeline
  - gps_fix_analysis.py : compute TTFF / fix stability / refix metrics from the timeline

It is designed to work WITHOUT ROS installed by relying on the pure-Python `rosbags` backend.

Examples
--------
Analyze a single bag:
  python3 gnss_fix_pipeline.py "/Volumes/SHGP31-5/code/agile_ws/Experiment Data/26_0105_1710_angular_rate_level_1_15s.bag"

Analyze all bags under a root:
  python3 gnss_fix_pipeline.py "/Volumes/SHGP31-5/code/agile_ws/Experiment Data" --recursive

Write outputs somewhere specific:
  python3 gnss_fix_pipeline.py "/Volumes/SHGP31-5/code/agile_ws/Experiment Data" --recursive --out-root "/tmp/gnss_out"

recurse
  python Post\ processing/gnss_fix_pipeline.py "Experiment Data/26_0105" --recursive --ftg "Experiment Data/26_0105" --ftg-recursive --out-root "/Volumes/SHGP31-5/code/agile_ws/plot_0105_0109" --match-margin-s 10
  python Post\ processing/gnss_fix_pipeline.py "Experiment Data/26_0107" --recursive --ftg "Experiment Data/26_0107" --ftg-recursive --out-root "/Volumes/SHGP31-5/code/agile_ws/plot_0105_0109" --match-margin-s 10
  python Post\ processing/gnss_fix_pipeline.py "Experiment Data/26_0108" --recursive --ftg "Experiment Data/26_0108" --ftg-recursive --out-root "/Volumes/SHGP31-5/code/agile_ws/plot_0105_0109" --match-margin-s 10
  python Post\ processing/gnss_fix_pipeline.py "Experiment Data/26_0109" --recursive --ftg "Experiment Data/26_0109" --ftg-recursive --out-root "/Volumes/SHGP31-5/code/agile_ws/plot_0105_0109" --match-margin-s 10
"""

from __future__ import annotations

import argparse
import os
import sys
import csv
import datetime as dt
from typing import List, Optional


def _bag_is_dir(bag_path: str) -> bool:
    return os.path.isdir(bag_path) and os.path.exists(os.path.join(bag_path, "metadata.yaml"))

def _is_ftg_file(path: str) -> bool:
    return os.path.isfile(path) and path.lower().endswith(".ftg")


def find_bag_dirs(root: str) -> List[str]:
    out: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        if "metadata.yaml" in filenames:
            out.append(dirpath)
            dirnames[:] = []
    return sorted(out)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ROS-free GNSS fix/re-fix analysis for ROS2 bag runs.")
    p.add_argument(
        "path",
        help=(
            "Bag directory (contains metadata.yaml) OR a directory containing many bags. "
            "If PATH is a .ftg file, run FTG-only analysis."
        ),
    )
    p.add_argument("--recursive", action="store_true", help="If PATH is a directory, scan recursively for bag dirs.")
    p.add_argument(
        "--ftg",
        default=None,
        help=(
            "Ohcoach cell .ftg file OR directory containing .ftg files. "
            "Required for bag analysis (this pipeline treats FTG as the reference source)."
        ),
    )
    p.add_argument("--ftg-recursive", action="store_true", help="If --ftg is a directory, scan recursively.")
    p.add_argument(
        "--match-margin-s",
        type=float,
        default=10.0,
        help="When matching FTG to a bag run by time, include this margin around the bag window (default: 60s).",
    )
    p.add_argument(
        "--windows-csv",
        default=None,
        help=(
            "FTG-only mode: CSV defining run windows to slice a continuous .ftg into per-run outputs. "
            "Expected columns: start_iso_utc,end_iso_utc[,run_id]. Example start: 2025-11-04T09:00:14.600Z"
        ),
    )
    p.add_argument("--out-root", default=None, help="Output root directory (default: current working directory).")
    p.add_argument("--desired-flag", default="F", help="Desired fix flag for metrics (default: F).")
    p.add_argument("--sustain-s", type=float, default=1.0, help="Sustain time for 'refixed' metric (default: 1.0s).")
    p.add_argument(
        "--debug",
        action="store_true",
        help="Keep debug artifacts (decoded per-topic CSVs, timelines, raw dumps). Default is minimal outputs only.",
    )
    return p.parse_args(argv)


def _run_one_bag(
    bag_dir: str,
    out_root: Optional[str],
    desired_flag: str,
    sustain_s: float,
    ftg: str,
    ftg_recursive: bool,
    match_margin_s: float,
    debug: bool,
) -> int:
    try:
        import gps_fix_analysis  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "Failed to import gps_fix_analysis.py. Run from the repo root, and ensure dependencies are installed "
            "(especially 'rosbags' for non-ROS machines)."
        ) from e

    argv = [
        "--bag",
        bag_dir,
        "--out-root",
        out_root or "",
        "--desired-flag",
        desired_flag,
        "--sustain-s",
        str(sustain_s),
        "--match-margin-s",
        str(match_margin_s),
        "--ftg",
        ftg,
    ]
    if ftg_recursive:
        argv += ["--recursive"]
    if debug:
        argv += ["--debug"]
    # gps_fix_analysis treats empty out_root as "use defaults"
    argv = [x for x in argv if x != ""]
    return int(gps_fix_analysis.main(argv))

def _parse_iso_utc_to_epoch_s(s: str) -> float:
    v = (s or "").strip()
    if not v:
        raise ValueError("empty datetime string")
    # Accept trailing 'Z'
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    # Accept "YYYY-mm-dd HH:MM:SS(.sss)" by replacing space with 'T'
    if " " in v and "T" not in v:
        v = v.replace(" ", "T")
    dt_obj = dt.datetime.fromisoformat(v)
    if dt_obj.tzinfo is None:
        # Treat naive as UTC (caller should provide UTC to avoid ambiguity)
        dt_obj = dt_obj.replace(tzinfo=dt.timezone.utc)
    return float(dt_obj.timestamp())


def _run_ftg_only(ftg_path: str, out_root: str, windows_csv: Optional[str], desired_flag: str, sustain_s: float) -> int:
    try:
        import gps_fix_analysis  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "Failed to import gps_fix_analysis.py. Run from the repo root and ensure dependencies are installed."
        ) from e

    rows_epoch = gps_fix_analysis.parse_ftg_to_timeline_rows(ftg_path, receiver="ohcoach_cell")
    if not rows_epoch:
        print(f"[FAIL] No GPS rows parsed from FTG: {ftg_path}", file=sys.stderr)
        return 4

    os.makedirs(out_root, exist_ok=True)

    # No windows provided: analyze the entire file as one long session (usually not what you want).
    if not windows_csv:
        base = os.path.splitext(os.path.basename(ftg_path))[0] or "ftg"
        out_dir = os.path.join(out_root, "human_csv", base)
        os.makedirs(out_dir, exist_ok=True)
        start_epoch = min(r.ts_sec for r in rows_epoch)
        rows_rel = gps_fix_analysis.rebase_rows_to_start(rows_epoch, start_epoch_s=start_epoch)
        gps_fix_analysis.write_timeline_csv(out_dir, "gnss_timeline.csv", rows_rel)
        gps_fix_analysis.write_analysis_outputs(out_dir, rows_rel, desired_flag=desired_flag, sustain_s=sustain_s, prefix="")
        print(f"[OK] FTG-only outputs written to: {out_dir} (entire file; consider --windows-csv)")
        return 0

    # Windowed run slicing.
    windows: List[tuple[str, float, float]] = []
    with open(windows_csv, "r", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"windows csv has no header: {windows_csv}")
        for i, r in enumerate(reader):
            start_iso = (r.get("start_iso_utc") or "").strip()
            end_iso = (r.get("end_iso_utc") or "").strip()
            run_id = (r.get("run_id") or f"run_{i:03d}").strip()
            start_s = _parse_iso_utc_to_epoch_s(start_iso)
            end_s = _parse_iso_utc_to_epoch_s(end_iso)
            if end_s <= start_s:
                raise ValueError(f"Invalid window (end<=start) for run_id={run_id}: {start_iso} .. {end_iso}")
            windows.append((run_id, start_s, end_s))

    if not windows:
        print(f"[FAIL] No windows found in: {windows_csv}", file=sys.stderr)
        return 5

    ok = 0
    fail = 0
    for run_id, start_s, end_s in windows:
        rows_win_epoch = [r for r in rows_epoch if start_s <= r.ts_sec <= end_s]
        if not rows_win_epoch:
            print(f"[WARN] No FTG rows in window for run_id={run_id} ({start_s}..{end_s})")
            fail += 1
            continue
        rows_rel = gps_fix_analysis.rebase_rows_to_start(rows_win_epoch, start_epoch_s=start_s)
        out_dir = os.path.join(out_root, "human_csv", run_id)
        os.makedirs(out_dir, exist_ok=True)
        gps_fix_analysis.write_timeline_csv(out_dir, "gnss_timeline.csv", rows_rel)
        gps_fix_analysis.write_analysis_outputs(out_dir, rows_rel, desired_flag=desired_flag, sustain_s=sustain_s, prefix="")
        print(f"[OK] FTG window run_id={run_id} -> {out_dir}")
        ok += 1

    print(f"Done. ftg_windows_ok={ok} ftg_windows_failed={fail}")
    return 0 if fail == 0 else 1


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    path = args.path

    # FTG-only mode (continuous recording; optionally slice by windows CSV).
    if _is_ftg_file(path):
        out_root = args.out_root or os.getcwd()
        return _run_ftg_only(
            ftg_path=path,
            out_root=out_root,
            windows_csv=args.windows_csv,
            desired_flag=args.desired_flag,
            sustain_s=float(args.sustain_s),
        )

    # Bag analysis requires FTG reference.
    if not args.ftg:
        print("Error: --ftg is required for bag analysis (provide a .ftg file or a directory of .ftg files).", file=sys.stderr)
        return 2

    if _bag_is_dir(path):
        return _run_one_bag(
            path,
            args.out_root,
            args.desired_flag,
            float(args.sustain_s),
            ftg=str(args.ftg),
            ftg_recursive=bool(args.ftg_recursive),
            match_margin_s=float(args.match_margin_s),
            debug=bool(args.debug),
        )

    if not os.path.isdir(path):
        print(f"Error: not a bag dir and not a directory: {path}", file=sys.stderr)
        return 2

    bag_dirs: List[str]
    if args.recursive:
        bag_dirs = find_bag_dirs(path)
    else:
        bag_dirs = [
            os.path.join(path, name)
            for name in sorted(os.listdir(path))
            if _bag_is_dir(os.path.join(path, name))
        ]
    if not bag_dirs:
        print(f"No bag directories found under: {path}", file=sys.stderr)
        return 3

    ok = 0
    fail = 0
    for bag_dir in bag_dirs:
        rc = _run_one_bag(
            bag_dir,
            args.out_root,
            args.desired_flag,
            float(args.sustain_s),
            ftg=str(args.ftg),
            ftg_recursive=bool(args.ftg_recursive),
            match_margin_s=float(args.match_margin_s),
            debug=bool(args.debug),
        )
        if rc == 0:
            ok += 1
        else:
            fail += 1

    print(f"Done. runs_ok={ok} runs_failed={fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())


