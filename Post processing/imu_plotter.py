#!/usr/bin/env python3
"""
Per-run IMU plotter.

Jan 5 pipeline requirements:
- Per-run only (no cross-run overlays)
- Include yaw rate (IMU gyro_z / angular velocity z) alongside accel

Input: a single run folder like:
  exports_all_2026-01-05/human_csv/<run>.bag/
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib.pyplot as plt


@dataclass
class Series:
    name: str
    t_sec: List[float]
    y: List[float]


def _read_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", newline="") as f:
        r = csv.DictReader(f)
        return [row for row in r]


def _to_float(s: Optional[str]) -> Optional[float]:
    if s is None:
        return None
    s2 = str(s).strip()
    if s2 == "" or s2.lower() == "nan":
        return None
    try:
        return float(s2)
    except Exception:
        return None


def _load_imu(run: Path) -> Optional[Dict[str, List[float]]]:
    p = run / "imu.csv"
    if not p.exists():
        return None
    rows = _read_csv_rows(p)
    out: Dict[str, List[float]] = {"t": [], "ax": [], "ay": [], "az": [], "gz": []}
    for row in rows:
        ts = _to_float(row.get("ts_sec"))
        ax = _to_float(row.get("accel_x"))
        ay = _to_float(row.get("accel_y"))
        az = _to_float(row.get("accel_z"))
        gz = _to_float(row.get("gyro_z"))
        if ts is None or ax is None or ay is None or az is None or gz is None:
            continue
        out["t"].append(ts)
        out["ax"].append(ax)
        out["ay"].append(ay)
        out["az"].append(az)
        out["gz"].append(gz)
    if len(out["t"]) < 2:
        return None
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Per-run IMU plotter (accel + yaw rate).")
    ap.add_argument("--run", required=True, help="Run folder (human_csv/<run>.bag/)")
    ap.add_argument("--png", action="store_true", help="Save a PNG instead of showing interactively.")
    ap.add_argument("--outdir", default=None, help="Output directory for PNG (implies --png).")
    ap.add_argument("--out", default=None, help="Explicit output PNG path (implies --png).")
    args = ap.parse_args()

    run = Path(args.run)
    if not run.exists() or not run.is_dir():
        raise SystemExit(f"Run folder not found: {run}")

    save_png = bool(args.png or args.outdir or args.out)
    out: Optional[Path] = None
    if save_png:
        if args.out:
            out = Path(args.out)
        else:
            outdir = Path(args.outdir) if args.outdir else run
            outdir.mkdir(parents=True, exist_ok=True)
            out = outdir / f"{run.name}__imu.png"
        out.parent.mkdir(parents=True, exist_ok=True)

    imu = _load_imu(run)
    if imu is None:
        raise SystemExit(f"No usable IMU rows found in: {run / 'imu.csv'}")

    t0 = min(imu["t"])
    t_rel = [tt - t0 for tt in imu["t"]]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True, layout="constrained")
    ax1.plot(t_rel, imu["ax"], lw=1.1, label="accel_x")
    ax1.plot(t_rel, imu["ay"], lw=1.1, label="accel_y")
    ax1.plot(t_rel, imu["az"], lw=1.1, label="accel_z")
    ax1.set_title(f"IMU | {run.name}")
    ax1.set_ylabel("Accel [m/s^2]")
    ax1.grid(True, alpha=0.25)
    ax1.legend(loc="upper left", frameon=False)

    ax2.plot(t_rel, imu["gz"], lw=1.1, label="gyro_z (yaw rate)")
    ax2.set_xlabel("Time [s] (relative)")
    ax2.set_ylabel("Yaw rate [rad/s]")
    ax2.grid(True, alpha=0.25)
    ax2.legend(loc="upper left", frameon=False)

    if save_png:
        assert out is not None
        fig.savefig(out, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"[OK] Saved: {out}")
    else:
        plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


