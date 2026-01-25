### (한국어) agile_ws — LIMO GNSS Fix/Re-fix 실험 워크스페이스

이 저장소는 **AgileX LIMO**에서 **모션 보조 GNSS 실험**을 수행하기 위한 **워크스페이스**입니다.

이 실험의 목표는 “위치 정확도”가 아니라, 예를 들어 ublox X20 PPP vs GPS/GPS-RTK 같은 GNSS 솔루션의 **fix 거동**을 비교하는 것입니다:
- **첫 Fix까지 걸리는 시간 (TTFF)**
- **Fix 지속시간 / 안정성**
- **Fix 손실 후 재-Fix까지의 시간**

여러 센서를 동일 위치에 장착해 동시에 기록합니다. **반복 가능한 모션은 비교 가능성을 높이지만**, **차량 자세/포즈를 ground truth로 취급하지 않습니다**.

---

### 빠른 시작 (일반적인 실행)

현재 이 repo는 몇 개의 스크립트로 구성된 “얇은 실험 매니저(thin experiment manager)” 형태로 동작합니다:
- `start_ROS.sh`: 로봇 스택(드라이버 + MAVROS + RTK 노드)을 launch로 구동
- `estop_cli.py`: 터미널 E-stop + 안전 필터 역할 (**`cmd_vel_raw` 구독 → 필터된 `cmd_vel` 발행**, 그리고 `/estop` 발행)
- `run_scenarios_from_files.py`: 시나리오 레벨을 실행하고 (기본값) `Data_Logger.py`로 rosbag를 시작/종료

### 로봇 구동 (Bring-up)

- **터미널 1 (ROS 환경 + Bring-up)**:
  - `./start_ROS.sh`
  - 수행 내용:
    - `./env_sanitizer.sh` 실행 (ROS 환경 + discovery 신뢰성 설정)
    - `ros2 launch limo_base LIMO+MAVROS+RTK_Node_Launcher.launch.py port_name:=ttyUSB1` 로 `limo_base` launch

- **터미널 2 (E-stop CLI — 계속 실행 유지 권장)**:
  - `python3 estop_cli.py`
  - 키:
    - `s` 또는 `SPACE`: E-stop 활성화(래치), 0 `cmd_vel` 발행
    - `c`: E-stop 해제
    - `q` / `Ctrl+C`: 종료 (보수적으로 E-stop은 활성 상태로 남김)
  - 참고: 연결성 ping 대상은 현재 `estop_cli.py` 내부(`ping_targets`)에 하드코딩되어 있습니다.

- **터미널 3 (시나리오 레벨 실행 + bag 기록)**:
  - 레벨 목록:
    - `python3 run_scenarios_from_files.py --list-levels --scenario-type const_vel --show-notes`
  - 레벨 실행 (기본적으로 기록함):
    - `python3 run_scenarios_from_files.py --scenario-type const_vel --level level_2`
  - 모션만 실행 (기록 안 함):
    - `python3 run_scenarios_from_files.py --scenario-type const_vel --level level_2 --no-record`
  - Dry-run (명령만 출력, 실제로 움직이지 않음):
    - `python3 run_scenarios_from_files.py --scenario-type const_vel --level level_2 --dry-run`

### 출력 (데이터 저장 위치)

- ROS2 bag은 `Experiment Data/` 아래에 저장됩니다.
- Bag 폴더 이름 규칙(`Data_Logger.py`가 생성):
  - `YY_MMDD_HHMM_<scenario>_<duration>.bag`
  - duration은 처음에 `DURATION_PLACEHOLDER`로 생성되며, 종료 시 측정된 runtime(예: `48s`)으로 rename 됩니다.

### 오프라인 분석 (ROS 없이)

`Post processing/` 아래의 오프라인 파이프라인은 pure-Python `rosbags` reader를 사용하므로 **ROS 설치 없이도** 동작하도록 설계되어 있습니다.
- 실행 진입점: `Post processing/gnss_fix_pipeline.py` (docstring의 예시 참고)
- Bag reader의 핵심 의존성: `rosbags` (`Post processing/bag_to_human_csv.py` 참고)

---

### 아키텍처 (목표 vs 현재)

- **Experiment Manager (오케스트레이터 + UI)** (목표; 현재는 `run_scenarios_from_files.py` + 터미널 툴이 일부 역할을 대체)
  - 시나리오 선택(UI)
  - 실행 전 체크리스트 / 유효성 게이트
  - 기록 시작/종료
  - 시나리오 시작/종료/중단
  - 라이브 모니터링(GNSS fix 상태, rate, CPU/drop, cmd vs 측정 모션)
  - 선택적으로 “rally point 복귀” 보조(수동/자동)

