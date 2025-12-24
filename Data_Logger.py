#!/usr/bin/env python3

"""
it should also save:
    Estop state
    Event flag from scenario runner
    optional validity
"""

import argparse
import os
import signal
import subprocess
import sys
import time
from datetime import datetime


TOPICS = [
    "/gps_rtk_f9p_helical/gps/fix",
    "/gps_rtk_f9p_helical/gps/nmea",
    "/gps_rtk_f9p_helical/gps/rtk_status",
    "/pixhawk/global_position/raw/satellites",
    "/pixhawk/global_position/raw/fix",
    "/cmd_vel",
    "/cmd_vel_raw",
    "/imu",
]


def build_bag_name(scenario: str, duration_label: str) -> str:
    """
    Build bag name: YY_MMDD_HHMM_<scenario>_<duration>.bag
    Duration will be replaced at the end with the measured runtime.
    """
    stamp = datetime.now().strftime("%y_%m%d_%H%M")
    return f"{stamp}_{scenario}_{duration_label}.bag"


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

    try:
        proc = subprocess.Popen(cmd)
    except FileNotFoundError:
        print("Error: 'ros2' command not found. Make sure your ROS 2 environment is sourced.", file=sys.stderr)
        return 1

    try:
        proc.wait()
        # Normal exit (no Ctrl+C). Use elapsed time anyway.
        end_monotonic = time.monotonic()
    except KeyboardInterrupt:
        # User pressed Ctrl+C; stop the ros2 bag process and measure duration.
        print("\nStopping ros2 bag recording...")
        try:
            # Send SIGINT to ros2 bag process; if it's already exiting this is harmless.
            proc.send_signal(signal.SIGINT)
        except ProcessLookupError:
            pass
        finally:
            try:
                proc.wait(timeout=10.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        end_monotonic = time.monotonic()

    duration_s = max(0, int(end_monotonic - start_monotonic))
    duration_label = f"{duration_s}s"
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