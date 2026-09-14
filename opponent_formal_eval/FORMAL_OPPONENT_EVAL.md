# Formal Opponent Evaluation — B0_RANDOM vs B3_ADAPTIVE

White frozen; simulator physics frozen; Black enhanced ONLY by legal observation-driven adaptive policy (B3). Paired seeds 1001–1030, N=30/setting.

## Main table

| Scale | Opponent | N | Clean Win | Enemy Kills | Friendly USV Loss | Explored Area | Peak Simult Threats | Resolution Time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 5+5 vs10 | B0 | 30 | 29 | 9.967 | 1.733 | 57455.833 | 10.0 | 12094.873 |
| 5+5 vs10 | B3 | 30 | 25 | 9.8 | 0.567 | 81894.167 | 9.9 | 21216.233 |
| 10+10 vs20 | B0 | 30 | 28 | 19.867 | 4.1 | 67085.833 | 20.0 | 14187.4 |
| 10+10 vs20 | B3 | 30 | 24 | 19.733 | 3.5 | 93022.5 | 20.0 | 23772.033 |
| 15+15 vs30 | B0 | 30 | 28 | 29.933 | 6.667 | 74610.0 | 30.0 | 13518.929 |
| 15+15 vs30 | B3 | 30 | 25 | 29.767 | 7.1 | 101271.667 | 30.0 | 22326.033 |

## Paired effect of adaptive opponent (Δ = B3 − B0)

| Scale | Δ Clean Win | Δ Friendly Loss | Δ Exploration | Δ Peak Threat | Δ Resolution Time |
|---|---:|---:|---:|---:|---:|
| 5+5 vs10 | -0.133 | -1.167 | 24438.333 | -0.1 | 9121.36 |
| 10+10 vs20 | -0.133 | -0.6 | 25936.667 | 0.0 | 9584.633 |
| 15+15 vs30 | -0.1 | 0.433 | 26661.667 | 0.0 | 8804.679 |

## Clean Win Rate (Wilson 95% CI)

- 5+5 vs10 B0: 29/30 (0.967), CI [0.8333, 0.9941]
- 5+5 vs10 B3: 25/30 (0.833), CI [0.6644, 0.9266]
- 10+10 vs20 B0: 28/30 (0.933), CI [0.7868, 0.9815]
- 10+10 vs20 B3: 24/30 (0.800), CI [0.6269, 0.905]
- 15+15 vs30 B0: 28/30 (0.933), CI [0.7868, 0.9815]
- 15+15 vs30 B3: 25/30 (0.833), CI [0.6644, 0.9266]

## Consistency check

- kill_accounting_mismatch_total=78 (event-vs-terminal lag; event-based reconciled count is authoritative)

## Failures (non-clean)

- S1 B0: type b × 1
- S1 B3: type B × 1
- S1 B3: type C × 4
- S2 B0: type b × 2
- S2 B3: type C × 6
- S3 B0: type b × 2
- S3 B3: type B × 1
- S3 B3: type C × 4

## B3 adaptive behavior (event counters)

- See episode_results.csv b3_* columns (replan / lane-shift / dispersion / detection events).

## Definitions

- clean_win = engine Victory (all enemy combat USV destroyed) AND breakthrough==0.
- enemy_combat_killed_event = event-based reconciled combat kill count (authoritative).
- peak_simultaneous_threat_count = max over White-legal steps of visible enemy count (same definition B0/B3).
- paired by initial scenario seed 1001–1030; trajectories may diverge after policy interaction.
