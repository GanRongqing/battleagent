# RL Environment Handoff Guide

> READ-ONLY audit of the current maritime POMDP project for an RL teammate.
> Every path below was verified against the current repository at
> `/root/autodl-tmp/hsystem` (Python: `/root/miniconda3/envs/hsystem_env/bin/python`).
> Where something does not exist, the doc says `NOT IMPLEMENTED` / `NEEDS WRAPPER`.

## 1. Purpose

The project contains a **maritime POMDP simulator** (two-sided, continuous physics, USV + UAV
platforms) and a **deterministic White Harness** that plays the defender side through a
hierarchical decision stack.

For RL, the recommended replacement is the **Allocator / Task-Assignment layer only**:

```
legal observation
  → RL policy (WHO gets WHICH TASK against WHICH TARGET)
  → existing controller / BT / ActionSafety
  → simulator
```

RL must **not** learn primitive control (move/lock/takeoff/land/BT-phase). Those stay in the
existing deterministic execution layer.

## 2. Current System Architecture

Real chain (default frozen W5 harness; ASCII from actual call order in
`agent_hybrid_v5.py:AgentMain.step_once`):

```
        Simulator (hsystem/simserver/sim_server.py + hsystem/simulation/core/)
                  │  POST /apply  (actions injected, one ~30 s macro step advanced)
                  ▼
   HTTP API (hsystem/pomdp_api/main.py, 127.0.0.1:8000)
   GET /status  GET /legal_actions  GET /obs  POST /apply  GET /result
                  ▲                                  │
                  │ (poll loop in AgentMain.run)     │
   ┌──────────────┴──────────────────────────────────▼─────────────────────────┐
   │ White Agent / Harness:  agent_hybrid_v5.py (frozen W5 baseline)           │
   │                                                                           │
   │  TrackManager.update(obs)         → belief EnemyTrack[] (agent_hybrid_v5.py:458)│
   │  ThreatAllocator.allocate_usvs()  → {target: [usv,...]}  (agent_hybrid_v5.py:1718/1798)│  ◄── RL replaces this
   │  USVController.step(...)          → USV primitive actions (move/lock/...)  (agent_hybrid_v5.py:1969/2002)│
   │  UAVManager.step(...)             → UAV actions (search/screen/reacquire)  (agent_hybrid_v5.py:2162/2193)│
   │  ActionSafety.filter(...)         → legal-filtered actions                 (agent_hybrid_v5.py:2496)│
   │  ApiClient.apply(safe)            → POST /apply                            (agent_hybrid_v5.py:147)│
   └─────────────────────────────────────────────────────────────────────────────┘
   Opponent policy (opponent_profiles.py B0..B3) runs INSIDE the sim process
   Scenario builder (hsystem/sim_script/20250819TZB/scenario_builder.py) builds each game
```

Optional BT route (a parallel decision/executor prototype, **not** the default W5 path):

```
   Allocator result → TaskCommand (bt_harness_interface.py:141)
   → BTPlatformExecutive.submit_task / tick (bt_harness_interface.py:427, bt_real_trees.py)
   → intent-level ActionRequest[] → Harness ActionSafety → POST /apply
   Decision authority: Harness owns WHO/WHAT(target); BT owns HOW/phase.
```

Real component map:

