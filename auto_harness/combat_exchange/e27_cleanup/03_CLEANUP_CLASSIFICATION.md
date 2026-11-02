# 03 — CLEANUP CLASSIFICATION
**Tier A (removed)**: all `__pycache__/` (1328) + `*.pyc`; `hsystem/build/` (duplicate `.so` + `.o`
objects); `/tmp/opencode/simlogs`.
**Tier B (removed, reproducible historical logs)**: `hsystem/pomdp_api/api_logs/games/*.json` (4183 files;
engine per-episode output; current C27/C30 six-scenario evidence was first compacted to gzip under
`e25.../raw_logs/games_c27` and `e26.../raw_logs/games_c30`); `/tmp/opencode/parallel_runs` (worker logs;
results JSONLs + six-scenario game logs saved into e25/e26 raw_logs first).
**Tier C (kept)**: all candidate source C1–C30, baselines C10/C19/C27/C30, skills, tests, engine code and
compiled in-place `.so` (`hsystem/simulation/**/*.so`, 5 files). No candidate code deleted.
**Tier D (protected, NOT deleted)**: `.git` (both repos), `.venv`, engine `simulation/database`, models/data,
API config, `runtime_audit`, `w6_anti_evasion`, `policy_system`, `b0_v2`, all curated `auto_harness` evidence.