- **Scenario Runner (모션 모듈)** (현재: `limo_scenario_motion.py`, `run_scenarios_from_files.py`가 호출)
  - 모션 프로파일 실행(open-loop 허용)
  - `cmd_vel_raw` 발행 (권장: 안전/E-stop 노드가 필터링해 `cmd_vel` 발행)
  - 구조화된 **이벤트 스트림**(RUN_START, SEGMENT_START, RUN_END, ABORT) 발행

- **Recorder**
  - 모션 전에 `ros2 bag record` 시작, 모션 후 종료
  - 표준 topic 리스트 및 QoS 프로파일 사용
  - 파일명에 **메타데이터 포함**, sidecar manifest(JSON/YAML) 기록

- **Analyzer (오프라인)**
  - bag + 이벤트 스트림을 읽음
  - 보고서(CSV/plots): fix timeline, refix time, drop rate, “valid window”
  - 이벤트 스트림 외에 휴리스틱(cmd vs 측정 모션)로 이상 탐지/부분 run salvage 지원

**설계 원칙**: 이벤트 스트림과 휴리스틱은 상호 보완적입니다. 이벤트는 “의도”를 정의하고, 휴리스틱은 이상 상황을 탐지하며 부분 데이터를 salvage합니다.

---

### 현재 구현 메모 (현재 존재하는 것)

- **오케스트레이션**: `run_scenarios_from_files.py`
  - `scenarios/*.ini`에서 시나리오 레벨 로드
  - 선택적 preflight(토픽 존재 / 메시지 flow / subscriber 체크)
  - 선택적 RTK FIXED 게이트(`/gps_rtk_f9p_helical/gps/rtk_status`, quality==4)
  - `--no-record`가 아니면 `Data_Logger.py`를 시작/종료
  - `/estop`이 활성화되면 모션 abort
- **모션**: `limo_scenario_motion.py`가 `cmd_vel_raw` 발행(안전 필터가 `cmd_vel` 발행한다고 가정)
- **기록**: `Data_Logger.py`는 canonical topic 리스트로 `ros2 bag record`를 감싸고 health heartbeat를 발행
- **안전 필터 / E-stop**: `estop_cli.py`가 `cmd_vel_raw` → `cmd_vel` 브리지 및 `/estop` 발행

---

### 정의 (합의된 작업 가정)

- **Fix 플래그**: 프로젝트는 클라이언트 제공의 순위 기반 플래그를 사용합니다:
  - **F** (RTK Fix), **R** (RTK Float), **D** (Differential), **3D**, **2D**, **N** (No fix)
  - ROS `NavSatFix.status.status`는 너무 coarse 하므로, 클라이언트 플래그를 전용 status field/topic으로 명시적으로 보존(또는 raw 필드 + 정규화 매핑)합니다.

- **Refix** (작업 정의): “refixed”는 원하는 fix 상태가 **≥ 1.0 s** 동안 지속되는 것을 의미합니다.
  - 예: 수신기가 10 Hz면 약 10개 연속 샘플에 해당합니다(발행 rate에 따라 조정).

- **시간 기준(Timebase)**: 모든 publisher가 동일 clock domain을 공유한다면, 상대 시간 비교는 단일 ROS timebase로 충분합니다.
  - 여러 머신의 클럭이 동기화되지 않으면 fix/refix 타이밍 비교가 신뢰하기 어렵습니다.

---

### 유효성 게이트 (성능 pass/fail 아님)

Run이 “사용 가능(usable)”하려면:
- **모든 센서가 존재하며 발행 중**(기대 토픽 세트가 존재, rate가 대략 기대 수준)
- **rosbag가 모션 전에 시작하고 모션 후에 종료**
- **시나리오 완료**(시간/거리 도달) 또는 **ABORT**(사유 포함)
- **심각한 메시지 drop / CPU 과부하가 없음**(임계값은 추후 정의; 우선 관측치 기록)
- **분석에 필요한 GNSS status 필드가 bag에 존재**

이 게이트들은 데이터 무결성에 대한 조건이며, “어느 수신기가 더 좋다”를 판단하기 위한 pass/fail이 아닙니다.

---

### 시나리오 명세 (하드코딩이 아닌 데이터)

