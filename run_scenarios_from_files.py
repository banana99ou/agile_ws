#!/usr/bin/env python3
"""
Reads human-readable scenario description files (hardcoded paths) and invokes
`limo_scenario_motion.py` accordingly.

This script is a ROS 2 node (rclpy) that orchestrates:
- (optional) Data_Logger.py (ros2 bag record wrapper)
- limo_scenario_motion.py (motion per level)

It publishes simple status/event strings for monitoring and subscribes to /estop
to refuse/abort motion when E-stop is active.

1. See all available levels:
    python3 run_scenarios_from_files.py --list-levels
2. Run a specific level (e.g., level_2):
    python3 run_scenarios_from_files.py --level level_2
3. Test the command without moving the robot (Dry Run):
    python3 run_scenarios_from_files.py --level level_2 --dry-run
"""

from __future__ import annotations

import argparse
import configparser
import subprocess
import sys
import time
import signal
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import rclpy  # pyright: ignore[reportMissingImports]
from rclpy.node import Node  # pyright: ignore[reportMissingImports]
from std_msgs.msg import String, Bool  # pyright: ignore[reportMissingImports]


ROOT = Path(__file__).resolve().parent
MOTION_SCRIPT = ROOT / "limo_scenario_motion.py"
DATA_LOGGER_SCRIPT = ROOT / "Data_Logger.py"

# Hardcoded scenario description files (as requested)
CONST_VEL_FILE = ROOT / "scenarios" / "const_vel_scenarios.ini"
CONST_ACC_FILE = ROOT / "scenarios" / "const_acc_scenarios.ini"


@dataclass(frozen=True)
class ScenarioCall:
    name: str
    argv: List[str]

EXPECTED_SECTION_KEYS = [
    "scenario",
    "heading_deg",
    "distance_m",
    "speed_mps",
    "acc_mps2",
    "max_speed_mps",
    "vel_tolerance",
    "acc_tolerance",
    "rate_hz",
    "max_duration_s",
    "planned_time_s",
    "final_speed_mps",
    "notes",
]


def _get_float(section: configparser.SectionProxy, key: str) -> float:
    try:
        return section.getfloat(key)
    except Exception as e:
        raise ValueError(f"Invalid or missing float '{key}' in section [{section.name}]: {e}") from e


def _get_optional_float(section: configparser.SectionProxy, key: str) -> Optional[float]:
    v = section.get(key, fallback=None)
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        return float(s)
    except Exception as e:
        raise ValueError(f"Invalid float '{key}' in section [{section.name}]: {e}") from e


def _get_str(section: configparser.SectionProxy, key: str) -> str:
    v = section.get(key, fallback=None)
    if v is None or not str(v).strip():
        raise ValueError(f"Missing '{key}' in section [{section.name}]")
    return str(v).strip()


def load_scenario_file(path: Path) -> Tuple[Dict[str, str], List[ScenarioCall], float]:
    if not path.exists():
        raise FileNotFoundError(f"Scenario file not found: {path}")

    cfg = configparser.ConfigParser(interpolation=None)
    cfg.optionxform = str  # preserve key case (we use snake_case anyway)
    cfg.read(path, encoding="utf-8")

    if "meta" not in cfg:
        raise ValueError(f"Missing required [meta] section in {path}")

    meta = cfg["meta"]
    scenario_type = _get_str(meta, "type")
    inter_run_pause_s = meta.getfloat("inter_run_pause_s", fallback=0.0)

    calls: List[ScenarioCall] = []
    for section_name in cfg.sections():
        if section_name == "meta":
            continue

        s = cfg[section_name]

        # Enforce unified template: all sections must include the same keys (values may be blank).
        missing = [k for k in EXPECTED_SECTION_KEYS if k not in s]
        if missing:
            raise ValueError(
                f"Section [{section_name}] in {path} is missing required keys: {', '.join(missing)}"
            )

        # defaults
        rate_hz = meta.getfloat("default_rate_hz", fallback=20.0)
        max_duration_s = meta.getfloat("default_max_duration_s", fallback=60.0)

        # per-scenario overrides
        rate_hz_opt = _get_optional_float(s, "rate_hz")
        if rate_hz_opt is not None:
            rate_hz = rate_hz_opt
        max_dur_opt = _get_optional_float(s, "max_duration_s")
        if max_dur_opt is not None:
            max_duration_s = max_dur_opt

        distance_m = _get_float(s, "distance_m")

        argv = [
            sys.executable,
            str(MOTION_SCRIPT),
            "--scenario",
            scenario_type,
            "--distance",
            f"{distance_m}",
            "--rate-hz",
            f"{rate_hz}",
            "--max-duration",
            f"{max_duration_s}",
        ]

        if scenario_type == "const_vel":
            speed_mps = _get_float(s, "speed_mps")
            vel_tol = meta.getfloat("default_vel_tolerance", fallback=0.05)
            vel_tol_opt = _get_optional_float(s, "vel_tolerance")
            if vel_tol_opt is not None:
                vel_tol = vel_tol_opt
            argv += ["--speed", f"{speed_mps}", "--vel-tolerance", f"{vel_tol}"]

        elif scenario_type == "const_acc":
            acc_mps2 = _get_float(s, "acc_mps2")
            acc_tol = meta.getfloat("default_acc_tolerance", fallback=0.1)
            acc_tol_opt = _get_optional_float(s, "acc_tolerance")
            if acc_tol_opt is not None:
                acc_tol = acc_tol_opt

            max_speed_mps = _get_optional_float(s, "max_speed_mps")
            if max_speed_mps is None:
                max_speed_mps = _get_optional_float(meta, "default_max_speed_mps")  # type: ignore[arg-type]
            if max_speed_mps is None:
                raise ValueError(
                    f"Missing 'max_speed_mps' in section [{section_name}] for const_acc scenarios"
                )

            argv += [
                "--acc",
                f"{acc_mps2}",
                "--acc-tolerance",
                f"{acc_tol}",
                "--max-speed",
                f"{max_speed_mps}",
            ]
        else:
            raise ValueError(f"Unsupported scenario type '{scenario_type}' in {path}")

        calls.append(ScenarioCall(name=section_name, argv=argv))

    meta_dict = {k: v for k, v in meta.items()}
    return meta_dict, calls, float(inter_run_pause_s)


