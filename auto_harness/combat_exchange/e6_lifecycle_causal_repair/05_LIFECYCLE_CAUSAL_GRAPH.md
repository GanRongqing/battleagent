# 05 — LIFECYCLE CAUSAL GRAPH
```
legal radar obs (obs.active, position)  --active=>alive (entity.pyx/radar.pyx)-->
   |
kill_detect: engaged_missing (black-kill delta) / corpse(stationary>=CORPSE_AGE)
   |  (FALSE_DEATH on a live target, e.g. usv13 @7800)
   v
killed_names / _KILLED  ----(OFF)----> TrackManager suppresses target -> allocator never sees it
   |                                  -> (winning W2-4 path preserved)
   |----(ON: OBS_TI_REVIVE)----------> track restored -> allocator sees a live target
                                       -> assignment changes @8160 -> action @8160 -> outcome 9/20
```
Evidence levels:
- `kill_detect -> killed_names`: **DIRECT_DATA_DEPENDENCY** (write in kill_detect, read in update).
- `killed_names -> track suppression`: **DIRECT_DATA_DEPENDENCY** (update l.474).
- `track -> allocator -> action`: **DIRECT_DATA_DEPENDENCY** (allocate_usvs over tracks; controller step).
- `kill(260) -> revive(261) -> assign/action(272)`: **TEMPORAL_ASSOCIATION** + **COUNTERFACTUAL_CONFIRMED**
  (OFF/ON pair differs exactly along this path; same seed/engine).
- The **combat sign** of restoring a live target is downstream: a data-correct restore is tactically
  harmful here. That is an INTERFACE-SEMANTICS issue, not a truth/lifecycle correctness issue.