시나리오는 YAML/JSON 같은 읽기 쉬운 파일로 저장하는 것을 권장합니다:
- 속도/가속 레벨 및 세그먼트 구조
- 예측 세그먼트/런 duration 및 거리
- “valid window” 검출 허용오차(cmd vs 측정 모션)
- 안전 한계(max cmd speed, max yaw rate, max runtime)

Runner는 시나리오 파일 경로를 받아 실행할 수 있어야 합니다.

---

### 기록할 것 (최소 권장)

- **모션 컨텍스트**
  - `/cmd_vel` (필터링된/안전한 최종 명령)
  - `/cmd_vel_raw` (모션 모듈의 원본 명령)
  - `/wheel/odom`
  - `/imu` (sanity: yaw-rate/진동 컨텍스트)

- **수신기별 GNSS (네임스페이스 적용 권장)**
  - raw fix 메시지(예: `NavSatFix`)
  - 정규화된 클라이언트 fix flag(F/R/D/3D/2D/N) 토픽, 또는 이를 복원할 수 있는 raw 필드
  - fix timeline 계산에 필요한 수신기 특화 status 토픽

- **실험 이벤트**
  - runner 이벤트 토픽(RUN_START / SEGMENT marker / RUN_END / ABORT)

---

### 저장소 맵 (각 스크립트 역할)

Top-level scripts:
- **`start_ROS.sh`**: bring-up 원라인(`env_sanitizer.sh` 실행 후 `limo_base` + MAVROS + RTK 노드 launch).
- **`env_sanitizer.sh`**: 신뢰성 관련 ROS 2 환경 변수 설정(특히 `ROS_LOCALHOST_ONLY=1`) + ROS 2 daemon 재시작.
- **`estop_cli.py`**: 터미널 E-stop + 안전 필터(`cmd_vel_raw` → `cmd_vel`, `/estop` 발행).
- **`run_scenarios_from_files.py`**: 시나리오 오케스트레이터(`scenarios/*.ini` 로드, `limo_scenario_motion.py` 실행, `Data_Logger.py` 제어).
- **`limo_scenario_motion.py`**: Scenario Runner 프로토타입(`/wheel/odom` 기반 heading-hold, `cmd_vel_raw` 발행).
- **`Data_Logger.py`**: ROS2 bag recorder wrapper(`ros2 bag record`, canonical topic list, 측정 duration으로 bag rename).
- **`limo_rally_teleop.py`**: 텔레옵 / rally-point 관련 제어(“rally point 복귀” 프로토타입 포함).
- **`odom_monitor.py`**: Odometry sanity 모니터링 헬퍼.
- **`gps_status_display.py`**: 사람이 보기 좋은 GPS 상태 표시 헬퍼.
- **`GPS-RTK_ROS2_pub_node.py`**: F9P Helical GNSS 노드(TCP RTCM → 수신기, GNSS status + `NavSatFix` 발행).
- **`rtcm_server.py`**: RTCM TCP 브로드캐스터 서버(네트워크로 수신기에 RTCM 공급).
- **`hotspot_ON.sh`**: 로봇 Wi-Fi hotspot 헬퍼(NetworkManager).
- **`fix_hotspot_dhcp_reservation.sh`**: hotspot DHCP reservation 헬퍼(고정 IP 용도).

ROS2 packages under `src/`:
- **`src/limo_ros2/`**: LIMO base ROS2 패키지(launch 포함).
- **`src/rtcm_to_mavros/`**: RTCM → MAVROS 헬퍼(예: `rtcm_tcp_pub.py`).

Other subtree:
- **`ohcoach-cell-tools/`**: Ohcoach cell 파싱 도구(별도 도메인; `ohcoach-cell-tools/README.md` 참고).

Offline analysis:
- **`Post processing/`**: ROS2-bag → CSV/plot 파이프라인(특히 `gnss_fix_pipeline.py`, `bag_to_human_csv.py`, `gps_fix_analysis.py`).

System tests / utilities:
- **`system testing/`**: 각종 validator(예: `check_rtcm.py`, 모션 envelope 도구).

---

### TODO (다음 작업)

- **Experiment Manager**
  - 최소 CLI부터 정의(UI는 추후): 시나리오 선택, recorder 시작, runner 시작, stop/abort, manifest 작성
  - bag naming + sidecar metadata 표준화

- **Namespaces & topic contract**
  - 수신기별 네임스페이스 적용 및 일관된 topic contract 정의
  - MAVROS/PX4에서 fix 상태의 authoritative 토픽 결정