| Component | Path | Notes |
|---|---|---|
| Simulator backend | `hsystem/simserver/base_server.py`, `sim_server.py`, `http_server.py`, `sim_client.py`, `client_pool.py` | spawns N sim_servers; each game builds engine via `temp.py` |
| Sim physics core | `hsystem/simulation/core/engine.py`, `tzb_engine.py`, `base_engine.pyx` | combat/radar engine; `arsenal/locker.py` etc. |
| HTTP API | `hsystem/pomdp_api/main.py` | FastAPI on `http://127.0.0.1:8000` |
| White Agent / Harness | `agent_hybrid_v5.py` (frozen W5), `agent_hybrid_w6.py` (anti-evasion W6) | both subclass `AgentMain` (v5:2575) |
| TrackManager / belief | `agent_hybrid_v5.py:458` (`EnemyTrack` :293) | legal belief, no hidden truth |
| ThreatAllocator | `agent_hybrid_v5.py:1718`, `allocate_usvs` :1798 | **RL replacement target** |
| USV controller | `agent_hybrid_v5.py:1969`, `USVController.step` :2002 | states DEAD/FROZEN/LOCKING/INTERCEPTING/AVAILABLE |
| UAV manager | `agent_hybrid_v5.py:2162`, `UAVManager.step` :2193 | ON_SHIP/SEARCH/SCREEN/REACQUIRE/RETURN/LANDING/CHARGING/SAFE_LOITER/GLOBAL_SEARCH |
| PlatformExecutive / BT | `bt_harness_interface.py` (contract :235), `bt_real_trees.py` (real trees) | recommended executor contract for RL; NOT in default W5 path |
| ActionSafety | `agent_hybrid_v5.py:2496` (`filter`) | legal_actions + live-state double check, single writer |
| Opponent policy | `opponent_profiles.py` (B0–B4 constants :26-31) | runs in sim process |
| Scenario builder | `hsystem/sim_script/20250819TZB/scenario_builder.py` (+ `scenario_composition.py`) | reads `/tmp/opencode/rw_cfg.txt` |

## 3. Recommended RL Boundary

Replace the module that decides **WHO / WHAT TASK / WHICH TARGET**:

- Class: `ThreatAllocator` — `agent_hybrid_v5.py:1718`
- Method: `allocate_usvs(tracks, usvs, usv_map, now, intent=None, return_margin=False, candidates=None)` — `agent_hybrid_v5.py:1798`
- Input: `tracks` = `{name: EnemyTrack}` (belief), `usvs` = live USV unit list from `/status`, `usv_map` = `usv_ctrl.targets` (`{usv_name: track_name|None}` = current commitment), `now` (sim s), optional `intent` (`StrategicIntent`, :804)
- Output: `{target_name: [usv_names]}` (target → assigned interceptors)

An RL policy should produce the **same semantic output** (`{target: [platform_ids]}`), so the
rest of the stack (USVController / UAVManager / ActionSafety / executor) is untouched.
No RL wrapper exists today → the adapter is `PROPOSED INTERFACE / NEEDS WRAPPER`.

## 4. Simulator / Environment Files

| Item | Path | Use |
|---|---|---|
| Backend entry | `hsystem/simserver/base_server.py` | spawns sim_server workers (`--simserver_num 3`) |
| Sim server | `hsystem/simserver/sim_server.py` | loads scenario text → `temp.py`, calls `temp.sim()` |
| HTTP bridge | `hsystem/pomdp_api/main.py` | all HTTP endpoints |
| Scenario script (loaded per game) | `hsystem/sim_script/20250819TZB/scenario_composition.py` | read cfg → `build_scenario(...)` |
| Scenario builder | `hsystem/sim_script/20250819TZB/scenario_builder.py` | builds engine, deploys units, seeds RNG per game |
| Per-game config file | `/tmp/opencode/rw_cfg.txt` (env `RW_CFG_FILE`) | `seed wu wuv bu buv frontage oob profile` |
| Verified start command | `bash /tmp/opencode/start_services.sh` | launches base_server + pomdp_api; health = `GET /health` (200) |

## 5. Environment Lifecycle

Real flow (per `agent_hybrid_v5.py:AgentMain.run` :2963 and `pomdp_api/main.py`):

| Step | Endpoint / action |
|---|---|
| start game | `POST /start?script_name=scenario_composition` (v5 `ApiClient.start` :155) |
| status | `GET /status` (resource snapshot, unit states, intel, 局内时间, ended flag) |
| legal actions | `GET /legal_actions` (actions grouped by type: `[move] [lock] [launch_uav] [fly] [land_uav]`) |
| decide+act | parse obs → allocate → controllers → `ActionSafety.filter` → `POST /apply {"actions":[...]}` |
| reset / new game | `POST /reset` exists (`pomdp_api/main.py:1517`) |
| stop | `GET /stop` (`v5:170`) |
| result | `GET /result` (authoritative result + 奖励信号) |
| game log | `GET /game_log` |

