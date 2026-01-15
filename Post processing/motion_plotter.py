#!/usr/bin/env python3
"""
Motion/GNSS/wheel-odom plotter.

Generates multiple per-run PNGs:
  - cmd_vel: |v| and lin_x only (no other cmd components)
  - speeds: cmd |v| + GNSS (Pixhawk) + GNSS-RTK (F9P) + wheel odom speed
  - XY overlay: GPS (Pixhawk), GPS-RTK (F9P), wheel odom (rotated+translated for overlay)
  - angular_rate level 1–3 only: r_cmd(t)=v_xy/|wz| + wheel-odom circle-fit radius

Input: a single run folder like:
  exports_all_2026-01-05/human_csv/<run>.bag/
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np


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


def _latlon_to_xy_m(lat_deg: float, lon_deg: float, lat0_rad: float, lon0_deg: float, lat0_deg: float) -> Tuple[float, float]:
    # Simple equirectangular approximation
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * math.cos(lat0_rad)
    x = (lon_deg - lon0_deg) * m_per_deg_lon
    y = (lat_deg - lat0_deg) * m_per_deg_lat
    return x, y


def _load_cmd_twist(run: Path) -> Optional[Dict[str, List[float]]]:
    p = run / "motion_cmd_vel.csv"
    if not p.exists():
        return None
    rows = _read_csv_rows(p)
    out: Dict[str, List[float]] = {"t": [], "lin_x": [], "lin_y": [], "lin_z": [], "ang_z": []}
    for row in rows:
        ts = _to_float(row.get("ts_sec"))
        if ts is None:
            continue
        lin_x = _to_float(row.get("lin_x"))
        lin_y = _to_float(row.get("lin_y"))
        lin_z = _to_float(row.get("lin_z"))
        ang_z = _to_float(row.get("ang_z"))
        if lin_x is None or lin_y is None or lin_z is None or ang_z is None:
            continue
        out["t"].append(ts)
        out["lin_x"].append(lin_x)
        out["lin_y"].append(lin_y)
        out["lin_z"].append(lin_z)
        out["ang_z"].append(ang_z)
    if len(out["t"]) < 2:
        return None
    return out


def _load_wheel_odom(run: Path) -> Optional[Dict[str, List[float]]]:
    p = run / "wheel_odom.csv"
    if not p.exists():
        print(f"Warning: wheel_odom.csv not found in {run}")
        return None
    rows = _read_csv_rows(p)
    out: Dict[str, List[float]] = {"t": [], "x": [], "y": [], "vx": [], "vy": [], "vz": [], "wz": []}
    for row in rows:
        ts = _to_float(row.get("ts_sec"))
        if ts is None:
            continue
        x = _to_float(row.get("x"))
        y = _to_float(row.get("y"))
        vx = _to_float(row.get("vx"))
        vy = _to_float(row.get("vy"))
        vz = _to_float(row.get("vz"))
        wz = _to_float(row.get("wz"))
        if x is None or y is None or vx is None or vy is None or vz is None or wz is None:
            continue
        out["t"].append(ts)
        out["x"].append(x)
        out["y"].append(y)
        out["vx"].append(vx)
        out["vy"].append(vy)
        out["vz"].append(vz)
        out["wz"].append(wz)
    if len(out["t"]) < 2:
        return None
    return out


def _load_gnss_xy(run: Path, csv_name: str) -> Optional[Dict[str, List[float]]]:
    p = run / csv_name
    if not p.exists():
        return None
    rows = _read_csv_rows(p)
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
    lat0_deg = lat[0]
    lon0_deg = lon[0]
    lat0_rad = math.radians(lat0_deg)
    x: List[float] = []
    y: List[float] = []
    for la, lo in zip(lat, lon):
        xx, yy = _latlon_to_xy_m(la, lo, lat0_rad, lon0_deg, lat0_deg)
        x.append(xx)
        y.append(yy)
    return {"t": t, "x": x, "y": y}


def _speed_from_xy(t: List[float], x: List[float], y: List[float]) -> List[float]:
    if len(t) < 2:
        return []
    v: List[float] = [float("nan")]
    prev_t, prev_x, prev_y = t[0], x[0], y[0]
    for i in range(1, len(t)):
        dt = t[i] - prev_t
        if dt <= 0.0:
            v.append(float("nan"))
        else:
            v.append(math.hypot(x[i] - prev_x, y[i] - prev_y) / dt)
        prev_t, prev_x, prev_y = t[i], x[i], y[i]
    return v


def _global_t0(series: List[Series]) -> float:
    t0 = None
    for s in series:
        if not s.t_sec:
            continue
        mn = min(s.t_sec)
        t0 = mn if t0 is None else min(t0, mn)
    return 0.0 if t0 is None else float(t0)


def _is_angular_rate_level_1_3(run_name: str) -> bool:
    # Match e.g. "..._angular_rate_level_1_..." and ignore level 4+
    return ("angular_rate_level_1" in run_name) or ("angular_rate_level_2" in run_name) or ("angular_rate_level_3" in run_name)


def _rotate_translate_odom_to_gnss(
    odom_x: List[float],
    odom_y: List[float],
    gnss_x: List[float],
    gnss_y: List[float],
) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    Wheel odom is in a local frame; rotate + translate it so overlays are visually comparable.
    Heuristic: align the start->end direction of odom with start->end direction of GNSS.
    """
    od = np.column_stack([np.asarray(odom_x, dtype=float), np.asarray(odom_y, dtype=float)])
    gn = np.column_stack([np.asarray(gnss_x, dtype=float), np.asarray(gnss_y, dtype=float)])

    od0 = od[0].copy()
    gn0 = gn[0].copy()
    od_rel = od - od0

    v_od = od_rel[-1] - od_rel[0]
    v_gn = gn[-1] - gn[0]
    ang_od = float(math.atan2(v_od[1], v_od[0])) if float(np.hypot(v_od[0], v_od[1])) > 1e-9 else 0.0
    ang_gn = float(math.atan2(v_gn[1], v_gn[0])) if float(np.hypot(v_gn[0], v_gn[1])) > 1e-9 else 0.0
    dtheta = ang_gn - ang_od

    c = math.cos(dtheta)
    s = math.sin(dtheta)
    R = np.array([[c, -s], [s, c]], dtype=float)
    od_rot = (R @ od_rel.T).T
    od_aligned = od_rot + gn0
    return od_aligned[:, 0], od_aligned[:, 1], dtheta


