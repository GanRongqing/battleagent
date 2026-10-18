# 10 — IMPLEMENTATION DIFF
File: `agent_hybrid_v5.py` (TrackManager only).
+ `__init__`: `self._lc_enabled = os.getenv("TARGET_LIFECYCLE_V2","0")=="1"`, `self.lifecycle`,
  `self.lifecycle_log`.
+ `_lc_set(name,state,event,source)`: deduped transition/audit record.
+ `update()`: on positioned active obs -> `OBSERVED_ACTIVE`; if name in `killed_names` ->
  `DEATH_EVIDENCE_CONFLICT` (surfaces the defect). On passive -> `OBSERVED_BEARING`.
+ `kill_detect()`: on inference -> `SUSPECTED_DEAD` (never `CONFIRMED_DEAD`).
No change to tracks, killed_names, `_KILLED`, assignments, actions, engine, Black, scenarios.
`_KILLED` cross-episode reset remains a documented latent issue (not changed; out of minimal scope).
