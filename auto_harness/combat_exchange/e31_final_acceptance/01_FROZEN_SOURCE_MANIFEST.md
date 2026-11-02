# 01 — FROZEN SOURCE MANIFEST
- Base commit (E30): `d82d9fc`
- Candidate: **C31 / white-combat-0031-v1**, entry `agent_hybrid_c31.py`
- Safety: `scenario_agnostic_safety.py`, `BUFFER = 5_000.0` (line 26), real public polygon, no hardcoded W2 box.
- Engine hash from `/start`: `a509457250bc2799` (all 13 episodes)
- Python: `/root/miniconda3/envs/hsystem_env/bin/python`
- Runner: `auto_harness/evaluation/parallel_runner/parallel_runner.py` (STRATS includes W2-1..6,S10,S15,S20,S30,S10RW,EXTD,EXTT)
- Worker: 3 workers, independent ports, E9 identity, E15 manifest.
- Public area channel: engine `judge.area` → `public_area` → `/status.公开地图.作战区域` → `Obs.public_area`.
- This round only added behavior-neutral counters (current_out/preventive/unexpected); tactics unchanged; verified by identical 13/13 K/L to E30.
| artifact | sha256 (first 16) |
|---|---|
| agent_hybrid_c31.py | cf7ac611dba48c99 |
| scenario_agnostic_safety.py | 6a6fcae54f7c2a7f |
| agent_hybrid_split_screen.py | 1438639a0b83f9f6 |
| agent_hybrid_safe_recon.py | a4b6246cbc6334a2 |
| agent_hybrid_fleet_recon.py | 833c28e3ae0f9c8e |
| hsystem/pomdp_api/main.py | 0fae2e789bf20558 |
