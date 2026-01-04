#!/usr/bin/env python3
"""
Minimal motion-vs-GNSS plotter.

What it does:
- Plots commanded speed from `motion_cmd_vel.csv` (lin_x).
- Plots GNSS-derived speed from successive lat/lon rows (no smoothing, no interpolation).
- Uses a single shared timebase: t_rel = ts_sec - min(ts_sec across all series).

Inputs (from `bag_to_human_csv.py` outputs in a run folder):
- motion_cmd_vel.csv
- gnss_f9p_helical_fix.csv
- gnss_pixhawk_navsatfix.csv

Modes:
- Interactive by default (opens a window via matplotlib).
- Save PNG when requested via `--png` (or `--out` / `--outdir`).

Examples:
  Interactive (default):
    python3 motion_plotter.py --run /path/to/human_csv/<run>.bag

  Save next to CSVs:
    python3 motion_plotter.py --run /path/to/human_csv/<run>.bag --png

  Save into an outdir (batch-friendly):
    python3 motion_plotter.py --run /path/to/human_csv/<run>.bag --outdir plots_all
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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


def _load_cmd_lin_x(run: Path) -> Optional[Series]:
    p = run / "motion_cmd_vel.csv"
    if not p.exists():
        return None
    rows = _read_csv_rows(p)
    t: List[float] = []
    y: List[float] = []
    for row in rows:
        ts = _to_float(row.get("ts_sec"))
        lin_x = _to_float(row.get("lin_x"))
        if ts is None or lin_x is None:
            continue
        t.append(ts)
        y.append(lin_x)
    if len(t) < 2:
        return None
    return Series(name="cmd_vel lin_x [m/s]", t_sec=t, y=y)


def _latlon_to_xy_m(lat_deg: float, lon_deg: float, lat0_rad: float, lon0_deg: float, lat0_deg: float) -> Tuple[float, float]:
    # Simple equirectangular approximation
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * math.cos(lat0_rad)
    x = (lon_deg - lon0_deg) * m_per_deg_lon
    y = (lat_deg - lat0_deg) * m_per_deg_lat
    return x, y


def _load_gnss_speed(run: Path, csv_name: str, label: str) -> Optional[Series]:
    p = run / csv_name
    if not p.exists():
        return None
    rows = _read_csv_rows(p)

    # Collect (t, lat, lon) in-file order, skipping incomplete rows.
    t: List[float] = []
    lat: List[float] = []
    lon: List[float] = []
    for row in rows:
        ts = _to_float(row.get("ts_sec"))
        la = _to_float(row.get("lat") or row.get("latitude"))
        lo = _to_float(row.get("lon") or row.get("longitude"))
        if ts is None or la is None or lo is None:
            continue
        t.append(ts)
        lat.append(la)
        lon.append(lo)

    if len(t) < 2:
        return None

    # Reference origin at first GNSS point
    lat0_deg = lat[0]
    lon0_deg = lon[0]
    lat0_rad = math.radians(lat0_deg)

    # Compute speed per step, aligned to t[i] (line-by-line, no interpolation)
    v: List[float] = [float("nan")]
    prev_x, prev_y = _latlon_to_xy_m(lat[0], lon[0], lat0_rad, lon0_deg, lat0_deg)
    prev_t = t[0]
    for i in range(1, len(t)):
        cur_x, cur_y = _latlon_to_xy_m(lat[i], lon[i], lat0_rad, lon0_deg, lat0_deg)
        dt = t[i] - prev_t
        if dt <= 0.0:
            v.append(float("nan"))
        else:
            dist = math.hypot(cur_x - prev_x, cur_y - prev_y)
            v.append(dist / dt)
        prev_x, prev_y, prev_t = cur_x, cur_y, t[i]

    return Series(name=label, t_sec=t, y=v)


def _global_t0(series: List[Series]) -> float:
    t0 = None
    for s in series:
        if not s.t_sec:
            continue
        mn = min(s.t_sec)
        t0 = mn if t0 is None else min(t0, mn)
    return 0.0 if t0 is None else float(t0)


def _default_png_name(run: Path) -> str:
    return f"{run.name}__cmd_vs_gnss_speed.png"


def main() -> int:
    ap = argparse.ArgumentParser(description="cmd_vel vs GNSS-derived speed.")
    ap.add_argument("--run", required=True, help="Run folder (human_csv/<run>.bag/)")
    ap.add_argument(
        "--png",
        action="store_true",
        help="Save a PNG instead of showing an interactive window (headless-friendly).",
    )
    ap.add_argument(
        "--out",
        default=None,
        help="Output PNG path (implies --png). If omitted with --png, saves next to the run CSVs.",
    )
    ap.add_argument(
        "--outdir",
        default=None,
        help="Output directory for PNG (implies --png). Filename is derived from run name.",
    )
    args = ap.parse_args()

    run = Path(args.run)
    if not run.exists() or not run.is_dir():
        raise SystemExit(f"Run folder not found: {run}")

    save_png = bool(args.png or args.out or args.outdir)
    out: Optional[Path] = None
    if save_png:
        if args.out:
            out = Path(args.out)
        elif args.outdir:
            outdir = Path(args.outdir)
            outdir.mkdir(parents=True, exist_ok=True)
            out = outdir / _default_png_name(run)
        else:
            out = run / _default_png_name(run)
        out.parent.mkdir(parents=True, exist_ok=True)

    series: List[Series] = []
    s_cmd = _load_cmd_lin_x(run)
    if s_cmd is not None:
        series.append(s_cmd)

    s_f9p = _load_gnss_speed(run, "gnss_f9p_helical_fix.csv", "GNSS speed (F9P helical) [m/s]")
    if s_f9p is not None:
        series.append(s_f9p)

    s_px4 = _load_gnss_speed(run, "gnss_pixhawk_navsatfix.csv", "GNSS speed (Pixhawk) [m/s]")
    if s_px4 is not None:
        series.append(s_px4)

    if not series:
        raise SystemExit(f"No usable series found in: {run}")

    t0 = _global_t0(series)

    fig, ax = plt.subplots(figsize=(12, 6), layout="constrained")
    for s in series:
        t_rel = [tt - t0 for tt in s.t_sec]
        ax.plot(t_rel, s.y, lw=1.2, label=s.name)

    ax.set_title(f"cmd_vel vs GNSS-derived speed | {run.name}")
    ax.set_xlabel("Time [s] (shared, relative)")
    ax.set_ylabel("Speed [m/s]")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), frameon=False)

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