- **Fix flag 정규화**
  - 수신기별 정규화 fix flag(F/R/D/3D/2D/N) 구현 및 기록
  - 디버깅을 위해 raw 필드도 함께 유지

- **Safety**
  - 온보드 deadman/watchdog 구현 및 stop authority / mux 규칙 정의
  - “사용 불가 run” 임계값 추가(drop, 누락 토픽 등)

- **Scenario spec**
  - YAML/JSON으로 시나리오 정의 저장(속도/가속 레벨, 예측 duration/거리, 안전 한계)

- **Analysis**
  - 오프라인 분석 구현: fix/refix timeline 및 run validity 추출(이벤트 스트림 + 휴리스틱 통합)

- **Documentation**
  - 스크립트별 역할을 설명하는 docstring 보강
  - LIMO + MAVROS + GNSS 노드 launch 및 네임스페이스 적용 방법을 설명하는 launch README 추가

---

### English (original)

### agile_ws — LIMO GNSS Fix/Re-fix Experiment Workspace

This repository is a **workspace for running motion-assisted GNSS experiments** on an **AgileX LIMO**.

The experiment goal is to compare GNSS solutions by **fix behavior** (not “position accuracy”), e.g. ublox X20 PPP vs GPS/GPS-RTK, using:
- **Time to first fix (TTFF)**
- **Fix duration / stability**
- **Time to re-fix after loss**

Multiple sensors are co-mounted and recorded at the same time. **Repeatable motion is helpful for comparability**, but **vehicle pose is not treated as ground truth**.

---

### Quick start (typical run)

This repo currently works as a “thin experiment manager” composed of a few scripts:
- `start_ROS.sh` brings up the robot stack (driver + MAVROS + RTK node via a launch file).
- `estop_cli.py` provides a terminal E-stop and acts as a safety filter: **subscribes `cmd_vel_raw` → publishes filtered `cmd_vel`** and publishes `/estop`.
- `run_scenarios_from_files.py` runs a selected scenario level and (by default) starts/stops `Data_Logger.py` to record rosbag.

### Bring-up (robot)

- **Terminal 1 (ROS env + bring-up)**:
  - `./start_ROS.sh`
  - What it does:
    - Runs `./env_sanitizer.sh` (ROS env + discovery reliability settings)
    - Launches `limo_base` via `ros2 launch limo_base LIMO+MAVROS+RTK_Node_Launcher.launch.py port_name:=ttyUSB1`

- **Terminal 2 (E-stop CLI — keep this running)**:
  - `python3 estop_cli.py`
  - Keys:
    - `s` or `SPACE`: activate E-stop (latched, publishes zero `cmd_vel`)
    - `c`: clear E-stop
    - `q` / `Ctrl+C`: quit (leaves E-stop active by default)
  - Note: the connectivity ping target is currently hardcoded inside `estop_cli.py` (`ping_targets`).

- **Terminal 3 (run a scenario level + record a bag)**:
  - List levels:
    - `python3 run_scenarios_from_files.py --list-levels --scenario-type const_vel --show-notes`
  - Run a level (records by default):
    - `python3 run_scenarios_from_files.py --scenario-type const_vel --level level_2`
  - Motion only (no recording):
    - `python3 run_scenarios_from_files.py --scenario-type const_vel --level level_2 --no-record`
  - Dry-run (print commands, do not move):
    - `python3 run_scenarios_from_files.py --scenario-type const_vel --level level_2 --dry-run`

### Output (where data goes)

- ROS2 bags are written under `Experiment Data/`
- Bag folder naming pattern (created by `Data_Logger.py`):
  - `YY_MMDD_HHMM_<scenario>_<duration>.bag`
  - The duration starts as `DURATION_PLACEHOLDER` and is renamed on stop to the measured runtime (e.g., `48s`).

### Offline analysis (ROS-free)

The offline pipeline under `Post processing/` is designed to work **without ROS installed** by using the pure-Python `rosbags` reader.
- Entry point: `Post processing/gnss_fix_pipeline.py` (see its docstring examples)
- Key dependency used by the bag reader: `rosbags` (see `Post processing/bag_to_human_csv.py`)

---

### Architecture (target vs current state)

- **Experiment Manager (orchestrator + UI)** (target; today this role is partially covered by `run_scenarios_from_files.py` and terminal tooling)
  - Scenario selection (dropdown)
  - Pre-run checklist / validity gates
  - Start/stop recording
  - Start/stop/abort scenarios
  - Live monitoring (GNSS fix state, rates, CPU/drops, cmd vs measured motion)
  - Optional “return to rally point” assist (manual/automatic depending on what exists)

