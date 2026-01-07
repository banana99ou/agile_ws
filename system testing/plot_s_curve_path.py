#!/usr/bin/env python3
"""
Pure-math S-curve candidate plotter.

Plots the original reference curve and three "resized" candidates inside a
50m x 12m testing-site rectangle (default: centered at (0,0) => x∈[-25,25], y∈[-6,6]).

Original (reference):
  x(t) = 20 sin(0.2 t)
  y(t) = 10 sin(0.4 t)
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import matplotlib.pyplot as plt


@dataclass(frozen=True)
class CurveSpec:
    name: str
    ax: float
    wx: float
    ay: float
    wy: float
    phix: float = 0.0
    phiy: float = 0.0

    def eval(self, t: np.ndarray, x0: float = 0.0, y0: float = 0.0) -> Tuple[np.ndarray, np.ndarray]:
        x = x0 + self.ax * np.sin(self.wx * t + self.phix)
        y = y0 + self.ay * np.sin(self.wy * t + self.phiy)
        return x, y


def _site_rect(centered: bool) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """
    Returns ((xmin, xmax), (ymin, ymax)) for a 50x12 rectangle.
    """
    if centered:
        return (-25.0, 25.0), (-6.0, 6.0)
    return (0.0, 50.0), (-6.0, 6.0)

def _uniform_scale_to_fit(
    ax: float,
    ay: float,
    x_half_span: float,
    y_half_span: float,
    margin_x: float,
    margin_y: float,
) -> float:
    """
    Compute a uniform scale factor s so that:
      |s*ax| <= x_half_span - margin_x
      |s*ay| <= y_half_span - margin_y
    """
    if x_half_span <= margin_x or y_half_span <= margin_y:
        raise ValueError("Margins are too large for the site rectangle.")
    sx = (x_half_span - margin_x) / float(abs(ax))
    sy = (y_half_span - margin_y) / float(abs(ay))
    return float(min(sx, sy))


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Plot S-curve candidates inside a 50m x 12m rectangle.")
    p.add_argument(
        "--centered",
        action="store_true",
        help="Center the 50x12 rectangle at (0,0) (x∈[-25,25]). Default is x∈[0,50] with the curves shifted by +25m.",
    )
    p.add_argument(
        "--out",
        type=str,
        default=str(Path("_tmp_no_debug") / "s_curve_candidates_site.png"),
        help="Output image path (PNG).",
    )
    p.add_argument(
        "--dpi",
        type=int,
        default=160,
        help="Output DPI when saving the figure.",
    )
    p.add_argument(
        "--margin-x",
        type=float,
        default=0.5,
        help="Horizontal margin to keep inside the rectangle (meters).",
    )
    p.add_argument(
        "--margin-y",
        type=float,
        default=0.5,
        help="Vertical margin to keep inside the rectangle (meters).",
    )
    args = p.parse_args(argv)

    # Reference curve (too tall for 12m height, but included for comparison).
    original = CurveSpec(name="original: 20sin(0.2t), 10sin(0.4t)", ax=20.0, wx=0.2, ay=10.0, wy=0.4)

    centered = bool(args.centered)
    (xmin, xmax), (ymin, ymax) = _site_rect(centered=centered)
    x_half_span = 0.5 * (xmax - xmin)
    y_half_span = 0.5 * (ymax - ymin)

    # Uniformly scaled version of the original (preserves shape, only shrinks).
    # This is the mathematically correct "same shape, fits in rectangle with margin" option.
    s = _uniform_scale_to_fit(
        ax=original.ax,
        ay=original.ay,
        x_half_span=x_half_span,
        y_half_span=y_half_span,
        margin_x=float(args.margin_x),
        margin_y=float(args.margin_y),
    )
    scaled = CurveSpec(
        name=f"scaled(original) x={original.ax*s:.2f}sin(0.2t), y={original.ay*s:.2f}sin(0.4t) (s={s:.3f})",
        ax=original.ax * s,
        wx=original.wx,
        ay=original.ay * s,
        wy=original.wy,
    )

    # Additional alternative candidates (still bounded, but not strictly a uniform scale).
    # Keep them for optional comparison.
    candidates = [
        scaled,
        CurveSpec(name="alt1: 25sin(0.2t), 5.5sin(0.3t)", ax=25.0, wx=0.2, ay=5.5, wy=0.3),
        CurveSpec(
            name="alt2: 25sin(0.2t), 5.5sin(0.4t + π/4)",
            ax=25.0,
            wx=0.2,
            ay=5.5,
            wy=0.4,
            phiy=float(np.pi / 4),
        ),
    ]

    # Use a time window long enough to show closed patterns for all candidates.
    # For wx=0.2 and wy=0.3 => ratio 2:3, common period is 20π.
    t = np.linspace(0.0, float(20.0 * np.pi), 6000)

    x0 = 0.0 if centered else 25.0  # shift to [0, 50] if not centered
    y0 = 0.0

    fig, ax = plt.subplots(figsize=(11, 4.2))

    # Site boundary
    ax.add_patch(
        plt.Rectangle(
            (xmin, ymin),
            xmax - xmin,
            ymax - ymin,
            fill=False,
            linewidth=2.0,
            linestyle="-",
            color="black",
            label="testing site: 50m x 12m",
        )
    )

    # Curves
    x, y = original.eval(t, x0=x0, y0=y0)
    ax.plot(x, y, linewidth=2.0, alpha=0.45, label=original.name)

    for spec in candidates:
        x, y = spec.eval(t, x0=x0, y0=y0)
        ax.plot(x, y, linewidth=2.0, label=spec.name)

    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(xmin - 2.0, xmax + 2.0)
    ax.set_ylim(ymin - 1.0, ymax + 1.0)
    ax.grid(True, linestyle="--", linewidth=0.7, alpha=0.5)
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.set_title("S-curve candidates (pure math) inside 50m x 12m boundary")
    ax.legend(loc="upper right", fontsize=9, framealpha=0.9)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=int(args.dpi))
    print(f"saved: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