**Timing model (critical):** the engine is stepped by the simulator server; in
`build_scenario` it calls `engine.set_ratio(100)` (100× real time). On the API side
`POST /apply` **advances one macro step**: it injects the actions, then sets
`release_until_time = current_time + MACRO_STEP_DURATION` (`MACRO_STEP`, default **30 s**
sim; `pomdp_api/main.py:87,1779-1783`). So the de-facto control cadence is **one agent
decision ≈ every ~30 s sim**, gated by `/apply` + a release window — it is NOT free-running
continuous time, and `/apply` DOES drive the coarse time advancement (macro-step). An RL env
should keep the same "apply → advance one macro step" synchronisation.

## 6. Observation Available to RL (legal, actually read by current code)

All from `GET /status` parsed by `Obs` (`agent_hybrid_v5.py:203`) plus belief built by
`TrackManager`/`EnemyTrack` (`:458`/`:293`).

Friendly platforms (`资源快照.单位状态.white_usv_states` / `.white_uav_states`; fields the
code dereferences: `name, position, is_alive, is_locking, locking_unit, is_frozen, battery,
home_name, is_at_usv`):
- USV: id, position, alive, locking flag + `locking_unit`, frozen flag, battery, current state (`USVController.state`)
- UAV: id, position, alive, `is_at_usv` (docked), battery, state (`UAVManager.state`), `home_name`

Enemy tracks (belief `EnemyTrack`, built only from radar capture / passive alarm):
- track id (`name`), `is_ship` (from public name), estimated position (`last_position` /
  `predicted_position(now)`), `last_velocity`, `last_seen_time` → `age(now)`, `is_visible(now)`,
  `confidence`, `point_confidence`, `maneuver_score`, `uncertainty_radius`,
  `heading`, `engaged` (≥1 USV locking), `assigned_usvs`
- raw intel in `/status`: `雷达捕获` (active: `{name, position, velocity}`), `被动告警`
  (passive: `{name, bearing, detected_by}`)

Global:
- sim time (`局内时间`), `已结束`, `对局结果`
- fleet counts (`usv_total/alive, uav_total/alive/flying, enemy_visible`) — `Obs` :214-219
- mission state (`MISSION_NORMAL/GLOBAL_REACQUIRE/TERMINAL`, v5 :128, `_compute_mission` :2752)
- coverage map (`CoverageMap` :600), resource state (`FriendlyResourceState` :673)
- existing commitments: `usv_ctrl.targets` (`{usv → target|None}`)

Legal actions (`GET /legal_actions`, `LegalSet` :237) expose an **implicit action mask** at the
primitive level (can_move/can_lock/can_launch/can_fly/can_land). There is **no
RL-level assignment mask** yet (`NEEDS RL WRAPPER`).

## 7. Forbidden Observation / Fair-Play Boundary

Forbidden for any actor policy (including RL): ground-truth enemy positions, hidden Black
waypoints / selected lanes, Black policy internals (B3 `b3_plan`), future trajectories,
scenario hidden truth, seeds, evaluation-only truths (victory/breakthrough counts during play).

Real enforcement artifacts:
- `test_opponent_profiles.py` — hidden-truth counterfactual (identical legal obs ⇒ identical
  action), White-internal-state mask, variable-cardinality stress
- `test_w6_units.py` (T9) — same legal obs, different hidden truth ⇒ identical W6 output
- Black observation boundary: `opponent_profiles.py` reads only `get_black_targets()` (Black
  radar intel) + own units
- Static leakage greps in the tests above; runtime audits under `runtime_audit/`
- `maritime_metrics.py` is an **evaluator-side** collector (accounting only, never feeds the agent)

## 8. Recommended RL Action Space

Real task vocabulary (from the BT contract, `bt_harness_interface.py`):

- `TaskType` (:43): `INTERCEPT_LOCK` (USV), `ENGAGE_TARGET` (USV), `HOLD_POSITION` (both),
  `COOPERATIVE_LOCK` (UAV), `SITUATION_UPDATE` (UAV), `RETURN_RECHARGE` (UAV)
- `PlatformType` (:38): `USV`, `UAV`

Suggested RL action form (wrapper-level, mirrors the allocator output + task type):

```
(platform_id, task_type, target_id)     # USV: INTERCEPT_LOCK/ENGAGE_TARGET, target=enemy track
                                        # UAV: COOPERATIVE_LOCK/SITUATION_UPDATE/RETURN_RECHARGE, target may be empty
```

`PROPOSED INTERFACE — NOT CURRENTLY IMPLEMENTED` (no RL wrapper exists in the repo).

