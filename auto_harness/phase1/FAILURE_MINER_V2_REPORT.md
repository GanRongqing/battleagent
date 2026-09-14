# Failure Miner v2 — duration-normalized (Phase 0 corpus, N=100)

- clean=65 fail=35
- taxonomy: {'F-LEAK': 26, 'CLEAN_WIN': 65, 'F-ATTRITION': 9}

## Duration-normalized event features

| feature | raw clean | raw fail | /1k steps clean | /1k steps fail | /1k sim-s clean | /1k sim-s fail |
|---|---|---|---|---|---|---|
| lost_track_runs | 9.123 | 11.829 | 16.9062 | 10.0818 | 0.4686 | 0.3313 |
| capacity_hole_proxy_steps | 26.108 | 32.657 | 48.915 | 27.4199 | 1.3572 | 0.9082 |
| reacquire_attempts | 175.8 | 208.114 | 332.5903 | 178.2901 | 9.2446 | 5.8606 |

Finding: raw counts are higher in failures only because failures last ~2x longer;
per-1000-step and per-1000-sim-s rates are LOWER in failures. Track continuity /
reacquire / capacity-hole are therefore NOT the primary cause (duration artifact).

## Absolute-time-bin mean lost tracks

| window | clean | fail |
|---|---|---|
| 0-5k | 0.48 | 0.49 |
| 5-10k | 1.09 | 1.08 |
| 10-15k | 0.35 | 0.48 |
| 15-20k | 0.15 | 0.21 |
| 20-25k | 0.19 | 0.19 |
| 25-endk | 0 | 0 |

## New taxonomy

- F-LEAK = 26 (breakthrough, all enemies eventually killed)
- F-ATTRITION = 9 (breakthrough + loss>=5 or survivors>0)
