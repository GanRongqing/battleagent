# 05 — MINIMAL INTEGRATION RESULTS (Gate C)
Config: ACE, seed 43001, frozen engine/scenario, `LIFECYCLE_HANDOFF_V1=1`, `OBS_TI_REVIVE=0`.
Deterministic step mode. 2 full trajectories (W2-4, W2-6).

| scenario | config | Black kills | White losses | ratio | steps | traj hash | comparison |
|---|---|---:|---:|---:|---:|---|---|
| W2-4 | OFF baseline | 12 | 6 | 2.000 | 1407 | c73fc6afe2dc | — |
| W2-4 | **HANDOFF=1** | **12** | **5** | **2.400** | 1407 | 67cb84f61cee | **no regression (better)** |
| W2-6 | OFF baseline | 10 | 18 | 0.556 | 991 | 279709d01258 | — |
| W2-6 | **HANDOFF=1** | **14** | **13** | **1.077** | 1328 | 38950941ba67 | **positive exchange** |
| W2-4 | E4 `OBS_TI_REVIVE=1` (old) | 9 | 20 | 0.450 | 834 | — | the old regression is gone |

Mechanism (W2-6): own-lock 13 (OFF 11), sustained windows **27** (OFF 16), max concurrency **5** (OFF 4),
prelock deaths **5** (OFF 8). W2-4: own 14, windows 24, maxC 6, prelock 1.
Reading: clearing BOTH death stores on a fresh legal observation removes the inconsistent "zombie track"
(killed_names cleared but `_KILLED` still dead), so the restored live target is engaged coherently and
losses fall sharply on W2-6 (18→13) while W2-4 improves slightly (6→5 losses).

Distinct trajectories vs baselines confirm a real behaviour change, not a logging artefact.