def _circle_fit_radius(x: List[float], y: List[float]) -> Optional[float]:
    """
    Algebraic least squares circle fit:
      x^2 + y^2 = 2*a*x + 2*b*y + c
    """
    if len(x) < 6:
        return None
    xx = np.asarray(x, dtype=float)
    yy = np.asarray(y, dtype=float)
    A = np.column_stack([2.0 * xx, 2.0 * yy, np.ones_like(xx)])
    b = xx * xx + yy * yy
    try:
        sol, *_ = np.linalg.lstsq(A, b, rcond=None)
        a, b2, c = float(sol[0]), float(sol[1]), float(sol[2])
        r2 = a * a + b2 * b2 + c
        if not np.isfinite(r2) or r2 <= 0.0:
            return None
        return float(math.sqrt(r2))
    except Exception:
        return None


def _save_fig(fig: plt.Figure, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _plot_motion_and_paths(run: Path, outdir: Optional[Path], save_png: bool) -> List[Path]:
    """
    Returns list of written output paths.
    """
    written: List[Path] = []

    cmd = _load_cmd_twist(run)
    gnss_rtk = _load_gnss_xy(run, "gnss_f9p_helical_fix.csv")
    gnss_gps = _load_gnss_xy(run, "gnss_pixhawk_navsatfix.csv")
    odom = _load_wheel_odom(run)

    if cmd is None and gnss_rtk is None and gnss_gps is None and odom is None:
        return written

    # ------------------ Figure 1: speeds ------------------
    series_cmd: List[Series] = []
    if cmd is not None:
        t = cmd["t"]
        vmag = [math.sqrt(x * x + y * y + z * z) for x, y, z in zip(cmd["lin_x"], cmd["lin_y"], cmd["lin_z"])]
        series_cmd.append(Series(name="cmd |v| [m/s]", t_sec=t, y=vmag))
        series_cmd.append(Series(name="cmd lin_x [m/s]", t_sec=t, y=cmd["lin_x"]))

    series_meas: List[Series] = []
    if cmd is not None:
        t = cmd["t"]
        vmag = [math.sqrt(x * x + y * y + z * z) for x, y, z in zip(cmd["lin_x"], cmd["lin_y"], cmd["lin_z"])]
        series_meas.append(Series(name="cmd |v| [m/s]", t_sec=t, y=vmag))
    if gnss_gps is not None:
        series_meas.append(
            Series(
                name="GNSS speed (Pixhawk GPS) [m/s]",
                t_sec=gnss_gps["t"],
                y=_speed_from_xy(gnss_gps["t"], gnss_gps["x"], gnss_gps["y"]),
            )
        )
    if gnss_rtk is not None:
        series_meas.append(
            Series(
                name="GNSS speed (F9P RTK) [m/s]",
                t_sec=gnss_rtk["t"],
                y=_speed_from_xy(gnss_rtk["t"], gnss_rtk["x"], gnss_rtk["y"]),
            )
        )
    if odom is not None:
        v_odom = [math.sqrt(vx * vx + vy * vy + vz * vz) for vx, vy, vz in zip(odom["vx"], odom["vy"], odom["vz"])]
        series_meas.append(Series(name="wheel odom speed [m/s]", t_sec=odom["t"], y=v_odom))

    all_series = [*series_cmd, *series_meas]
    t0 = _global_t0(all_series) if all_series else 0.0

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True, layout="constrained")
    for s in series_cmd:
        t_rel = [tt - t0 for tt in s.t_sec]
        ax1.plot(t_rel, s.y, lw=1.2, label=s.name)
    ax1.set_title(f"Motion | {run.name}")
    ax1.set_ylabel("cmd_vel [m/s]")
    ax1.grid(True, alpha=0.25)
    ax1.legend(loc="upper left", frameon=False)

    for s in series_meas:
        t_rel = [tt - t0 for tt in s.t_sec]
        ax2.plot(t_rel, s.y, lw=1.2, label=s.name)
    ax2.set_xlabel("Time [s] (shared, relative)")
    ax2.set_ylabel("Speed [m/s]")
    ax2.grid(True, alpha=0.25)
    ax2.legend(loc="upper left", frameon=False)

    if save_png:
        assert outdir is not None
        out_motion = outdir / f"{run.name}__motion.png"
        _save_fig(fig, out_motion)
        written.append(out_motion)

    # ------------------ Figure 2: XY overlay ------------------
    gnss_anchor = gnss_rtk or gnss_gps
    if gnss_anchor is not None:
        fig2, ax = plt.subplots(figsize=(8, 8), layout="constrained")
        gps_label = "GPS (Pixhawk)"
        rtk_label = "GPS-RTK (F9P)"

        # Show per-sensor measured radius (circle fit) next to each sensor label.
        if _is_angular_rate_level_1_3(run.name):
            if gnss_gps is not None:
                r_gps = _circle_fit_radius(gnss_gps["x"], gnss_gps["y"])
                if r_gps is not None:
                    gps_label = f"{gps_label} (r_meas≈{r_gps:.2f}m)"
            if gnss_rtk is not None:
                r_rtk = _circle_fit_radius(gnss_rtk["x"], gnss_rtk["y"])
                if r_rtk is not None:
                    rtk_label = f"{rtk_label} (r_meas≈{r_rtk:.2f}m)"

        if gnss_gps is not None:
            ax.plot(gnss_gps["x"], gnss_gps["y"], lw=1.2, label=gps_label)
        if gnss_rtk is not None:
            ax.plot(gnss_rtk["x"], gnss_rtk["y"], lw=1.2, label=rtk_label)
        if odom is not None:
            odom_x_al, odom_y_al, _ = _rotate_translate_odom_to_gnss(
                odom["x"], odom["y"], gnss_anchor["x"], gnss_anchor["y"]
            )
            odom_label = "wheel odom"
            if _is_angular_rate_level_1_3(run.name):
                r_meas = _circle_fit_radius(list(odom_x_al), list(odom_y_al))
                if r_meas is not None:
                    odom_label = f"wheel odom (r_meas≈{r_meas:.2f}m)"
            ax.plot(odom_x_al, odom_y_al, lw=1.2, label=odom_label)

        ax.set_title(f"XY path overlay | {run.name}")
        ax.set_xlabel("X [m]")
        ax.set_ylabel("Y [m]")
        ax.set_aspect("equal", adjustable="box")
        ax.grid(True, alpha=0.25)
        ax.legend(loc="upper left", frameon=False)

        if save_png:
            assert outdir is not None
            out_xy = outdir / f"{run.name}__xy_overlay.png"
            _save_fig(fig2, out_xy)
            written.append(out_xy)

    # ------------------ Figure 3: angular_rate-only radius verification ------------------
    if _is_angular_rate_level_1_3(run.name) and cmd is not None:
        t = np.asarray(cmd["t"], dtype=float)
        vxy = np.sqrt(np.asarray(cmd["lin_x"], dtype=float) ** 2 + np.asarray(cmd["lin_y"], dtype=float) ** 2)
        wz = np.asarray(cmd["ang_z"], dtype=float)
        eps = 1e-4
        ok = np.isfinite(t) & np.isfinite(vxy) & np.isfinite(wz) & (np.abs(wz) > eps)
        if int(np.count_nonzero(ok)) >= 2:
            t_rel = (t - t0)[ok]
            r_cmd = (vxy[ok] / np.abs(wz[ok])).astype(float)

            r_meas = None
            if odom is not None and gnss_anchor is not None:
                odom_x_al, odom_y_al, _ = _rotate_translate_odom_to_gnss(
                    odom["x"], odom["y"], gnss_anchor["x"], gnss_anchor["y"]
                )
                r_meas = _circle_fit_radius(list(odom_x_al), list(odom_y_al))

            # Per-sensor radii (circle fit)
            r_gps = _circle_fit_radius(gnss_gps["x"], gnss_gps["y"]) if gnss_gps is not None else None
            r_rtk = _circle_fit_radius(gnss_rtk["x"], gnss_rtk["y"]) if gnss_rtk is not None else None

            fig3, ax = plt.subplots(figsize=(12, 5), layout="constrained")
            ax.plot(t_rel, r_cmd, lw=1.2, label="r_cmd(t)=v_xy/|wz|")
            if r_gps is not None:
                ax.axhline(r_gps, lw=1.0, linestyle="--", label=f"r_meas≈{r_gps:.2f}m (GPS)")
            if r_rtk is not None:
                ax.axhline(r_rtk, lw=1.0, linestyle="--", label=f"r_meas≈{r_rtk:.2f}m (GPS-RTK)")
            if r_meas is not None:
                ax.axhline(r_meas, lw=1.0, linestyle="--", label=f"r_meas≈{r_meas:.2f}m (wheel odom fit)")
            ax.set_title(f"Circular-path verification (angular_rate) | {run.name}")
            ax.set_xlabel("Time [s] (relative)")
            ax.set_ylabel("Radius [m]")
            ax.grid(True, alpha=0.25)
            ax.legend(loc="upper left", frameon=False)

            if save_png:
                assert outdir is not None
                out_r = outdir / f"{run.name}__angular_rate_radius.png"
                _save_fig(fig3, out_r)
                written.append(out_r)

    return written


