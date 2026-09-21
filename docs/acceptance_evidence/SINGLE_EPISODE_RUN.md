# Single Episode Run (canonical W5)

- scenario: S2 (scenario_composition, 10 USV + 10 UAV vs 20 Black)
- opponent_profile: B0_RANDOM
- seed: 1001
- LLM_ENABLED: false
- runner: scripts/acceptance/run_single_w5.py (reuses run_opponent_formal.run_one)
- command: `/root/miniconda3/envs/hsystem_env/bin/python scripts/acceptance/run_single_w5.py`

## Result
```
{
  "experiment_id": "ACCEPTANCE",
  "scenario": "S2",
  "scale": "S2",
  "opponent_profile": "B0_RANDOM",
  "seed": 1001,
  "friendly_usv_initial": 10,
  "friendly_uav_initial": 10,
  "enemy_combat_usv_initial": 20,
  "enemy_uav_initial": 0,
  "result": "Result.Victory",
  "victory": 1,
  "clean_win": 1,
  "failure_reason": "clean",
  "sim_time": 13663.0,
  "wall_time": 307.2,
  "friendly_usv_alive": 6,
  "friendly_usv_dead": 4,
  "friendly_uav_alive": 10,
  "friendly_uav_dead": 0,
  "friendly_total_dead": 4,
  "enemy_combat_killed_event": 20,
  "enemy_combat_killed_terminal": 20,
  "enemy_combat_alive_end": 0,
  "kill_accounting_mismatch": 0,
  "enemy_breakthrough_count": 0,
  "enemy_oob_count": 0,
  "timeout": 0,
  "explored_area_km2": 68725.0,
  "explored_ratio": 0.3555,
```

## [META]
```
[META] result=Result.Victory victory_time=13663 first_detection=1854 first_lock=7372 first_kill=8308 enemy_kills=20 friendly_usv_losses=4 friendly_uav_losses=0 black_breakthrough=0 reacquire_attempts=55 reacquire_success=55 sensor_assisted_locks=57 low_conf_commitments=0 global_reacquire_entries=0 global_reacquire_success=0 coverage_collapse_events=1 active_clusters_max=1 coverage_quality_final=0.
```

## stdout excerpt (first 12 representative lines)
```
HYBRID AGENT V5 — Variable-Cardinality Hierarchical Maritime Agent
对局 1 开始
[t=185s] step=10 | MISSION=NORMAL_C | USV: 10/10 (avail=10 int=0 lock=0 frz=0) | UAV: air=10 rtb=0 chg=0 loiter=0 | TRACKS: vis=0 lost=0 engaged=0 | TOP:  | KILL=0 | ACTIONS=20 | INTENT: focus=2 ratio=0.20
[t=398s] step=20 | MISSION=NORMAL_C | USV: 10/10 (avail=10 int=0 lock=0 frz=0) | UAV: air=10 rtb=0 chg=0 loiter=0 | TRACKS: vis=0 lost=0 engaged=0 | TOP:  | KILL=0 | ACTIONS=20 | INTENT: focus=2 ratio=0.20
[t=614s] step=30 | MISSION=NORMAL_C | USV: 10/10 (avail=10 int=0 lock=0 frz=0) | UAV: air=10 rtb=0 chg=0 loiter=0 | TRACKS: vis=0 lost=0 engaged=0 | TOP:  | KILL=0 | ACTIONS=20 | INTENT: focus=2 ratio=0.20
[t=834s] step=40 | MISSION=NORMAL_C | USV: 10/10 (avail=10 int=0 lock=0 frz=0) | UAV: air=10 rtb=0 chg=0 loiter=0 | TRACKS: vis=0 lost=0 engaged=0 | TOP:  | KILL=0 | ACTIONS=20 | INTENT: focus=2 ratio=0.20
[t=1,058s] step=50 | MISSION=NORMAL_C | USV: 10/10 (avail=10 int=0 lock=0 frz=0) | UAV: air=10 rtb=0 chg=0 loiter=0 | TRACKS: vis=0 lost=0 engaged=0 | TOP:  | KILL=0 | ACTIONS=20 | INTENT: focus=2 ratio=0.20
[t=1,275s] step=60 | MISSION=NORMAL_C | USV: 10/10 (avail=10 int=0 lock=0 frz=0) | UAV: air=10 rtb=0 chg=0 loiter=0 | TRACKS: vis=0 lost=0 engaged=0 | TOP:  | KILL=0 | ACTIONS=20 | INTENT: focus=2 ratio=0.20
[t=1,510s] step=70 | MISSION=NORMAL_C | USV: 10/10 (avail=10 int=0 lock=0 frz=0) | UAV: air=10 rtb=0 chg=0 loiter=0 | TRACKS: vis=0 lost=0 engaged=0 | TOP:  | KILL=0 | ACTIONS=20 | INTENT: focus=2 ratio=0.20
[t=1,740s] step=80 | MISSION=NORMAL_C | USV: 10/10 (avail=10 int=0 lock=0 frz=0) | UAV: air=10 rtb=0 chg=0 loiter=0 | TRACKS: vis=0 lost=0 engaged=0 | TOP:  | KILL=0 | ACTIONS=20 | INTENT: focus=2 ratio=0.20
      [DETECT] black_usv8
      [DETECT] black_usv3
```

- agent log: docs/acceptance_evidence/run/logs/S2_B0_RANDOM_s1001.log
- runtime_audit: runtime_audit/ (per-run manifest; see LOGGING_REFERENCE.md)