## 9. TaskCommand / PlatformExecutive Contract

All in `bt_harness_interface.py` (dataclasses + ABC) and `bt_real_trees.py` (real trees):

| Item | Path |
|---|---|
| `TaskCommand` | `bt_harness_interface.py:141` (task_id, platform_id, platform_type, task_type, target_id, role, revision, priority, valid_from/until, preemptible, safety_override, allow_local_reacquire, max_search_time, constraints) |
| `TaskAck` | `:162` |
| `CancelTaskRequest` | `:171` |
| `ActionRequest` | `:178` (intent-level: action_kind/target/waypoint/course/speed/meta) |
| `TaskFeedback` | `:193` |
| `ExecutionContext` | `:206` (legal snapshot only — no ground truth) |
| `BTStepResult` | `:223` |
| `PlatformExecutive` (ABC) | `:235` — `submit_task()`, `cancel_task()`, `tick()` |
| `BTPlatformExecutive` | `:427` |
| `BTActionAdapter` | `:556` |
| Real trees/bridge | `bt_real_trees.py` |

Contract rules that matter for RL: **Harness owns WHO + WHAT (platform/target/task)**, BT owns
**HOW (phase)**, target_id is immutable once assigned (local reacquire keeps target; timeout →
`need_reallocation`), and in `HARNESS_BT_MODE` the only simulator writer is the Harness
`POST /apply` (`bt_harness_interface.py:252`, `:549`).

## 10. Action Mask / Legal Assignment

- Primitive-level legality exists: `LegalSet` (`agent_hybrid_v5.py:237`) + `ActionSafety.filter`
  (`:2496`) double-check every primitive (dead/busy/frozen/lock-valid/etc.).