def start_data_logger(scenario_label: str) -> subprocess.Popen:
    """
    Start Data_Logger.py (ros2 bag record wrapper) in a child process.
    The logger is stopped later via SIGINT (or terminate/kill fallback) so it can finalize and rename the bag.
    """
    if not DATA_LOGGER_SCRIPT.exists():
        raise FileNotFoundError(f"Data_Logger.py not found: {DATA_LOGGER_SCRIPT}")

    # Use the same interpreter as this script.
    cmd = [sys.executable, str(DATA_LOGGER_SCRIPT), scenario_label]
    # Force a stable CWD so Data_Logger writes under this workspace's "Experiment Data/".
    return subprocess.Popen(cmd, cwd=str(ROOT))


def wait_process_alive(proc: subprocess.Popen, seconds: float) -> None:
    """
    Precaution-only: confirm the subprocess does not immediately die.
    """
    deadline = time.time() + float(seconds)
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"Process exited early (code={proc.returncode})")
        time.sleep(0.05)


def stop_data_logger(proc: subprocess.Popen, timeout_s: float = 15.0) -> None:
    """
    Stop Data_Logger.py gracefully.
    On POSIX, SIGINT is the intended stop signal (similar to Ctrl+C) so Data_Logger can rename the bag.
    On platforms where SIGINT isn't delivered as expected, we fall back to terminate/kill.
    """
    if proc.poll() is not None:
        return

    try:
        proc.send_signal(signal.SIGINT)
    except Exception:
        try:
            proc.terminate()
        except Exception:
            pass

    try:
        proc.wait(timeout=timeout_s)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
        try:
            proc.wait(timeout=5.0)
        except Exception:
            pass