def main() -> int:
    ap = argparse.ArgumentParser(description="Motion/GNSS/wheel-odom plotter (multi-figure per run).")
    ap.add_argument("--run",    required=True,       help="Run folder (human_csv/<run>.bag/)")
    ap.add_argument("--png",    action="store_true", help="Save PNGs instead of showing an interactive window (headless-friendly).",)
    ap.add_argument("--outdir", default=None,        help="Output directory for PNGs (implies --png). Filenames are derived from run name.",)
    args = ap.parse_args()

    # check folder exists
    run = Path(args.run)
    if not run.exists() or not run.is_dir():
        raise SystemExit(f"Run folder not found: {run}")

    # prepare outdir
    save_png = bool(args.png or args.outdir)
    outdir: Optional[Path] = None
    if save_png:
        outdir = Path(args.outdir) if args.outdir else run
        outdir.mkdir(parents=True, exist_ok=True)

    # plot
    written = _plot_motion_and_paths(run, outdir=outdir, save_png=save_png)

    # If we couldn't even build the plots (no usable data), fail in both modes.
    if save_png:
        if not written:
            raise SystemExit(f"No usable data series found in: {run}")
        for p in written:
            print(f"[OK] Saved: {p}")
    else:
        # Interactive mode: figures were created but not saved/closed.
        plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
