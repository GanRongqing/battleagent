# 01 — MINIMAL INTERFACE CONFLICT (W2-4 steps 260–272, from E6 trace)
Reused E6 traces `/tmp/opencode/e6_lifecycle_causal_repair/raw_evidence/life_w24_{off,on}.jsonl`.

| Q | finding | status |
|---|---|---|
| Q1 which downstream interface first receives the different state | Track set handed to the allocator/controller: at step 261 OFF tracks exclude `usv13`, ON include it | CONFIRMED |
| Q2 does the change overwrite/reset existing task records | No evidence of task-record reset; the change is a track-set difference. Assignment divergence appears at step 272 | DISPROVED (reset) / CONFIRMED (track-set diff) |
| Q3 do `killed_names` and `_KILLED` conflict for the same target | **YES**: `OBS_TI_REVIVE` clears only `killed_names` (v5 l.498-509); `step_once` always `_KILLED.update(killed)` (l.2821), so `_KILLED` still contains `usv13` while the track is restored | **CONFIRMED (root interface violation)** |
| Q4 do consumers interpret "re-observed" as "reinitialize all decision state" | No full reset; but `_KILLED` consumers (allocator l.1837; controller release l.2057; opportunistic lock l.2143) still treat the restored live target as dead → a "zombie" track | CONFIRMED |
| Q5 contract violation | Violates Invariant 5 (inference vs confirmed must be distinguishable downstream) and the single-source requirement: two death stores disagree in the same step | CONFIRMED |

Direct evidence: E6 trace step 261 — OFF `killed_names=['usv13']`, ON `killed_names=[]`; ON track list contains
`usv13`; code path shows `_KILLED` is monotonic (never cleared on revive).
