#!/usr/bin/env python3
"""
Client-view GNSS result plotter.

Consumes the *existing* GNSS fix metric CSVs (no per-sample timelines required):
  - run_gnss_fix_metrics_summary.csv
  - run_gnss_fix_segments.csv
  - run_gnss_refix_intervals.csv

and produces a single PNG:
  - gnss_fix_timeline.png

The plot shows:
  - sustained desired-fix segments as horizontal bars (one lane per receiver)
  - refix gaps (loss -> refix) as a shaded region
  - TTFF marker (first sustained fix)
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def _to_float(x: Optional[str]) -> Optional[float]:
    if x is None:
        return None
    s = str(x).strip()
    if s == "" or s.lower() == "nan":
        return None
    try:
        return float(s)
    except Exception:
        return None


def _read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", newline="") as f:
        return list(csv.DictReader(f))


@dataclass(frozen=True)
class ReceiverSummary:
    receiver: str
    desired_flag: str
    sustain_s: float
    first_ts: Optional[float]
    last_ts: Optional[float]
    time_to_first_fix_s: Optional[float]
    first_fix_ts: Optional[float]


def _load_summaries(run_dir: Path, prefix: str) -> Dict[str, ReceiverSummary]:
    p = run_dir / f"{prefix}gnss_fix_metrics_summary.csv"
    rows = _read_csv(p)
    out: Dict[str, ReceiverSummary] = {}
    for r in rows:
        rx = str(r.get("receiver") or "").strip()
        if not rx:
            continue
        out[rx] = ReceiverSummary(
            receiver=rx,
            desired_flag=str(r.get("desired_flag") or "").strip(),
            sustain_s=_to_float(r.get("sustain_s")) or 0.0,
            first_ts=_to_float(r.get("first_ts")),
            last_ts=_to_float(r.get("last_ts")),
            time_to_first_fix_s=_to_float(r.get("time_to_first_fix_s")),
            first_fix_ts=_to_float(r.get("first_fix_ts")),
        )
    return out


def _load_segments(run_dir: Path, prefix: str) -> Dict[str, List[Tuple[float, float]]]:
    """
    Returns {receiver: [(start_ts, end_ts), ...]}.
    """
    p = run_dir / f"{prefix}gnss_fix_segments.csv"
    rows = _read_csv(p)
    out: Dict[str, List[Tuple[float, float]]] = {}
    for r in rows:
        rx = str(r.get("receiver") or "").strip()
        st = _to_float(r.get("start_ts"))
        en = _to_float(r.get("end_ts"))
        if not rx or st is None or en is None:
            continue
        out.setdefault(rx, []).append((float(st), float(en)))
    # sort
    for rx in list(out.keys()):
        out[rx] = sorted(out[rx], key=lambda t: t[0])
    return out


def _load_refix_gaps(run_dir: Path, prefix: str) -> Dict[str, List[Tuple[float, float]]]:
    """
    Returns {receiver: [(loss_end_ts, refix_start_ts), ...]}.
    """
    p = run_dir / f"{prefix}gnss_refix_intervals.csv"
    if not p.exists():
        return {}
    rows = _read_csv(p)
    out: Dict[str, List[Tuple[float, float]]] = {}
    for r in rows:
        rx = str(r.get("receiver") or "").strip()
        loss_end = _to_float(r.get("loss_end_ts"))
        refix_start = _to_float(r.get("refix_start_ts"))
        if not rx or loss_end is None or refix_start is None:
            continue
        out.setdefault(rx, []).append((float(loss_end), float(refix_start)))
    for rx in list(out.keys()):
        out[rx] = sorted(out[rx], key=lambda t: t[0])
    return out


def _format_kst_hms_from_epoch_s(epoch_s: float) -> str:
    # KST is UTC+9, no DST.
    tz = _dt.timezone(_dt.timedelta(hours=9))
    dt = _dt.datetime.fromtimestamp(float(epoch_s), tz=tz)
    return dt.strftime("%H:%M:%S")


def write_gnss_fix_timeline_png(
    run_dir: Path,
    prefix: str,
    out_path: Optional[Path] = None,
    bag_start_epoch_s: Optional[float] = None,
) -> Path:
    # Import matplotlib lazily so non-plot users can still run the pipeline.
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    summaries = _load_summaries(run_dir, prefix=prefix)
    segments = _load_segments(run_dir, prefix=prefix)
    refix_gaps = _load_refix_gaps(run_dir, prefix=prefix)

    receivers = sorted(set(summaries.keys()) | set(segments.keys()) | set(refix_gaps.keys()))
    if not receivers:
        raise RuntimeError(f"No receivers found in {run_dir} (prefix='{prefix}')")

    # Determine plot window from summaries when available, else from segment bounds.
    t_min: Optional[float] = None
    t_max: Optional[float] = None
    for s in summaries.values():
        if s.first_ts is not None:
            t_min = s.first_ts if t_min is None else min(t_min, s.first_ts)
        if s.last_ts is not None:
            t_max = s.last_ts if t_max is None else max(t_max, s.last_ts)
    if t_min is None or t_max is None:
        for rx, segs in segments.items():
            for st, en in segs:
                t_min = st if t_min is None else min(t_min, st)
                t_max = en if t_max is None else max(t_max, en)
    if t_min is None or t_max is None:
        t_min, t_max = 0.0, 1.0

    # Layout
    lane_h = 0.8
    lane_gap = 0.35
    fig_h = max(2.5, 0.8 + len(receivers) * (lane_h + lane_gap))
    fig, ax = plt.subplots(figsize=(12, fig_h), layout="constrained")

    # Title: assume one desired_flag across receivers; if mixed, show blank.
    desired_flags = sorted({(summaries[rx].desired_flag or "").strip() for rx in receivers if rx in summaries})
    desired_flag = desired_flags[0] if len(desired_flags) == 1 else ""
    sustain_s_vals = sorted({summaries[rx].sustain_s for rx in receivers if rx in summaries and summaries[rx].sustain_s})
    sustain_s = sustain_s_vals[0] if len(sustain_s_vals) == 1 else None
    title = "GNSS desired-fix timeline"
    if desired_flag:
        title += f" (desired={desired_flag}"
        if sustain_s is not None:
            title += f", sustain={sustain_s:.1f}s"
        title += ")"
    ax.set_title(title)

    # Draw lanes
    y_ticks = []
    y_labels = []
    for i, rx in enumerate(receivers):
        y0 = i * (lane_h + lane_gap)
        y_center = y0 + lane_h / 2.0
        y_ticks.append(y_center)
        y_labels.append(rx)

        # Refix gaps (loss -> refix) shaded
        for loss_end, refix_start in refix_gaps.get(rx, []):
            x0 = max(loss_end, t_min)
            x1 = min(refix_start, t_max)
            if x1 > x0:
                ax.axvspan(x0, x1, ymin=(y0 / (y_ticks[-1] + lane_h)), ymax=((y0 + lane_h) / (y_ticks[-1] + lane_h)), color="#d62728", alpha=0.08)

        # Desired-fix segments bars
        spans: List[Tuple[float, float]] = []
        for st, en in segments.get(rx, []):
            x0 = max(st, t_min)
            x1 = min(en, t_max)
            if x1 <= x0:
                continue
            spans.append((x0, x1 - x0))
        if spans:
            ax.broken_barh(spans, (y0, lane_h), facecolors="#2ca02c", alpha=0.65)

        # TTFF marker (first sustained fix)
        s = summaries.get(rx)
        if s and s.first_fix_ts is not None:
            if t_min <= s.first_fix_ts <= t_max:
                ax.plot([s.first_fix_ts], [y_center], marker="v", markersize=7, color="#1f77b4", label="TTFF" if i == 0 else None)
                # Label TTFF using absolute KST time-of-day if bag_start_epoch_s is provided.
                if bag_start_epoch_s is not None:
                    try:
                        ttff_epoch = float(bag_start_epoch_s) + float(s.first_fix_ts)
                        kst_hms = _format_kst_hms_from_epoch_s(ttff_epoch)
                        ax.text(
                            float(s.first_fix_ts) + 0.15,
                            y_center,
                            f"TTFF {kst_hms} KST",
                            va="center",
                            ha="left",
                            fontsize=9,
                            color="#1f77b4",
                        )
                    except Exception:
                        pass

    ax.set_yticks(y_ticks)
    ax.set_yticklabels(y_labels)
    ax.set_xlabel("Time [s] (run-relative)")
    ax.set_xlim(t_min, t_max)
    ax.grid(True, axis="x", alpha=0.25)

    # Legend (avoid duplicates)
    handles, labels = ax.get_legend_handles_labels()
    if handles and labels:
        ax.legend(loc="upper right", frameon=False)

    out = out_path if out_path else (run_dir / "gnss_fix_timeline.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Plot client-view GNSS desired-fix timeline from run_gnss_fix_* CSVs.")
    ap.add_argument("--run", required=True, help="Run folder containing run_gnss_fix_*.csv (or gnss_fix_*.csv for FTG-only).")
    ap.add_argument("--prefix", default="run_", help="CSV filename prefix (default: run_)")
    ap.add_argument("--out", default=None, help="Output PNG path (default: <run>/gnss_fix_timeline.png)")
    ap.add_argument(
        "--bag-start-epoch-s",
        default=None,
        help="Optional bag start epoch seconds (UTC). If provided, TTFF is labeled as HH:MM:SS KST.",
    )
    args = ap.parse_args(argv)

    run_dir = Path(args.run)
    if not run_dir.exists() or not run_dir.is_dir():
        raise SystemExit(f"Run folder not found: {run_dir}")

    out = Path(args.out) if args.out else None
    try:
        written = write_gnss_fix_timeline_png(
            run_dir,
            prefix=str(args.prefix),
            out_path=out,
            bag_start_epoch_s=_to_float(args.bag_start_epoch_s),
        )
        print(f"[OK] Saved: {written}")
        return 0
    except ImportError as e:
        raise SystemExit(f"Missing dependency for plotting: {e}. Install matplotlib.") from e


if __name__ == "__main__":
    raise SystemExit(main())

