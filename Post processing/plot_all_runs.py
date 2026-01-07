#!/usr/bin/env python3
"""
Batch-generate validation plots for every run folder under a human_csv root.

Example:
  python3 plot_all_runs.py \\
    --human-csv-root /path/to/exports/human_csv \\
    --outdir /path/to/plots_all
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--human-csv-root", required=True, help="Path containing many <run>.bag/ folders")
    ap.add_argument("--outdir", required=True, help="Directory to write PNGs into")
    ap.add_argument(
        "--mode",
        default="legacy",
        choices=["legacy", "jan5"],
        help="legacy: run a single plotting script once per run; jan5: run motion+imu plotters for Jan 5 pipeline.",
    )
    ap.add_argument("--script", default="motion_plotter.py", help="(legacy mode) Path to plotting script")
    ap.add_argument("--motion-script", default="motion_plotter.py", help="(jan5 mode) Motion plotting script")
    ap.add_argument("--imu-script", default="imu_plotter.py", help="(jan5 mode) IMU plotting script")
    args = ap.parse_args()

    root = Path(args.human_csv_root)
    outdir = Path(args.outdir)
    script = Path(args.script)
    motion_script = Path(args.motion_script)
    imu_script = Path(args.imu_script)

    if not root.exists() or not root.is_dir():
        raise SystemExit(f"human-csv-root not found: {root}")
    if args.mode == "legacy":
        if not script.exists():
            raise SystemExit(f"plot script not found: {script}")
    else:
        if not motion_script.exists():
            raise SystemExit(f"motion script not found: {motion_script}")
        if not imu_script.exists():
            raise SystemExit(f"imu script not found: {imu_script}")

    outdir.mkdir(parents=True, exist_ok=True)

    runs = sorted([p for p in root.iterdir() if p.is_dir() and p.name.endswith(".bag")])
    if not runs:
        print(f"No run folders found under: {root}")
        return 2

    ok = 0
    fail = 0
    for run in runs:
        try:
            if args.mode == "legacy":
                cmd = [
                    "python3",
                    str(script),
                    "--run",
                    str(run),
                    "--png",
                    "--outdir",
                    str(outdir),
                ]
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
            else:
                cmd_motion = [
                    "python3",
                    str(motion_script),
                    "--run",
                    str(run),
                    "--png",
                    "--outdir",
                    str(outdir),
                    "--jan5",
                ]
                subprocess.run(cmd_motion, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

                cmd_imu = [
                    "python3",
                    str(imu_script),
                    "--run",
                    str(run),
                    "--png",
                    "--outdir",
                    str(outdir),
                ]
                subprocess.run(cmd_imu, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
            ok += 1
        except subprocess.CalledProcessError:
            fail += 1

    print(f"Done. runs_ok={ok} runs_failed={fail} outdir={outdir}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())



