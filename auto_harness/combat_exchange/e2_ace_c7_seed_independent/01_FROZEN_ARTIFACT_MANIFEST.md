# 01 — FROZEN ARTIFACT MANIFEST (E2)

| artifact | value |
|---|---|
| Git commit (repo /root/autodl-tmp/githsysys) | d8329c4 |
| ACE source SHA256 | 7527253c6d5a4bba198e478a990443354ecf5d8cf4e1c98ace66ce50dc809497 |
| C7 source SHA256 | 98b655e86a4f632c85e8a96023c966d39bedb636a4a469451a1548787efd8f98 |
| Engine source bundle SHA256 (base_engine.pyx, locker.py, judge_system.py, radar.pyx, motor.pyx) | a21ad9af7d5234137f63e230a97eb8fae28c072407e8dacb8f69c431d9dae5f4 |
| Compiled extension bundle SHA256 (base_engine/radar/motor .so) | dde30e04907d57bcbc485c2dc4129449ae2ac334dcb0c209a373cfa54c62a416 |
| Opponent+scenario bundle SHA256 (sces.json + 4 plan .py) | 2152d3692048809850494b9006a3a5ce0e1fdb8f4fcc434886557f561a0c6245 |
| Evaluation runner bundle SHA256 (run_e2_eval.py, run_agent_wrapper.py) | 3586ea62c10f8ea1fa54950f68c7a34ff7181e05df779c2ff67f1c1213132504 |
| Seed plumbing config | svc.sh: RW_SEED_FILE=/tmp/opencode/seed_w0.txt ; PYTHONHASHSEED=0 |

Frozen policy: ACE, C7, Black, TrackManager, ThreatAllocator, USVController, ActionSafety, legality,
sensors, weapons, routes, Locker probability semantics, deterministic stepping, seed plumbing.
If any of the above changes mid-run -> EVALUATION_EPOCH_CONTAMINATED (STOP).