class ScenarioOrchestrator(Node):
    def __init__(self):
        super().__init__("scenario_orchestrator")
        self._pub_status = self.create_publisher(String, "/scenario_runner/status", 10)
        self._pub_event = self.create_publisher(String, "/scenario_runner/event", 10)

        self.estop_active = False
        self.create_subscription(Bool, "/estop", self._on_estop, 10)

    def _on_estop(self, msg: Bool):
        self.estop_active = bool(msg.data)

    def status(self, text: str):
        m = String()
        m.data = text
        self._pub_status.publish(m)

    def event(self, text: str):
        m = String()
        m.data = text
        self._pub_event.publish(m)

    def spin_sleep(self, seconds: float):
        end = time.time() + float(seconds)
        while rclpy.ok() and time.time() < end:
            rclpy.spin_once(self, timeout_sec=0.1)

    def run_motion_subprocess(self, argv: List[str]) -> int:
        """
        Run a motion level and keep spinning so /estop can be observed.
        If estop becomes active, attempt to stop the motion process.
        """
        proc = subprocess.Popen(argv)
        try:
            while rclpy.ok() and proc.poll() is None:
                rclpy.spin_once(self, timeout_sec=0.1)
                if self.estop_active:
                    self.get_logger().error("E-STOP active; aborting motion subprocess")
                    try:
                        proc.send_signal(signal.SIGINT)
                    except Exception:
                        try:
                            proc.terminate()
                        except Exception:
                            pass
                    break

            try:
                return proc.wait(timeout=10.0)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
                return proc.wait()
        finally:
            # Best-effort ensure it's not left running
            if proc.poll() is None:
                try:
                    proc.kill()
                except Exception:
                    pass

    def run_level(
        self,
        scenario_type: str,
        call: ScenarioCall,
        no_record: bool,
        record_startup_wait_s: float,
    ) -> int:
        label = f"{scenario_type}_{call.name}" if scenario_type else call.name

        self.event(f"LEVEL_START {label}")
        self.status(f"phase=starting level={label}")

        if self.estop_active:
            raise RuntimeError("E-STOP active; refusing to start level")

        logger_proc: Optional[subprocess.Popen] = None
        try:
            if not no_record:
                logger_proc = start_data_logger(label)
                if record_startup_wait_s > 0:
                    wait_process_alive(logger_proc, seconds=float(record_startup_wait_s))

            if self.estop_active:
                raise RuntimeError("E-STOP active; refusing to start motion")

            self.status(f"phase=running level={label}")
            rc = self.run_motion_subprocess(call.argv)
            return rc
        finally:
            self.status(f"phase=stopping level={label}")
            if logger_proc is not None:
                stop_data_logger(logger_proc)
            self.event(f"LEVEL_END {label}")


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Run limo_scenario_motion.py scenarios from INI description files (hardcoded)."
    )
    p.add_argument(
        "--scenario-type",
        choices=["const_vel", "const_acc", "both"],
        default="both",
        help="Which scenario file(s) to search in.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the commands that would run, but do not execute them.",
    )
    p.add_argument(
        "--level",
        type=str,
        default=None,
        help="The level section name to run (e.g. 'level_2'). Required unless using --list-levels.",
    )
    p.add_argument(
        "--list-levels",
        action="store_true",
        help="List available level section names and exit (filtered by --scenario-type).",
    )
    p.add_argument(
        "--no-record",
        action="store_true",
        help="Do not start/stop Data_Logger.py (motion only).",
    )
    p.add_argument(
        "--record-startup-wait-s",
        type=float,
        default=1.0,
        help="Precaution-only: wait this many seconds and confirm Data_Logger.py process stays alive before motion starts.",
    )
    args = p.parse_args(argv)

    if not args.list_levels and not args.level:
        print("Error: --level <name> is required unless using --list-levels.")
        return 1

    rclpy.init(args=None)
    node = ScenarioOrchestrator()

    files: List[Path] = []
    if args.scenario_type in ("const_vel", "both"):
        files.append(CONST_VEL_FILE)
    if args.scenario_type in ("const_acc", "both"):
        files.append(CONST_ACC_FILE)

    if not MOTION_SCRIPT.exists():
        node.get_logger().error(f"Error: motion script not found: {MOTION_SCRIPT}")
        node.destroy_node()
        rclpy.shutdown()
        return 2

    try:
        node.event("RUN_START")

        # 1. If listing, gather names and exit.
        if args.list_levels:
            for path in files:
                try:
                    meta, calls, _ = load_scenario_file(path)
                    scenario_type = meta.get("type", "").strip()
                    print(f"{path.name} (type={scenario_type})")
                    for c in calls:
                        print(f"  - {c.name}")
                except Exception as e:
                    print(f"Error reading {path.name}: {e}")
            return 0

        # 2. Find the specific requested level (across all allowed files).
        target_call: Optional[Tuple[Path, str, ScenarioCall]] = None
        for path in files:
            try:
                meta, calls, _ = load_scenario_file(path)
                scenario_type = meta.get("type", "").strip()
                for c in calls:
                    if c.name == args.level:
                        target_call = (path, scenario_type, c)
                        break
                if target_call:
                    break
            except Exception:
                continue

        if not target_call:
            node.get_logger().error(
                f"Level '{args.level}' not found in the selected file(s) ({args.scenario_type}). "
                "Use --list-levels to see available names."
            )
            return 5

        path, scenario_type, call = target_call
        node.get_logger().info(f"Scenario file: {path.name} type={scenario_type}")
        node.get_logger().info(f"Level: {call.name}")
        node.get_logger().info("Command: " + " ".join(call.argv))
        node.status(f"phase=ready file={path.name} level={call.name}")

        if args.dry_run:
            node.get_logger().info("Dry run: not executing.")
            return 0

        # 3. Execute the single level
        try:
            rc = node.run_level(
                scenario_type=scenario_type,
                call=call,
                no_record=bool(args.no_record),
                record_startup_wait_s=float(args.record_startup_wait_s),
            )
        except Exception as e:
            node.get_logger().error(f"Aborted level '{call.name}': {e}")
            return 4

        if rc != 0:
            node.get_logger().error(f"Error: scenario '{call.name}' failed with exit code {rc}")
            return rc

        node.event("RUN_END")
        return 0
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())


