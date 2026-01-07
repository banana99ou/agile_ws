#!/usr/bin/env python3
"""
General-purpose CSV plotter for time-series data.
Overlay columns from multiple CSV files (recursively found) with a clickable legend.

Usage:
    python show.py --path /path/to/folder --file imu.csv [--cols accel_x,accel_y,accel_z]

Examples:
    # Compare imu.csv across all bags in human_csv
    python show.py --path human_csv --file imu.csv

    # Compare cmd_vel in a specific bag folder
    python show.py --path human_csv/25_1224_1916_const_vel_497s.bag --file motion_cmd_vel.csv
"""

import pandas as pd
import sys
import matplotlib

# If we are saving to disk (or explicitly disabling UI), force a non-interactive backend.
# This avoids GUI requirements in headless environments and makes runs deterministic.
if ("--out" in sys.argv) or ("--no-show" in sys.argv):
    matplotlib.use("Agg")

import matplotlib.pyplot as plt
from pathlib import Path
import argparse

# ── CONFIGURE ────────────────────────────────────────────────────────────────
FIGSIZE   = (12, 8)
# ─────────────────────────────────────────────────────────────────────────────

def extract_time_series(df: pd.DataFrame) -> pd.Series:
    """
    Return a time Series in *seconds* starting at 0 for the file.
    Tries various common timestamp column names.
    """
    # 1. Preferred standard (already zero-based or seconds since epoch)
    for col in ["t_rel", "ts_sec", "t_sec", "t_s"]:
        if col in df.columns:
            ts = df[col].astype(float)
            return ts - ts.iloc[0]

    # 2. Nanoseconds (ROS2 bag_ts_ns)
    if "bag_ts_ns" in df.columns:
        ts = df["bag_ts_ns"].astype(float) / 1e9
        return ts - ts.iloc[0]

    # 3. Microseconds
    for col in ("t_us", "t_accel_us", "t_color_us"):
        if col in df.columns:
            ts = df[col].astype(float) / 1e6
            return ts - ts.iloc[0]

    # 4. Header stamps
    if "hdr_stamp_sec" in df.columns and "hdr_stamp_nanosec" in df.columns:
        ts = df["hdr_stamp_sec"].astype(float) + df["hdr_stamp_nanosec"].astype(float) / 1e9
        return ts - ts.iloc[0]

    # 5. Fallback: just use index if nothing else found
    print("⚠️  No recognized time column. Using row index as time.")
    return pd.Series(range(len(df))).astype(float)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", "-p", default="human_csv", help="Path to folder or root folder (default: human_csv)")
    parser.add_argument("--file", "-f", help="CSV filename or pattern (default: imu.csv for root, *.csv for leaf)")
    parser.add_argument("--cols", "-c", help="Comma-separated columns to plot (e.g. accel_x,accel_y,accel_z)")
    parser.add_argument("--out", help="Save plot to this file (e.g. plots/imu.png). Implies --no-show.")
    parser.add_argument("--no-show", action="store_true", help="Do not open an interactive window (useful for headless runs).")
    args = parser.parse_args()

    root = Path(args.path)
    if not root.exists():
        print(f"❌ Path does not exist: {root}")
        sys.exit(1)

    # Determine pattern
    if args.file:
        pattern = args.file
    else:
        # If root contains directories, assume it's a collection of runs -> default to imu.csv
        # Otherwise, assume it's a single run folder -> plot all its CSVs
        has_subdirs = any(d.is_dir() for d in root.iterdir()) if root.is_dir() else False
        if has_subdirs:
            pattern = "imu.csv"
            print("💡 Multiple subdirectories found. Defaulting to --file imu.csv to compare runs.")
        else:
            pattern = "*.csv"

    # Find matching CSV files
    if root.is_file():
        csv_files = [root]
    else:
        # Recursive search if it's a directory
        csv_files = sorted(root.rglob(pattern))

    if not csv_files:
        print(f"❌ No files matching '{args.file}' found in {root}")
        sys.exit(1)

    print(f"📂 Found {len(csv_files)} file(s).")

    # Determine which columns to plot from the first valid file
    first_df = None
    valid_csv_files = []
    plot_cols = []

    for f in csv_files:
        try:
            tmp = pd.read_csv(f, nrows=5)
            if tmp.empty: continue
            if first_df is None:
                first_df = tmp
            valid_csv_files.append(f)
        except Exception:
            continue

    if first_df is None:
        print("❌ Could not read any valid CSV files.")
        sys.exit(1)

    if args.cols:
        plot_cols = [c.strip() for c in args.cols.split(",")]
    else:
        # Auto-guess columns based on filename or content
        fname = pattern.lower()
        if "imu" in fname:
            plot_cols = [c for c in ["accel_x", "accel_y", "accel_z", "ax", "ay", "az"] if c in first_df.columns]
        elif "cmd_vel" in fname:
            plot_cols = [c for c in ["lin_x", "lin_y", "lin_z", "ang_z"] if c in first_df.columns]
        else:
            # Numeric columns excluding time/meta keywords
            time_meta = {"ts", "time", "stamp", "crc", "iso", "bag", "hdr", "rel", "sec", "ns", "us", "index", "source", "flag"}
            plot_cols = [c for c in first_df.columns if not any(k in c.lower() for k in time_meta)]
            # Try to filter for numeric-only (re-read a bit more for safety)
            full_first = pd.read_csv(valid_csv_files[0], nrows=100)
            plot_cols = [c for c in plot_cols if pd.api.types.is_numeric_dtype(full_first[c])]
            plot_cols = plot_cols[:4] # limit subplots

    if not plot_cols:
        print(f"⚠️  No columns to plot found in {valid_csv_files[0].name}. Try specifying --cols.")
        sys.exit(1)

    print(f"📊 Plotting columns: {plot_cols}")

    # Prepare subplots
    num_plots = len(plot_cols)
    fig, axes = plt.subplots(
        nrows=num_plots,
        ncols=1,
        sharex=True,
        figsize=FIGSIZE,
        layout="constrained"
    )
    if num_plots == 1:
        axes = [axes]

    run_lines: dict[str, list] = {}

    for csv_path in valid_csv_files:
        try:
            df = pd.read_csv(csv_path)
            time = extract_time_series(df)
            
            # Label strategy: parent_dir/filename
            if csv_path.parent != root:
                label = f"{csv_path.parent.name}/{csv_path.name}"
            else:
                label = csv_path.name
            
            run_lines[label] = []
            for ax, col in zip(axes, plot_cols):
                if col in df.columns:
                    ln, = ax.plot(time, df[col].astype(float), label=label, lw=1.0, alpha=0.8)
                    run_lines[label].append(ln)
        except Exception as e:
            print(f"⚠️  Error plotting {csv_path}: {e}")

    # Cosmetics
    for ax, col in zip(axes, plot_cols):
        ax.set_ylabel(col)
        ax.grid(True, alpha=0.3)
    
    axes[0].set_title(f"Comparison of {args.file} | {len(run_lines)} runs")
    axes[-1].set_xlabel("Time [s]")

    # Legend + Toggle
    handles = [run_lines[name][0] for name in run_lines if run_lines[name]]
    labels  = [name for name in run_lines if run_lines[name]]
    
    if labels:
        leg = axes[0].legend(
            handles, labels,
            loc="upper left", bbox_to_anchor=(1.02, 1.0),
            title="Click legend to toggle", frameon=False
        )

        line_map = {}
        for legline, label in zip(leg.get_lines(), labels):
            legline.set_picker(True)
            legline.set_pickradius(10)
            line_map[legline] = run_lines[label]

        def on_pick(event):
            legline = event.artist
            if legline not in line_map: return
            orig_lines = line_map[legline]
            vis = not orig_lines[0].get_visible()
            for ln in orig_lines:
                ln.set_visible(vis)
            legline.set_alpha(1.0 if vis else 0.2)
            fig.canvas.draw_idle()

        fig.canvas.mpl_connect("pick_event", on_pick)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        print(f"💾 Saved plot to: {out_path}")

    if args.no_show or args.out:
        plt.close(fig)
    else:
        plt.show()

if __name__ == "__main__":
    main()
