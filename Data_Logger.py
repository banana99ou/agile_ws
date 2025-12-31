#!/usr/bin/env python3

"""
ROS 2 bag recorder wrapper with a health/recording indicator.

Behavior:
- Starts `ros2 bag record` for a fixed topic list.
- Publishes a recording indicator + heartbeat so other tools can confirm recording is active.

Notes:
- This script is intended to be started/stopped by an orchestrator (e.g. run_scenarios_from_files.py).
- Stopping is done via SIGINT (Ctrl+C semantics) so we can rename the bag folder with the actual duration.
"""

import argparse
import os
import signal
import subprocess
import sys
import time
from datetime import datetime

import rclpy  # pyright: ignore[reportMissingImports]
from rclpy.node import Node  # pyright: ignore[reportMissingImports]

from std_msgs.msg import Bool, String  # pyright: ignore[reportMissingImports]


TOPICS = [
    "/gps_rtk_f9p_helical/gps/fix",
    "/gps_rtk_f9p_helical/gps/nmea",
    "/gps_rtk_f9p_helical/gps/rtk_status",
    "/pixhawk/global_position/raw/satellites",
    "/pixhawk/global_position/raw/fix",
    "/cmd_vel",
    "/cmd_vel_raw",
    "/imu",
    "/estop"
]


def build_bag_name(scenario: str, duration_label: str) -> str:
    """
    Build bag name: YY_MMDD_HHMM_<scenario>_<duration>.bag
    Duration will be replaced at the end with the measured runtime.
    """
    stamp = datetime.now().strftime("%y_%m%d_%H%M")
    return f"{stamp}_{scenario}_{duration_label}.bag"


class DataLoggerHealthNode(Node):
    def __init__(self, scenario: str):
        super().__init__("data_logger_health")
        self._scenario = scenario

        self._pub_recording = self.create_publisher(Bool, "/data_logger/recording", 10)
        self._pub_health = self.create_publisher(String, "/data_logger/health", 10)

        # Publish at 2 Hz while alive
        self._timer = self.create_timer(0.5, self._tick)

        self.recording_active = False
        self.bag_path = ""
        self.ros2_bag_pid = -1
        self.soft_stop_received = False

        self.create_subscription(Bool, "/scenario_runner/soft_stop", self._on_soft_stop, 10)

    def _on_soft_stop(self, msg: Bool):
        if msg.data:
            self.soft_stop_received = True
            self.get_logger().info("Soft stop received; bag will be marked with _SOFTSTOP")

    def _tick(self):
        # Publish recording flag
        rec = Bool()
        rec.data = bool(self.recording_active)
        self._pub_recording.publish(rec)

        # Publish health string (human readable)
        msg = String()
        msg.data = (
            f"recording={1 if self.recording_active else 0} "
            f"scenario={self._scenario} "
            f"pid={self.ros2_bag_pid} "
            f"bag_path={self.bag_path}"
        )
        self._pub_health.publish(msg)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Record a ROS 2 bag for a given scenario.\n"
            "File is initially created with a placeholder duration and renamed "
            "on Ctrl+C based on the actual recording time (in seconds)."
        )
    )
    parser.add_argument(
        "scenario",
        help="Scenario name to embed in the bag filename (e.g. 'slalom', 'rally_1').",
    )
    args = parser.parse_args(argv)

    scenario = args.scenario
    placeholder_duration = "DURATION_PLACEHOLDER"
    bag_name = build_bag_name(scenario, placeholder_duration)

    # Ensure output base directory exists: "./Experiment Data/"
    base_dir = os.path.join(os.getcwd(), "Experiment Data")
    os.makedirs(base_dir, exist_ok=True)
    bag_path = os.path.join(base_dir, bag_name)

    # ros2 bag record (ROS 2) actually creates a directory named <bag_name>
    # (even if it ends with .bag), not a single file. We still follow your
    # requested naming scheme and later rename that directory.
    cmd = [
        "ros2",
        "bag",
        "record",
        "-o",
        bag_path,
        *TOPICS,
    ]

    print(f"Recording ROS 2 bag to: {bag_path}")
    print("Press Ctrl+C to stop; the bag will then be renamed with the actual duration.")

    start_monotonic = time.monotonic()

    # Start ROS node for health publishing
    rclpy.init(args=None)
    node = DataLoggerHealthNode(scenario=scenario)
    node.recording_active = False
    node.bag_path = bag_path

    try:
        proc = subprocess.Popen(cmd)
    except FileNotFoundError:
        print("Error: 'ros2' command not found. Make sure your ROS 2 environment is sourced.", file=sys.stderr)
        node.destroy_node()
        rclpy.shutdown()
        return 1
    except Exception as e:
        print(f"Error: failed to start ros2 bag record: {e}", file=sys.stderr)
        node.destroy_node()
        rclpy.shutdown()
        return 1

    node.ros2_bag_pid = proc.pid or -1
    node.recording_active = True
    print(f"DATA_LOGGER_STARTED ros2_bag_pid={node.ros2_bag_pid}")

    end_monotonic = None
    try:
        # Spin the health node while ros2 bag record runs.
        while rclpy.ok() and proc.poll() is None:
            rclpy.spin_once(node, timeout_sec=0.2)
        end_monotonic = time.monotonic()
    except KeyboardInterrupt:
        # Stop request (Ctrl+C or orchestrator SIGINT)
        print("\nStopping ros2 bag recording...")
        try:
            proc.send_signal(signal.SIGINT)
        except Exception:
            pass
        try:
            proc.wait(timeout=10.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        end_monotonic = time.monotonic()
    finally:
        node.recording_active = False
        try:
            # Final publish
            node._tick()
        except Exception:
            pass
        node.destroy_node()
        rclpy.shutdown()

    if end_monotonic is None:
        end_monotonic = time.monotonic()

    duration_s = max(0, int(end_monotonic - start_monotonic))
    duration_label = f"{duration_s}s"
    if node.soft_stop_received:
        duration_label += "_SOFTSTOP"
    final_bag_name = build_bag_name(scenario, duration_label)
    final_bag_path = os.path.join(base_dir, final_bag_name)

    # Rename the output directory (or file, depending on future ros2 behaviors)
    try:
        if os.path.exists(bag_path):
            os.rename(bag_path, final_bag_path)
            print(f"Renamed bag from '{bag_path}' to '{final_bag_path}'")
        else:
            print(
                f"Warning: expected output '{bag_path}' does not exist; "
                f"cannot rename to '{final_bag_path}'.",
                file=sys.stderr,
            )
    except OSError as e:
        print(f"Error renaming bag: {e}", file=sys.stderr)
        return 1

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())