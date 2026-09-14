# W6-dev4 Design

## Goal
Give the W6 allocator a finite, bounded, auditable reallocation freedom (decision
expressivity) without touching HOW.

## Pipeline
Legal obs -> Track/Prediction/Risk -> CommitmentClassifier (anti_evasion/commitment.py)
-> ReleasablePoolBuilder (releasable_pool.py) -> ElasticReserveManager
(elastic_reserve.py) -> W6 allocator (agent dev4 branch) -> assignment -> legacy controller.

## Pools
FREE (no target) / SOFT (target, no lock/frozen) / HARD (lock|frozen, never releasable) /
RESERVE (free held by elastic manager when uncovered high-risk demand).

## Reallocation rules (conservative)
- dest must be imminent/uncovered or ETA >=25% better than the current lead (BETTER_INTERCEPTOR)
- hard never moved; soft move only if old target stays covered; one realloc per 5 steps (cap).
- applies as task-level owner change (usv_ctrl.targets) or free-pool addition; never waypoint.

## Gating
W6_MODE=dev4; default dev2 unchanged; dev3/iso unchanged (regression suites green).
