#!/usr/bin/env python3
"""
Angular-rate limit tester for LIMO (tank steering).

What it does:
- Publishes step commands on `cmd_vel_raw` with angular.z spanning a range.
- Subscribes to:
  - `/wheel/odom` for measured wz (twist.twist.angular.z)
  - `/imu` (or `/pixhawk/imu/data`) for measured gyro_z (angular_velocity.z)
- Records time series during each step:
  - cmd_wz, imu_gyro_z, odom_wz

This is intentionally similar in style to `limo_scenario_motion.py`, but does NOT use `Data_Logger.py`.

Example:
  python3 angular_rate_limit_tester.py --min-wz 0.02 --max-wz 1.0 --steps 10 --trial-s 5 --rest-s 2
"""

from __future__ import annotations

import argparse
import csv
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Imu


@dataclass
class Sample:
    ts_sec: float
    phase_idx: int
    phase_wz_cmd: float
    cmd_wz: float
    imu_gyro_z: float
    odom_wz: float


class AngularRateLimitTester(Node):
    def __init__(self, odom_topic: str, imu_topic: str, pub_topic: str):
        super().__init__("angular_rate_limit_tester")

        self.pub = self.create_publisher(Twist, pub_topic, 10)
        self.sub_odom = self.create_subscription(Odometry, odom_topic, self._cb_odom, 50)
        self.sub_imu = self.create_subscription(Imu, imu_topic, self._cb_imu, 50)

        self.last_odom_wz: Optional[float] = None
        self.last_imu_gz: Optional[float] = None

    def _now_sec(self) -> float:
        return float(self.get_clock().now().nanoseconds) * 1e-9

    def _cb_odom(self, msg: Odometry) -> None:
        self.last_odom_wz = float(msg.twist.twist.angular.z)

    def _cb_imu(self, msg: Imu) -> None:
        self.last_imu_gz = float(msg.angular_velocity.z)

    def stop_robot(self) -> None:
        self.pub.publish(Twist())


def _linspace(a: float, b: float, n: int) -> list[float]:
    if n <= 1:
        return [float(a)]
    step = (b - a) / float(n - 1)
    return [float(a + i * step) for i in range(n)]


