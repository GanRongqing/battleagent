# 01 — OBSERVATION DATA FLOW
| layer | source code | input | output | notes |
|---|---|---|---|---|
| Sim raw state | `sim_server` engine | — | `raw` dict incl `white_observation`, `white_usv_states`, `time` | radar capture + per-unit state |
| Intel builder | `hsystem/pomdp_api/main.py::_analyze_intel` (l.680) | `raw["white_observation"]` | `{"active":[{name,position,velocity}], "passive":[{name,bearing,...}]}` | active = radar capture w/ position; passive = bearing-only from `locked_attacker` |
| HTTP `/status` | `main.py::get_status` (l.1685) | intel | `资源快照.观察信息.white_observation.雷达捕获/被动告警` | **same `intel["active"]`** |
| Game log step | `main.py::_record_step`→`_make_game_log_step` (l.375/431) | `raw` (POST-advance) | `active_enemies=intel["active"]`, `passive_enemies=intel["passive"]` | recorded after `/apply` advance |
| Parser | `agent_hybrid_v5.py::Obs` (l.225-227) | `/status` 雷达捕获/被动告警 | `obs.active`, `obs.passive` | verbatim copy, no transform |
| TrackManager | `agent_hybrid_v5.py::TrackManager.update` (l.465) | `obs.active`/`obs.passive` | `tracks{name→EnemyTrack}` | **skips `killed_names` (l.474-475)** |
| Controller | `USVController.step` (l.2002) | `tracks` | actions | uses `tracks`, not `obs.active` |
KEY: game-log `active_enemies` and `/status` 雷达捕获 are produced by the **same function** from the
**same raw** → the game log is the legal observation, NOT engine truth.
