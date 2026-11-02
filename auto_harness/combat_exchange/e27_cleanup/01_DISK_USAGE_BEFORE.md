# 01 — DISK USAGE BEFORE (E27, baseline f141523)
Filesystems:
| mount | size | used | avail | use% |
|---|---|---|---|---|
| `/` (overlay) | 30G | 28G | 2.2G | 93% |
| `/root/autodl-tmp` (/dev/md127) | 60G | 54G | 6.6G | 90% |
Largest offenders:
| path | size | type | reproducible | safe |
|---|---|---|---|---|
| hsystem/pomdp_api/api_logs/games | 37G (4183 json) | engine per-episode logs | yes (re-run) | yes (historical, not current evidence) |
| /tmp/opencode/parallel_runs | 7.7G | experiment worker logs | yes | yes (evidence compacted first) |
| /tmp/opencode/simlogs | 73M | sim logs | yes | yes |
| hsystem/build | 184M | Cython build temp/dup .so | yes | yes |
| __pycache__ (1328 dirs) + *.pyc | 186.6MB | python cache | yes | yes |
| hsystem/.venv | 1.1–1.3G | separate Python 3.8 venv | no | **NO — protected** |
| hsystem/.git | 82M | engine git objects | no | **NO — protected** |
| githsysys/.git | 59M | deliverable git history | no | **NO — protected** |
