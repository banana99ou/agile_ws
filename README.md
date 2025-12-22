### agile_ws — LIMO GNSS Fix/Re-fix Experiment Workspace

This repository is a **workspace for running motion-assisted GNSS experiments** on an **AgileX LIMO**.

The experiment goal is to compare GNSS solutions **not** “position accuracy”. (e.g., ublox X20 PPP tech vs GPS/GPS-RTK tech) on:
- **Time to first fix**
- **Fix duration / stability**
- **Time to re-fix after loss**

Multiple sensors are co-mounted and recorded at the same time; **repeatable motion is helpful for comparability**, but **vehicle pose is not treated as ground truth**.

---

### High-level architecture (target)

- **Experiment Manager (orchestrator + UI)**
  - Scenario selection (dropdown)
  - Pre-run checklist / validity gates
  - Start/stop recording
  - Start/stop/abort scenarios
  - Live monitoring (GNSS fix state, rates, CPU/drops, cmd vs measured motion)
  - Optional “return to rally point” assist (manual/automatic depending on what exists)

- **Scenario Runner (motion module)**
  - Executes a motion profile (open-loop is acceptable)
  - Publishes `cmd_vel`
  - Emits a structured **event stream** (RUN_START, SEGMENT_START, RUN_END, ABORT)

- **Recorder**
  - Starts `ros2 bag record` before motion and stops after motion
  - Uses a standardized topic list and QoS profile
  - Saves bag with **metadata in filename** and writes a sidecar manifest (JSON/YAML)

- **Analyzer (offline)**
  - Reads bag + event stream
  - Produces a report (CSV/plots): fix timelines, refix times, drop rates, “valid window”
  - May apply heuristics (cmd vs measured motion) in addition to the event stream for post-mortem salvage

**Design principle**: event stream and heuristics are complementary. Events define intent; heuristics help detect anomalies and salvage partial runs.

---

### Definitions (agreed working assumptions)

- **Fix flags**: the project uses a client-provided ranked set:
  - **F** (RTK Fix), **R** (RTK Float), **D** (Differential), **3D**, **2D**, **N** (No fix)
  - ROS `NavSatFix.status.status` is too coarse for this; preserve the client flags explicitly as a dedicated status field/topic (or raw receiver fields + a normalized mapping).

- **Refix** (working definition): “refixed” means the desired fix state is sustained for **≥ 1.0 s**.
  - If a receiver updates at 10 Hz, that corresponds to ~10 consecutive samples; adjust if publish rate differs.

- **Timebase**: use a single ROS timebase for relative timing **as long as all publishers share the same clock domain**.
  - If sensors are on multiple machines with unsynced clocks, fix/re-fix timing comparisons become unreliable.

---

### Validity gates (not performance pass/fail)

A run is “usable” if:
- **All sensors were present and publishing** (expected topic set exists; expected rates are roughly met)
- **ROS bag started before motion and ended after motion**
- **scenario completed** (time/distance reached) or is marked as **ABORT** with reason
- **no massive message drop / CPU overload** (define thresholds later; start by logging observed drops/rates)
- **GNSS status fields required for analysis exist in the bag**

These gates are about data integrity, not “which receiver wins.”

---

### Safety model (important)

This project assumes remote operation (VPN/VNC). A network-dependent stop is **not sufficient** on its own.

Target safety behavior:
- **Onboard software deadman/watchdog**: if the robot does not receive a valid heartbeat at a required rate, it commands stop.
- **Single authority for motion**: avoid “two nodes fighting.” Use a command mux / explicit stop gating so E-stop can override every motion source.
- **E-stop semantics**: any trip condition results in immediate command of zero velocity and scenario abort event.

Hardware E-stop is ideal; if unavailable, treat speed envelopes and environment controls as mandatory.

---

### Scenario specification (data, not hardcoded)

Scenarios should be stored as readable files (YAML/JSON) containing:
- velocity/accel levels and segment structure
- predicted segment/run duration and distance
- tolerances used for “valid window” detection (cmd vs measured motion)
- safety limits (max cmd speed, max yaw rate, max runtime)

The Runner should accept a scenario file path and execute it.

---

### What to record (minimum recommended)

- **Motion context**
  - `cmd_vel`
  - `/wheel/odom`
  - `/imu` (for sanity, yaw-rate/vibration context)

- **GNSS per receiver (namespaced)**
  - raw fix message(s) (e.g., `NavSatFix`)
  - a **normalized client fix flag** topic (F/R/D/3D/2D/N) or raw fields sufficient to reconstruct it
  - any receiver-specific status topics that are needed to compute fix timelines

- **Experiment events**
  - runner event topic (RUN_START / SEGMENT markers / RUN_END / ABORT)

---

### Repository map (what each script is)

Top-level scripts:
- **`limo_scenario_motion.py`**: Scenario Runner prototype. Publishes `cmd_vel` and uses `/wheel/odom` for basic heading hold and distance/time stopping.
- **`limo_segment_teleop.py`**: Manual/segment teleop (used for staging / return-to-start workflows).
- **`limo_rally_teleop.py`**: Teleop / rally-point related control (prototype “return to rally point” exists).
- **`odom_monitor.py`**: Monitoring helper for odometry (sanity checks).
- **`gps_status_display.py`**: Display helper for GPS status (human monitoring).
- **`GPS-RTK_ROS2_pub_node.py`**: F9P Helical GNSS node. Forwards RTCM from TCP to the receiver and publishes GNSS status + `NavSatFix`.
- **`rtcm_server.py`**: RTCM TCP broadcaster server (feeds receivers via network).
- **`RTK_RTCM_decoder.py`**, **`check_rtcm.py`**, **`F9P_RTK_logger.py`**: Utilities for RTCM/RTK decode/logging/verification.
- **`pixhawk_heartbeat_test.py`**: PX4/MAVROS heartbeat test utility.
- **`env_robot.sh`**: Environment helper script(s) for robot setup.

ROS2 packages under `src/`:
- **`src/limo_ros2/`**: LIMO base ROS2 package(s), including launch files.
- **`src/rtcm_to_mavros/`**: RTCM → MAVROS helper(s) (e.g., `rtcm_tcp_pub.py`).

Other subtree:
- **`ohcoach-cell-tools/`**: Ohcoach cell parsing tools (separate domain; see `ohcoach-cell-tools/README.md`).

---

### TODO (next actions)

- **Experiment Manager**
  - Define a minimal manager CLI first (UI later): select scenario, start recorder, start runner, stop/abort, write manifest.
  - Standardize bag naming + sidecar metadata.

- **Namespaces & topic contract**
  - Put each receiver under its own namespace and define a consistent topic contract.
  - Decide which topics from MAVROS/PX4 are authoritative for fix state.

- **Fix flag normalization**
  - Implement a normalized fix flag (F/R/D/3D/2D/N) per receiver and record it.
  - Keep raw fields as well for debugging.

- **Safety**
  - Implement onboard deadman/watchdog and define stop authority / mux rules.
  - Add thresholds for “unusable run” (drops, missing topics, etc.).

- **Scenario spec**
  - Store scenario definitions as YAML/JSON (velocity/accel levels, predicted duration/distance, safety limits).

- **Analysis**
  - Implement offline analysis that extracts fix/re-fix timelines and run validity; incorporate both event stream and heuristics.

- **Documentation**
  - Add per-script docstrings describing role in the experiment system.
  - Add a launch README describing how to launch LIMO + MAVROS + GNSS nodes together and how namespaces are applied.


