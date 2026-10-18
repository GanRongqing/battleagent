# 00 — FREEZE AND SCOPE (E5)
- Git HEAD: `f492e89`; working tree clean at start.
- ACE `7527253c…`, C10 `886577b5…`, C11 `07d1ffa9…`, TrackManager host `agent_hybrid_v5.py` `eb6d5341…`,
  engine `locker.py` `130f9c65…` (unchanged).
- `OBS_TI_REVIVE` default = **"0"** (OFF), `agent_hybrid_v5.py:480` (unchanged).
- E4 data: `auto_harness/combat_exchange/e4_observation_revival/` (13 real episodes, seed 43001).
- E4 main table cross-checked against raw result JSONs — consistent (real, not SUMMARY_ONLY).
- Scope: read-only audit + offline verifier + tests. No production change, no C12, no full re-eval.