def _median(xs: list[float]) -> float:
    ys = sorted(xs)
    m = len(ys)
    if m == 0:
        return float("nan")
    if m % 2 == 1:
        return float(ys[m // 2])
    return 0.5 * float(ys[m // 2 - 1] + ys[m // 2])


def main() -> int:
    ap = argparse.ArgumentParser(description="Test angular-rate limit by stepping cmd_vel_raw.angular.z.")
    ap.add_argument("--min-wz", type=float, default=0.02, help="Minimum commanded angular rate (rad/s).")
    ap.add_argument("--max-wz", type=float, default=1.0, help="Maximum commanded angular rate (rad/s).")
    ap.add_argument("--steps", type=int, default=10, help="Number of steps between min and max (inclusive).")
    ap.add_argument("--trial-s", type=float, default=5.0, help="Duration of each step (seconds).")
    ap.add_argument("--rest-s", type=float, default=2.0, help="Rest (zero cmd) between steps (seconds).")
    ap.add_argument("--rate-hz", type=float, default=30.0, help="Publish/log rate (Hz).")
    ap.add_argument("--linear-x", type=float, default=0.0, help="Optional constant linear.x (m/s). 0.0 = spin in place.")
    ap.add_argument("--odom-topic", type=str, default="/wheel/odom", help="Odometry topic.")
    ap.add_argument("--imu-topic", type=str, default="/imu", help="IMU topic (gyro_z from angular_velocity.z).")
    ap.add_argument("--pub-topic", type=str, default="cmd_vel_raw", help="Publish topic for Twist.")
    ap.add_argument(
        "--out",
        type=str,
        default="angular_rate_limit_test.csv",
        help="Output CSV path for time series (created/overwritten).",
    )
    args = ap.parse_args()

    if args.steps < 1:
        raise SystemExit("--steps must be >= 1")
    if args.trial_s <= 0.0:
        raise SystemExit("--trial-s must be > 0")
    if args.rate_hz <= 0.0:
        raise SystemExit("--rate-hz must be > 0")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rclpy.init(args=None)
    node = AngularRateLimitTester(args.odom_topic, args.imu_topic, args.pub_topic)
    logger = node.get_logger()

    try:
        wz_list = _linspace(args.min_wz, args.max_wz, args.steps)
        dt = 1.0 / float(args.rate_hz)

        # Wait briefly for sensors
        logger.info(f"Waiting for topics: odom={args.odom_topic} imu={args.imu_topic}")
        t_wait_end = time.time() + 3.0
        while rclpy.ok() and time.time() < t_wait_end and (node.last_odom_wz is None or node.last_imu_gz is None):
            rclpy.spin_once(node, timeout_sec=0.1)
        if node.last_odom_wz is None:
            logger.warn("No /wheel/odom wz received yet (continuing anyway).")
        if node.last_imu_gz is None:
            logger.warn("No IMU gyro_z received yet (continuing anyway).")

        samples: list[Sample] = []

        logger.info(
            f"Starting angular-rate step test: steps={args.steps}, wz=[{args.min_wz:.3f}..{args.max_wz:.3f}] rad/s, "
            f"trial_s={args.trial_s:.2f}, rest_s={args.rest_s:.2f}, linear_x={args.linear_x:.2f} m/s"
        )

        for i, wz_cmd in enumerate(wz_list):
            # Rest segment (zero cmd)
            if args.rest_s > 0.0:
                logger.info(f"[{i+1}/{len(wz_list)}] Rest {args.rest_s:.1f}s")
                t_end = time.time() + float(args.rest_s)
                while rclpy.ok() and time.time() < t_end:
                    rclpy.spin_once(node, timeout_sec=0.0)
                    node.stop_robot()
                    time.sleep(dt)

            # Step segment
            logger.info(f"[{i+1}/{len(wz_list)}] Step wz_cmd={wz_cmd:.3f} rad/s for {args.trial_s:.1f}s")
            t_end = time.time() + float(args.trial_s)
            while rclpy.ok() and time.time() < t_end:
                rclpy.spin_once(node, timeout_sec=0.0)

                imu_gz = float(node.last_imu_gz) if node.last_imu_gz is not None else float("nan")
                odom_wz = float(node.last_odom_wz) if node.last_odom_wz is not None else float("nan")

                twist = Twist()
                twist.linear.x = float(args.linear_x)
                twist.angular.z = float(wz_cmd)
                node.pub.publish(twist)

                samples.append(
                    Sample(
                        ts_sec=node._now_sec(),
                        phase_idx=i,
                        phase_wz_cmd=float(wz_cmd),
                        cmd_wz=float(wz_cmd),
                        imu_gyro_z=imu_gz,
                        odom_wz=odom_wz,
                    )
                )
                time.sleep(dt)

            # brief stop after each step
            node.stop_robot()

            # Per-step summary (median tracking)
            imu_step = [abs(s.imu_gyro_z) for s in samples if s.phase_idx == i and s.imu_gyro_z == s.imu_gyro_z]
            odom_step = [abs(s.odom_wz) for s in samples if s.phase_idx == i and s.odom_wz == s.odom_wz]
            imu_med = _median(imu_step) if imu_step else float("nan")
            odom_med = _median(odom_step) if odom_step else float("nan")
            imu_ratio = (imu_med / abs(wz_cmd)) if abs(wz_cmd) > 1e-9 and imu_med == imu_med else float("nan")
            odom_ratio = (odom_med / abs(wz_cmd)) if abs(wz_cmd) > 1e-9 and odom_med == odom_med else float("nan")

            logger.info(
                f"[{i+1}/{len(wz_list)}] wz_cmd={wz_cmd:.3f} | imu_med={imu_med:.3f} (ratio={imu_ratio:.2f}) | "
                f"odom_med={odom_med:.3f} (ratio={odom_ratio:.2f})"
            )

        # Write CSV
        with out_path.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["ts_sec", "phase_idx", "phase_wz_cmd", "cmd_wz", "imu_gyro_z", "wheel_odom_wz"])
            for s in samples:
                w.writerow(
                    [
                        f"{s.ts_sec:.9f}",
                        s.phase_idx,
                        f"{s.phase_wz_cmd:.6f}",
                        f"{s.cmd_wz:.6f}",
                        f"{s.imu_gyro_z:.6f}",
                        f"{s.odom_wz:.6f}",
                    ]
                )
        logger.info(f"[OK] Wrote time series CSV: {out_path}")

        return 0
    except KeyboardInterrupt:
        logger.warn("KeyboardInterrupt: stopping robot.")
        return 130
    finally:
        try:
            node.stop_robot()
            node.destroy_node()
        finally:
            rclpy.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())