- **Scenario Runner (motion module)** (today: `limo_scenario_motion.py`, invoked by `run_scenarios_from_files.py`)
  - Executes a motion profile (open-loop is acceptable)
  - Publishes `cmd_vel_raw` (recommended: filtered into `cmd_vel` by a safety/E-stop node)
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

### Current implementation notes (what exists today)

- **Orchestration**: `run_scenarios_from_files.py`
  - Loads scenario levels from `scenarios/*.ini`
  - Optional preflight (topic presence / message flow / subscriber checks)
  - Optional RTK FIXED gate using `/gps_rtk_f9p_helical/gps/rtk_status` (quality==4)
  - Starts/stops `Data_Logger.py` unless `--no-record`
  - Aborts motion if `/estop` becomes active
- **Motion**: `limo_scenario_motion.py` publishes `cmd_vel_raw` (expects a safety filter to publish `cmd_vel`)
- **Recording**: `Data_Logger.py` wraps `ros2 bag record` with a canonical topic list and a health heartbeat
- **Safety filter / E-stop**: `estop_cli.py` bridges `cmd_vel_raw` → `cmd_vel` and publishes `/estop`

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
  - `/cmd_vel` (filtered/safe command sent to the base)
  - `/cmd_vel_raw` (unfiltered command from the motion module)
  - `/wheel/odom`
  - `/imu` (for sanity: yaw-rate/vibration context)

- **GNSS per receiver (namespaced)**
  - raw fix message(s) (e.g., `NavSatFix`)
  - a **normalized client fix flag** topic (F/R/D/3D/2D/N) or raw fields sufficient to reconstruct it
  - any receiver-specific status topics that are needed to compute fix timelines

- **Experiment events**
  - runner event topic (RUN_START / SEGMENT markers / RUN_END / ABORT)

---

### Repository map (what each script is)

Top-level scripts:
- **`start_ROS.sh`**: One-liner bring-up (runs `env_sanitizer.sh`, then launches `limo_base` + MAVROS + RTK node).
- **`env_sanitizer.sh`**: Sets ROS 2 environment variables for reliability (notably `ROS_LOCALHOST_ONLY=1`) and restarts the ROS 2 daemon.
- **`estop_cli.py`**: Terminal E-stop + safety filter (`cmd_vel_raw` → `cmd_vel`, publishes `/estop`).
- **`run_scenarios_from_files.py`**: Scenario orchestrator: loads levels from `scenarios/*.ini`, runs `limo_scenario_motion.py`, and controls `Data_Logger.py`.
- **`limo_scenario_motion.py`**: Scenario Runner prototype. Publishes `cmd_vel_raw` and uses `/wheel/odom` for basic heading hold and distance/time stopping.
- **`Data_Logger.py`**: ROS2 bag recorder wrapper: runs `ros2 bag record` with a canonical topic list and renames the bag with measured duration.
- **`limo_rally_teleop.py`**: Teleop / rally-point related control (prototype “return to rally point” exists).
- **`odom_monitor.py`**: Odometry sanity monitoring helper.
- **`gps_status_display.py`**: Human-readable GPS status display helper.
- **`GPS-RTK_ROS2_pub_node.py`**: F9P Helical GNSS node. Forwards RTCM from TCP to the receiver and publishes GNSS status + `NavSatFix`.
- **`rtcm_server.py`**: RTCM TCP broadcaster server (feeds receivers via network).
- **`hotspot_ON.sh`**: Robot Wi-Fi hotspot helper (NetworkManager).
- **`fix_hotspot_dhcp_reservation.sh`**: Hotspot DHCP reservation helper (for stable IPs).

ROS2 packages under `src/`:
- **`src/limo_ros2/`**: LIMO base ROS2 package(s), including launch files.
- **`src/rtcm_to_mavros/`**: RTCM → MAVROS helper(s) (e.g., `rtcm_tcp_pub.py`).

Other subtree:
- **`ohcoach-cell-tools/`**: Ohcoach cell parsing tools (separate domain; see `ohcoach-cell-tools/README.md`).

Offline analysis:
- **`Post processing/`**: ROS2-bag → CSV/plots pipeline (notably `gnss_fix_pipeline.py`, `bag_to_human_csv.py`, `gps_fix_analysis.py`).

System tests / utilities:
- **`system testing/`**: assorted small validators (e.g., `check_rtcm.py`, motion envelope tools).

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


