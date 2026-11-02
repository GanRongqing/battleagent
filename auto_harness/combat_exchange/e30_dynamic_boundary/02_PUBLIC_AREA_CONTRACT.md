# 02 — PUBLIC OPERATIONAL-AREA CONTRACT (legal, scenario-agnostic)
- Engine state (`engine.get_all_state` / `tzb_engine.get_state`) now includes
  `public_area = [[x,y], ...]` taken from `judge.area.exterior.coords` (exactly the judge's polygon).
- `GET /status` exposes `"公开地图": {"作战区域": [[x,y],...]}`.
- `Obs.public_area` parses it. No scenario id/name/seed/enemy info is included.
- Format is identical for all scenarios (list of vertices, metres, Cartesian); removing scenario names does not
  change anything. `judge`/scoring/engine rules are NOT modified — only a new public field is added.
- Missing/invalid area → the safety layer marks the episode `safety-unavailable` and does NOT fall back to any
  hardcoded rectangle (it leaves actions unchanged and reports the reason).
