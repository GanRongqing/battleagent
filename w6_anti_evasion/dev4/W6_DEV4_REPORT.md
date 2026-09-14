# W6-dev4 Decision Expressivity / Elastic Reallocation

## 1. Root cause
2035-state replay showed W6 features active (prediction 75%, risk 74%, reserve 44%) yet
assignment change = 0/2035. Offline counterfactual shows the bottleneck is decision
expressivity: the decision mechanisms never had a releasable platform to act on (they fired
only on rare uncovered-corridor triggers). Granting one/full soft-release lifts changeable
states to 17.8% / 37.4%.

## 2. Commitment model
`anti_evasion/commitment.py` — FREE / SOFT_COMMITTED / HARD_COMMITTED / RESERVE from legal
fields: HARD = locking or frozen (or dead); SOFT = target without lock/frozen; FREE = no
target; RESERVE = FREE held by the elastic manager.

## 3. Releasable candidate pool
`anti_evasion/releasable_pool.py` — FREE + eligible SOFT (old target still covered, not an
imminent corridor). HARD never enters.

## 4. Hard commitment protection
HARD platforms (active lock / frozen / second-hit window) are never reallocated; agent skips
them; live `hard_commit_violations` = 0.

## 5. Elastic reserve
`anti_evasion/elastic_reserve.py` — threat-driven, resource-relative, endgame-aware
(`desired_reserve_capacity`), controls availability only (never navigation).

## 6–8. Offline counterfactual & expressivity
See `offline/DEV4_OFFLINE_COUNTERFACTUAL_REPORT.md`: A 3.1% → B one-free 17.8% → C/D soft /
elastic 37.4% changeable states; reasons explainable.

## 9. Determinism / fair play
T27–T36 unit tests 15/15 (incl. hard-not-releasable, no-execution-override under dev4).
Dev2/dev3/isolation regression suites green (dev4 gated behind W6_MODE=dev4; default dev2).

## 10. Live sanity (S2 × B3 × 4001–4003, N=3; legacy execution)
| variant | clean | mean loss | brk | explored | res s |
|---|---:|---:|---:|---:|---:|
| W5 (prior) | 2/3 | 4.0 | 1 | 92,983 | 22,852 |
| W6-dev3 (prior) | 0/3 | 8.0 | 2 | 81,975 | 28,135 |
| W6-dev4 | 1/3 | 5.7 | 2 | 79,717 | 22,372 |

Resource/reallocation counters (dev4): mean free pool 5.5–7.8; soft release 0–1;
realloc 0–2/game; reserve release 3–7/game; hard-commit violations 0; execution override 0.

Live reading: decision expressivity now fires (>0, unlike dev3's 0) but remains sparse on
these 3 hard episodes; outcomes are within run-level noise; no catastrophic new failure.

## 11. Decision
Continue dev4 quality audit (eligibility/release timing is still conservative; sparse live
triggering), NOT a 3-scale/FINAL. Versioned as W6-dev4 (parent W6-dev3).
