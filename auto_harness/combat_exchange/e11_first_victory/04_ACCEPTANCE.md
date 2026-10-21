# 04 — ACCEPTANCE (same deterministic seed 43001, identity verified)
| Scenario | ACE K/L (CER) | C13 K/L (CER) | Victory | Note |
|---|---|---|---|---|
| W2-1 | 0/20 (0.000) | 0/20 (0.000) | Defeat | unchanged |
| W2-5 | 16/15 (1.067) | 16/15 (1.067) | Defeat | unchanged |
- `ended_reason`: W2-1 “我方所有单位被击毁”; W2-5 “敌方1艘艇突破防线”.
- Black breakthroughs: W2-5 = 1 (unchanged); W2-1 = all White dead.
- **No Victory achieved.**
## UAV lifecycle metric (the decisive check)
- First time all 10 UAVs are dead: W2-1 ACE `03:16:00` vs C13 `03:16:00` (identical); W2-5 ACE `04:42:00`
  vs C13 `04:42:00` (identical). **C13 is a NO_EFFECT no-op** (trajectories identical).
- Observed UAV loss: at 06:56:30 (C10 W2-5) all 10 were 12–30 km from known Black → mass-killed in one step.
=> The loss is NOT in `_global_search_fly` (C13 filtered it with no change). It occurs in another UAV role
  (SCREEN/REACQUIRE approach) or via track-visibility timing. Exact role = `NEED_INSTRUMENTATION`.
