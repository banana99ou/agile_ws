#!/usr/bin/env python3
"""
Plot angular-rate limit test results from `angular_rate_limit_tester.py`.

Input CSV columns:
  ts_sec, phase_idx, phase_wz_cmd, cmd_wz, imu_gyro_z, wheel_odom_wz

Outputs:
- Interactive matplotlib window (default)
- Optional PNG saving via --out (for convenience)
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def _safe_median(x: np.ndarray) -> float:
    x = x[np.isfinite(x)]
    if x.size == 0:
        return float("nan")
    return float(np.median(x))


def _safe_p10_p90(x: np.ndarray) -> tuple[float, float]:
    x = x[np.isfinite(x)]
    if x.size == 0:
        return float("nan"), float("nan")
    return float(np.percentile(x, 10)), float(np.percentile(x, 90))


def main() -> int:
    ap = argparse.ArgumentParser(description="Plot angular-rate limit tester CSV.")
    ap.add_argument("--csv", required=True, help="Path to angular_rate_limit_test.csv")
    ap.add_argument("--out", default=None, help="Optional output PNG path (if provided, saves instead of showing).")
    args = ap.parse_args()

    p = Path(args.csv)
    if not p.exists():
        raise SystemExit(f"CSV not found: {p}")

    df = pd.read_csv(p)
    required = {"ts_sec", "phase_idx", "phase_wz_cmd", "cmd_wz", "imu_gyro_z", "wheel_odom_wz"}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"Missing columns in CSV: {sorted(missing)}")

    # Timebase
    t = df["ts_sec"].to_numpy(dtype=float)
    t0 = float(np.nanmin(t))
    t_rel = t - t0

    cmd = df["cmd_wz"].to_numpy(dtype=float)
    imu = df["imu_gyro_z"].to_numpy(dtype=float)
    odom = df["wheel_odom_wz"].to_numpy(dtype=float)
    phase_idx = df["phase_idx"].to_numpy(dtype=int)
    phase_cmd = df["phase_wz_cmd"].to_numpy(dtype=float)

    # Use magnitude for tracking (sign can vary depending on convention / direction)
    cmd_abs = np.abs(cmd)
    imu_abs = np.abs(imu)
    odom_abs = np.abs(odom)

    # Phase summary stats
    phases = np.unique(phase_idx)
    cmd_levels: list[float] = []
    imu_med: list[float] = []
    imu_p10: list[float] = []
    imu_p90: list[float] = []
    odom_med: list[float] = []
    odom_p10: list[float] = []
    odom_p90: list[float] = []

    for ph in phases:
        m = phase_idx == ph
        cmd_level = float(np.nanmedian(np.abs(phase_cmd[m])))  # constant per phase
        cmd_levels.append(cmd_level)

        imu_m = imu_abs[m]
        odom_m = odom_abs[m]
        imu_med.append(_safe_median(imu_m))
        odom_med.append(_safe_median(odom_m))
        p10, p90 = _safe_p10_p90(imu_m)
        imu_p10.append(p10)
        imu_p90.append(p90)
        p10, p90 = _safe_p10_p90(odom_m)
        odom_p10.append(p10)
        odom_p90.append(p90)

    cmd_levels_np = np.asarray(cmd_levels, dtype=float)
    imu_med_np = np.asarray(imu_med, dtype=float)
    odom_med_np = np.asarray(odom_med, dtype=float)

    # Tracking ratios (median)
    eps = 1e-6
    imu_ratio = imu_med_np / np.maximum(cmd_levels_np, eps)
    odom_ratio = odom_med_np / np.maximum(cmd_levels_np, eps)

    fig = plt.figure(figsize=(13, 9), layout="constrained")
    gs = fig.add_gridspec(3, 1, height_ratios=[2.2, 1.3, 1.5])
    ax_ts = fig.add_subplot(gs[0, 0])
    ax_sum = fig.add_subplot(gs[1, 0])
    ax_ratio = fig.add_subplot(gs[2, 0])

    # ---------------- Time series ----------------
    ax_ts.plot(t_rel, cmd, lw=1.2, label="cmd_wz (published)")
    ax_ts.plot(t_rel, imu, lw=1.1, label="imu gyro_z")
    ax_ts.plot(t_rel, odom, lw=1.1, label="wheel_odom wz")
    ax_ts.set_title(f"Angular-rate limit test | {p.name}")
    ax_ts.set_ylabel("Angular rate [rad/s]")
    ax_ts.grid(True, alpha=0.25)
    ax_ts.legend(loc="upper left", frameon=False)

    # Draw phase boundaries
    # Identify boundary indices where phase changes
    change = np.nonzero(np.diff(phase_idx) != 0)[0]
    for idx in change:
        ax_ts.axvline(t_rel[idx], color="0.85", lw=1.0)

    # ---------------- Summary: measured vs commanded ----------------
    ax_sum.plot(cmd_levels_np, cmd_levels_np, color="0.6", lw=1.0, linestyle="--", label="y=x")
    ax_sum.errorbar(
        cmd_levels_np,
        imu_med_np,
        yerr=[imu_med_np - np.asarray(imu_p10), np.asarray(imu_p90) - imu_med_np],
        fmt="o-",
        lw=1.2,
        capsize=3,
        label="IMU |gyro_z| (median, p10–p90)",
    )
    ax_sum.errorbar(
        cmd_levels_np,
        odom_med_np,
        yerr=[odom_med_np - np.asarray(odom_p10), np.asarray(odom_p90) - odom_med_np],
        fmt="s-",
        lw=1.2,
        capsize=3,
        label="Odom |wz| (median, p10–p90)",
    )
    ax_sum.set_xlabel("Commanded |wz| [rad/s]")
    ax_sum.set_ylabel("Measured |wz| [rad/s]")
    ax_sum.grid(True, alpha=0.25)
    ax_sum.legend(loc="upper left", frameon=False)

    # ---------------- Ratio plot ----------------
    ax_ratio.plot(cmd_levels_np, imu_ratio, "o-", lw=1.2, label="IMU median(|wz|)/cmd")
    ax_ratio.plot(cmd_levels_np, odom_ratio, "s-", lw=1.2, label="Odom median(|wz|)/cmd")
    ax_ratio.axhline(1.0, color="0.6", lw=1.0, linestyle="--")
    ax_ratio.set_xlabel("Commanded |wz| [rad/s]")
    ax_ratio.set_ylabel("Tracking ratio")
    ax_ratio.set_ylim(0.0, max(1.2, float(np.nanmax([imu_ratio, odom_ratio])) * 1.05 if np.isfinite(np.nanmax([imu_ratio, odom_ratio])) else 1.2))
    ax_ratio.grid(True, alpha=0.25)
    ax_ratio.legend(loc="upper left", frameon=False)

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"[OK] Saved: {out}")
    else:
        plt.show()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


