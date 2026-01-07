#!/usr/bin/env python3
"""
Interactive cmd_vel plotter (all components).

Usage:
  python3 cmd_vel_plotter.py --run /path/to/human_csv/<run>.bag

Reads:
  <run>/motion_cmd_vel.csv

Plots (vs relative time):
  - lin_x, lin_y, lin_z
  - ang_x, ang_y, ang_z

No file saving; always interactive.
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np


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


def main() -> int:
    ap = argparse.ArgumentParser(description="Interactive plot of all cmd_vel components.")
    ap.add_argument("--run", required=True, help="Run folder (human_csv/<run>.bag/)")
    args = ap.parse_args()

    run = Path(args.run)
    if not run.exists() or not run.is_dir():
        raise SystemExit(f"Run folder not found: {run}")

    p = run / "motion_cmd_vel.csv"
    if not p.exists():
        raise SystemExit(f"Missing CSV: {p}")

    rows = _read_csv_rows(p)

    t: List[float] = []
    lin_x: List[float] = []
    lin_y: List[float] = []
    lin_z: List[float] = []
    ang_x: List[float] = []
    ang_y: List[float] = []
    ang_z: List[float] = []

    for row in rows:
        ts = _to_float(row.get("ts_sec"))
        lx = _to_float(row.get("lin_x"))
        ly = _to_float(row.get("lin_y"))
        lz = _to_float(row.get("lin_z"))
        ax = _to_float(row.get("ang_x"))
        ay = _to_float(row.get("ang_y"))
        az = _to_float(row.get("ang_z"))
        if ts is None or lx is None or ly is None or lz is None or ax is None or ay is None or az is None:
            continue
        t.append(ts)
        lin_x.append(lx)
        lin_y.append(ly)
        lin_z.append(lz)
        ang_x.append(ax)
        ang_y.append(ay)
        ang_z.append(az)

    if len(t) < 2:
        raise SystemExit(f"Not enough cmd_vel rows to plot in: {p}")

    t0 = min(t)
    t_rel = [tt - t0 for tt in t]

    fig, (ax_lin, ax_ang) = plt.subplots(2, 1, figsize=(12, 7), sharex=True, layout="constrained")

    ax_lin.plot(t_rel, lin_x, lw=1.1, label="lin_x [m/s]")
    ax_lin.plot(t_rel, lin_y, lw=1.1, label="lin_y [m/s]")
    ax_lin.plot(t_rel, lin_z, lw=1.1, label="lin_z [m/s]")
    ax_lin.set_title(f"cmd_vel (all components) | {run.name}")
    ax_lin.set_ylabel("Linear [m/s]")
    ax_lin.grid(True, alpha=0.25)
    ax_lin.legend(loc="upper left", frameon=False)

    ax_ang.plot(t_rel, ang_x, lw=1.1, label="ang_x [rad/s]")
    ax_ang.plot(t_rel, ang_y, lw=1.1, label="ang_y [rad/s]")
    ax_ang.plot(t_rel, ang_z, lw=1.1, label="ang_z [rad/s]")
    ax_ang.set_xlabel("Time [s] (relative)")
    ax_ang.set_ylabel("Angular [rad/s]")
    ax_ang.grid(True, alpha=0.25)
    ax_ang.legend(loc="upper left", frameon=False)

    # Radius estimate from cmd_vel: r(t) = v / w (for planar circular motion use v_xy / |w_z|)
    vxy = np.sqrt(np.asarray(lin_x, dtype=float) ** 2 + np.asarray(lin_y, dtype=float) ** 2)
    wz = np.asarray(ang_z, dtype=float)
    eps = 1e-4
    ok = np.isfinite(vxy) & np.isfinite(wz) & (np.abs(wz) > eps)
    r_cmd = np.full_like(vxy, np.nan, dtype=float)
    r_cmd[ok] = vxy[ok] / np.abs(wz[ok])

    if int(np.count_nonzero(ok)) >= 3:
        r_med = float(np.nanmedian(r_cmd))
        r_p10 = float(np.nanpercentile(r_cmd, 10))
        r_p90 = float(np.nanpercentile(r_cmd, 90))
        ok_pct = 100.0 * float(np.count_nonzero(ok)) / float(len(ok))
        ax_lin.text(
            0.99,
            0.03,
            f"r_cmd = v_xy/|wz|\nmedian≈{r_med:.2f} m  (p10–p90≈{r_p10:.2f}–{r_p90:.2f} m)\nvalid≈{ok_pct:.1f}%",
            transform=ax_lin.transAxes,
            ha="right",
            va="bottom",
            fontsize=10,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="0.8", alpha=0.9),
        )
    else:
        ax_lin.text(
            0.99,
            0.03,
            "r_cmd = v_xy/|wz|\n(insufficient valid samples)",
            transform=ax_lin.transAxes,
            ha="right",
            va="bottom",
            fontsize=10,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="0.8", alpha=0.9),
        )

    plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