- **RL-level assignment mask: `NEEDS RL WRAPPER`.** A future wrapper should mask out:
  dead platforms; platforms already committed (`usv_ctrl.targets` not None); invalid
  platform↔task compatibility (task_type↔PlatformType); invalid/dead targets; UAV battery /
  dock constraints; and honour active lock/engagement commitments (don't preempt a kill chain).

## 11. Reward and Termination Signals

Real signals available (evaluator/simulator truth):
- `GET /result` (`pomdp_api/main.py:1819`) → `对局结果` (`Result.Victory`/`Result.Defeat`),
  `奖励信号`, `结果说明`; Obs `reward` keys: `black_killed`, `black_hit`,
  `white_ship_killed`, `white_uav_killed`, `black_breakthrough` (`agent_hybrid_v5.py:229-234`)
- `maritime_metrics.py` (`GameMetricsCollector`) — explored area, unit deaths, enemy terminal
  classification; used by the evaluation runners
- `[META]` line printed at end of each game (`victory_time, enemy_kills,
  friendly_usv_losses, black_breakthrough, ...`) parsed by the runners

Clear split: these are **TRAINING-REWARD / EVALUATION-TRUTH** sources. They must NOT enter the
actor observation during play. `CURRENT REWARD IS NOT YET AN RL REWARD DESIGN` — the reward
signals are game-level counters, not shaped RL rewards; the RL teammate should design shaping
but keep hidden truth out of the observation.

## 12. Existing Opponents

- `opponent_profiles.py` — constants `B0_RANDOM..B4_DOCTRINE_MIX` (:26-30), `PROFILES` (:31),
  `b3_plan` (:192); B0 = legacy random-waypoint baseline.
- Ladder doc/state: `opponent_eval/OPPONENT_LADDER_REPORT.md`,
  `opponent_eval/opponent_profile_manifest.json`; smoke: `opponent_smoke.py`.
- Formal B0-vs-B3 evaluation: `run_opponent_formal.py` → `opponent_formal_eval/`; post-processing
  `opponent_finalize.py`, `opponent_pressure_from_log.py`.
- **B4_DOCTRINE_MIX status:** declared constant + listed in the manifest as a seed-driven
  doctrine mix "recorded evaluator-side, invisible to White", but it is **NOT part of the
  formal B0/B3 evaluation and was not used as a live evaluated profile** (smoke ran B0–B3).
  Treat as NOT FULLY IMPLEMENTED / optional for now.
- Advice: for RL training use an opponent population; keep formal test profiles/seeds isolated.

## 13. Existing Scenario Scales

Real scale table (same in `run_formal_eval.py:40-43` and `w6_dev_runner.SCEN`):

| Scale | White | Black |
|---|---|---|
| S1 | 5 USV + 5 UAV | 10 Black USV |
| S2 | 10 + 10 | 20 |
| S3 | 15 + 15 | 30 |

- Scenario builder: `hsystem/sim_script/20250819TZB/scenario_builder.py`
  (`build_scenario(white_usv_count, white_uav_count, black_usv_count, ..., rw_seed=..., opponent_profile=...)`)
- Per-game config writer: `w6_dev_runner.py:88-89`, `run_formal_eval.py:93-96`
  (`/tmp/opencode/rw_cfg.txt`: `seed wu wuv bu buv frontage oob profile`)
- Runner scale args: `run_formal_eval.py --scenario S1`, `w6_dev_runner.py --sanity/--dev/--ablation`

## 14. Seed Splits (as actually used)

| Range | Use | Where recorded |
|---|---|---|
| 1001–1030 | historical formal eval + formal B0 vs B3 (paired) | `formal_eval_20260825/config_manifest.json`, `opponent_formal_eval/config_manifest.json` |
| 1101–1103 | BT integration (1101 confirmed in `bt_port_eval/integration_results.csv`, `bt_port_logs/S1_B0RANDOM_s1101.log`) | `bt_port_eval/`, `bt_regression_eval/` |
| 1201–1205 | BT semantic regression paired (N=30 episodes) | `bt_regression_eval/paired_regression_30.csv` |
| 2001–2005 | W6 anti-evasion DEV (sanity 2001–2003) | `w6_anti_evasion/`, `white_harness_versions.jsonl` |
| 4001–4010 | co-evolution FINAL holdout (in active use) | `coevolution_final/config_manifest.json`, `coevolution_final/final_episode_results.csv` |
| ep4_… | Skill-evolution runtime-audit runs | `runtime_audit/run_ep4_1787234142` |

**Warning:** these ranges have been used for DEV/evaluation; they must NOT be treated as fully
unseen RL test seeds. `RL TRAIN/DEV/TEST SPLIT NOT YET DEFINED` — the RL teammate should define
fresh splits and keep them out of all prior ranges.

## 15. Existing Baseline Allocator

- Frozen baseline White: `agent_hybrid_v5.py` (W5). Runtime versioned as `W5` in
  `white_harness_versions.jsonl`; policy legacy hash `a7842b29…` (runtime file = legacy +
  inert W6 hook `_w6_intercept`, None-default → identical W5 behaviour).
- Allocator: `ThreatAllocator` (`agent_hybrid_v5.py:1718`),
  `allocate_usvs(tracks, usvs, usv_map, now, intent=None, return_margin=False, candidates=None)`
  → `{target_name: [usv_names]}`. Greedy marginal-gain concentration (1v1→2v1/3v1 by value),
  reserve kept via `intent.reserve_ratio`, low-confidence commitment guard, threat scoring
  (`threat_score` :1749), enemy-UAV excluded from USV assignment.
- Usage in the loop: `agent_hybrid_v5.py:2824-2827`.
- **Recommended comparison:** deterministic W5 `ThreatAllocator` vs the RL allocator, with
  simulator/controller/physics/opponent/observation boundary all frozen, so results attribute
  to the assignment policy only.

## 16. Existing Evaluation Tools

| Tool | Path | Purpose / supported metrics |
|---|---|---|
| Formal 3-scale runner | `run_formal_eval.py` → `formal_eval_20260825/` | N=30/scale, clean win / kills / loss / breakthrough / explored / resolution |
| Formal B0-vs-B3 runner | `run_opponent_formal.py` → `opponent_formal_eval/` | paired B0/B3, pressure metrics, failure cases |
| Metrics collector | `maritime_metrics.py` (`GameMetricsCollector`) | explored area, deaths, terminal accounting |
| Opponent smoke | `opponent_smoke.py` | profile sanity |
| W6 DEV/ablation runner | `w6_dev_runner.py` → `w6_anti_evasion/eval/` | mechanism fire-check, ablation |
| Co-evolution FINAL | `coevolution_final/final_runner.py`, `analyze.py`, `watchdog_finalize.py` | 3-stage paired (S1–S3 × Stage0-2 × 4001–4010), bootstrap CIs |
| Failure-case + paired CSVs | inside `formal_eval_20260825/`, `opponent_formal_eval/`, `bt_regression_eval/`, `coevolution_final/` | logs/failure_cases.csv |

Stably supported metrics: clean win rate, enemy kills, friendly USV loss, breakthrough,
explored area (km²), resolution time (s) — consistent across the runners via `[META]` +
`maritime_metrics`.

## 17. Minimum Handoff Set

### A. REQUIRED (RL must have)
- `agent_hybrid_v5.py` — frozen W5 baseline + all White modules (ApiClient/Obs/LegalSet/
  TrackManager/EnemyTrack/ThreatAllocator/USVController/UAVManager/ActionSafety/AgentMain)
- `hsystem/pomdp_api/main.py` — HTTP API (endpoints/schema)
- `hsystem/simserver/` (base_server, sim_server, http_server, sim_client, temp.py) — backend
- `hsystem/sim_script/20250819TZB/scenario_builder.py` + `scenario_composition.py` — scenario
- `/tmp/opencode/start_services.sh` — startup (or equivalent documented commands)
- `agent_hybrid_v5.py` Observation/LegalSet parsing (how to read `/status` & `/legal_actions`)

### B. RECOMMENDED (baseline + evaluation)
- `run_formal_eval.py` + `formal_eval_20260825/` (baseline numbers + runner template)
- `run_opponent_formal.py` + `opponent_formal_eval/` (opponent comparison pattern)
- `maritime_metrics.py` (exploration/death instrumentation pattern)
- `opponent_profiles.py` (opponent population)
- `bt_harness_interface.py` (TaskCommand/PlatformExecutive contract) as the executor contract reference
- `skills/maritime_commander/SKILL.md` (doctrine context; frozen hash `155b0201…`)

### C. NOT NEEDED INITIALLY
- Skill-evolution pipeline (`skill_evolution.py`, `skill_evolution_runs/`)
- LLM Commander experiments (LLMCommander layers, `commander_audit_seed.json`)
- BT regression/report artifacts (`bt_regression_eval/`, `bt_port_eval/`, `bt_real_trees.py` unless the executor contract is needed)
- W6 anti-evasion development (`anti_evasion/`, `agent_hybrid_w6.py`, `w6_anti_evasion/`,
  `coevolution_final/`) — the W6/co-evolution work is a later adaptation; the RL entry point is W5's allocator

## 18. Recommended Future RL Wrapper (design only — NOT IMPLEMENTED)

```python
class MaritimeAllocatorEnv:          # PROPOSED — NOT IMPLEMENTED
    def reset(self, seed, config): ...      # POST /start?script_name=..., read /status, /legal_actions
    def get_observation(self): ...          # legal belief + resource + mission (Section 6)
    def get_action_mask(self): ...          # platform alive / uncommitted / task-target valid (Section 10)
    def step(self, allocation_action): ...  # allocation_action = {target: [platform_ids]} or list of (platform, task, target)
                                            #   → existing executor (USVController/UAVManager) → ActionSafety → POST /apply
                                            #   → next legal observation
```

`allocation_action` only expresses **platform-task-target assignment**; the wrapper keeps
calling the existing executor/controller/ActionSafety. Reward is computed from
`/result` 奖励信号 / `maritime_metrics` (never fed back into the observation).

## 19. Suggested RL Observation / Action Contract (proposal)

- Observation: legal track belief (`position/velocity/confidence/age/uncertainty/visible/
  engaged`) + friendly platforms (`position/alive/state/battery/commitment`) + mission/time.
- Action: assignment `(platform_id, task_type, target_id)` per free platform (or an assignment
  matrix over candidate targets).
- Executor: existing deterministic execution layer (controllers + BT phase if used + ActionSafety).
- Reward: simulator/evaluator truth only (e.g. kill/loss/breakthrough/resolution shaping), hidden
  truth never exposed to the actor.

## 20. Quick Start for Teammate

All commands verified on this machine:

```bash
PY=/root/miniconda3/envs/hsystem_env/bin/python
cd /root/autodl-tmp/hsystem

# 1) start simulator + API (background)
bash /tmp/opencode/start_services.sh
# health check
$PY - <<'PY'
import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health').status)
PY

# 2) run one baseline game (harness-only = LLM off)
printf "1001 5 5 10 0 fixed_frontage 1.0 B0_RANDOM" > /tmp/opencode/rw_cfg.txt
SCENARIO_SCRIPT=scenario_composition LLM_ENABLED=false $PY agent_hybrid_v5.py --uavs

# 3) read legal observation in-process (or replicate Obs parsing)
#    GET /status, GET /legal_actions, POST /apply {"actions":[{"action_text":...,"action_type":...}]}

# 4) run a full baseline episode + metrics (formal runner, one seed)
$PY run_formal_eval.py --scenario S1 --seeds 1001

# 5) find the allocator to replace
#    ThreatAllocator.allocate_usvs  -> agent_hybrid_v5.py:1798

# 6) RL replaces the allocator call at agent_hybrid_v5.py:2824 (or a wrapper reimplements
#    the same allocate step and feeds the returned {target:[usv]} into usv_ctrl.step)
```

There is **no single one-click "RL" entry** yet; the above is the minimal real flow.

## 21. Known Interface Caveats (affect RL env design)

- `/apply` advances one macro step (~`MACRO_STEP` = 30 sim-s default) and sets a release window;
  it does not gate sub-macro continuous physics — synchronise RL steps to the same cadence.
- Engine runs at 100× sim ratio (`engine.set_ratio(100)` in `scenario_builder.py`); wall time per
  macro step is small but variable.
- Enemy tracks are sticky: `EnemyTrack.age/is_visible` thresholds and freeze/stale semantics
  (`FROZEN_DURATION`, corpse detection) determine whether a target is assignable.
- Lock semantics: a USV entering `LOCKING` holds the kill chain; a safe allocator must not strip
  a locking USV from its target mid-chain.
- UAV sensing is shared/cooperative (search/screen/reacquire roles; battery/dock constraints);
  UAV tasks are not the same as USV intercept tasks.
- `ActionSafety` enforces single-writer per unit per step and one action per unit; `noop` is the
  safe fallback when nothing is legal.
- BT route: target_id immutable once assigned; task persists across ticks; the only simulator
  writer is Harness `/apply` (`HARNESS_BT_MODE`).
- The sim shows **run-level nondeterminism** beyond the scenario RNG seed (verified: same seed,
  same code → different outcomes across runs). A single run is a noisy draw; use
  N≥10 with bootstrap CIs (see `coevolution_final/RNG_NONDETERMINISM.md`).
- No RNG/game state is exposed to the White agent beyond `/status` intel — don't try to recover
  hidden truth from any endpoint.

## 22. Recommended Experiment Contract

Compare:

```
Deterministic W5 ThreatAllocator   vs   RL Allocator
```

with everything else frozen: simulator physics, opponent profile, USV/UAV controllers,
TaskCommand interface (if BT executor used), ActionSafety, observation boundary, scenario
builder. Then any delta attributes to the **assignment policy** only.

## 23. Final Checklist

- [x] Simulator files identified (`hsystem/simserver/`, `hsystem/simulation/core/`)
- [x] Startup path identified (`/tmp/opencode/start_services.sh`, `hsystem/pomdp_api/main.py`)
- [x] Observation schema identified (`/status`, `LegalSet`, `EnemyTrack`, `Obs`)
- [x] Fair-play boundary identified (`test_opponent_profiles.py`, `test_w6_units.py` T9)
- [x] Current allocator identified (`ThreatAllocator.allocate_usvs`, `agent_hybrid_v5.py:1798`)
- [x] TaskCommand schema identified (`bt_harness_interface.py:141`, `PlatformExecutive:235`)
- [x] Action legality identified (`LegalSet`, `ActionSafety.filter`)
- [x] Reward / termination identified (`/result`, `奖励信号`, `maritime_metrics.py`)
- [x] Opponent profiles identified (`opponent_profiles.py` B0–B4)
- [x] Scenario scales identified (`run_formal_eval.py:40`, `w6_dev_runner.SCEN`)
- [x] Existing baseline identified (`agent_hybrid_v5.py` W5 frozen)
- [x] Evaluation runner identified (`run_formal_eval.py`, `run_opponent_formal.py`)
- [x] Minimum handoff file set identified (§17)
- [x] Proposed RL boundary documented (§3, §8, §18)
