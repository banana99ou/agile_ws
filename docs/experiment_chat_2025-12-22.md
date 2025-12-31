### Saved chat notes — 2025-12-22 (Experiment Manager + GNSS fix/re-fix)

This file captures the key outcomes and decisions from an interactive design chat.
It is **not** a full verbatim transcript; it is a structured summary intended to
prevent loss of context.

---

### Context

- **Platform**: AgileX LIMO
- **Sensors / receivers** (current + planned):
  - PX4/MAVROS GPS (topics under `/pixhawk/...`)
  - Holybro F9P Helical via `GPS-RTK_ROS2_pub_node.py` (publishes `gps/fix`, `gps/nmea`, `gps/rtk_status`)
  - Ohcoach cell (client-provided; fix flag ranking provided by client)
  - ublox X20 (delivery/data pipeline TBD)
- **Primary experiment goal**: compare GNSS **fix behavior**, not position accuracy:
  - time to first fix
  - fix duration / stability
  - time to re-fix after loss of fix
- **Motion**: open-loop motion on LIMO is acceptable; ground-truth vehicle pose is not required.
  - Motion exists mainly to provide comparable operating conditions (dynamics, vibration, RF environment).

---

### Fix flag / state semantics (important)

- Client-provided ranked flags (best → worst):
  - **F** (RTK Fix)
  - **R** (RTK Float)
  - **D** (Differential)
  - **3D** (3D fix)
  - **2D** (2D fix)
  - **N** (No fix)

Notes:
- ROS `NavSatFix.status.status` is coarse (NO_FIX/FIX/SBAS/GBAS) and cannot represent
  all client fix flags. Using it alone can be **lossy** (e.g., RTK float vs fixed).
- Decision direction: preserve fix flags explicitly as a dedicated “normalized fix flag”
  field/topic per receiver, and record raw receiver fields too.

---

### Validity gates (not performance pass/fail)

“No pass/fail besides reasonable stats” was judged insufficient for PI/client context.
Instead, define objective **run validity gates**:

- all required sensors present and publishing
- rosbag started before motion and ended after motion
- scenario completed (time/distance reached) or ABORT with reason
- no massive message drop / CPU overload (thresholds TBD; at least record observed rates)
- GNSS status fields required for analysis exist in the bag

These gates are about data integrity, not “which receiver is better.”

---

### Time alignment

- Using a single ROS timebase for all is acceptable for this goal (seconds-scale
  fix/re-fix timelines) as long as publishers share the same clock domain.
- If sensors publish from multiple unsynchronized machines, timing comparisons become unreliable.

---

### “Refixed” definition (working)

- Start with: **refixed = sustained desired fix state for ≥ 1.0 s**
  - With 10 Hz updates, that’s ~10 consecutive samples.
  - May adjust once publish rates and flicker behavior are understood.

---

### Motion / heading hold

- Heading hold is needed to keep LIMO reasonably straight during runs.
- Start with wheel odom only for simplicity:
  - Wheel odom yaw can drift; acceptable for this experiment goal.
  - IMU can later be used for yaw-rate damping if needed (not committed yet).

---

### Architecture (target)

- **Experiment Manager** (orchestrator + UI / CLI):
  - scenario selection (dropdown) and “add from path”
  - system monitoring and pre-run checklist
  - start/stop recording to rosbag with metadata in filename + sidecar manifest
  - start/stop/abort runner
  - support manual/auto “return to rally point” (prototype exists)

- **Scenario Runner**:
  - executes scenario spec (file-based, not hardcoded)
  - publishes `cmd_vel`
  - emits **event topic** (RUN_START, SEGMENT markers, RUN_END, ABORT)

- **Recorder**:
  - separate module/process controlling rosbag recording and naming/metadata

- **Analyzer**:
  - offline analysis of fix/re-fix timelines from bag
  - compute “valid windows” using both event stream and heuristics

Event topic vs heuristics:
- Decision: **do both**. Events define intent; heuristics allow post-mortem salvage.

---

### Safety / E-stop (software-only constraints)

- Remote operation over VPN/VNC: network-dependent stop alone is not sufficient.
- Desired model: onboard **deadman/watchdog** that stops motion if heartbeat is missing.
- Direction: all movement-related nodes should respect a common E-stop signal and
  stop immediately when tripped.
- Hardware E-stop is not planned; therefore enforce conservative envelopes and environment controls.

---

### Repo documentation actions taken

- Added repository root `README.md` describing:
  - goal/non-goals
  - target architecture
  - validity gates
  - safety model
  - scenario spec direction
  - what to record
  - repo file map
  - TODO list
- Updated `limo_scenario_motion.py` docstring to state it is the Runner module in a larger system.

---

### Open items / next steps

- Decide per receiver:
  - which topics are authoritative for fix state
  - how to map raw fields → normalized client fix flags (F/R/D/3D/2D/N)
- Namespacing plan in launch files for all receivers and motion modules.
- Define Recorder naming convention and sidecar manifest schema (run_id, scenario hash, timestamps, operator, git commit, etc.).
- Define stop authority / mux rules to prevent multiple motion sources fighting.
- Measure LIMO top speed and stability envelope (PI requested trying 15 m/s; treat as aspirational and safety-gated).


