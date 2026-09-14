# Formal Evaluation Summary — S1/S2/S3 (N=30 each, 90 episodes)

## Main table

| 场景 | N | Clean Win | 95% CI | 平均击杀 | 平均我方USV损失 | 平均探索面积(km²) | 探索比例 | Breakthrough | OOB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5+5 vs 10 | 30 | 29 | [0.8333, 0.9941] | 9.97 | 1.73 | 57455.8 | 0.2972 | 0 | 0 |
| 10+10 vs 20 | 30 | 28 | [0.7868, 0.9815] | 19.87 | 4.1 | 67085.8 | 0.3471 | 2 | 0 |
| 15+15 vs 30 | 30 | 28 | [0.7868, 0.9815] | 29.93 | 6.67 | 74610.0 | 0.386 | 2 | 0 |

## Definitions

- Clean Win = engine `Result.Victory` (black_ship_alive==0, i.e. all enemy combat USV destroyed) **and** `black_breakthrough==0` (existing run_priority_eval definition).
- 平均击杀 = **event-based reconciled** enemy combat USV killed (reward `black_killed` minus breakthrough minus OOB; cross-checked with agent `[KILL]` names).
- Exploration = maritime_metrics fixed 5 km grid, union-dedup; denominator = 任务区域.json polygon area (193,301.27 km²).
- OOB removal fraction computed from evaluator out-of-bounds flags.

## Consistency check

Issues found:

- S1 s1019: event-vs-terminal mismatch 1
- S1 s1021: event-vs-terminal mismatch 1
- S2 s1002: event-vs-terminal mismatch 1
- S2 s1003: event-vs-terminal mismatch 1
- S2 s1006: event-vs-terminal mismatch 1
- S2 s1007: event-vs-terminal mismatch 1
- S2 s1016: event-vs-terminal mismatch 1
- S2 s1019: event-vs-terminal mismatch 2
- S2 s1021: event-vs-terminal mismatch 1
- S2 s1023: event-vs-terminal mismatch 1
- S2 s1026: event-vs-terminal mismatch 1
- S2 s1029: event-vs-terminal mismatch 1
- S3 s1002: event-vs-terminal mismatch 1
- S3 s1004: event-vs-terminal mismatch 2
- S3 s1006: event-vs-terminal mismatch 1
- S3 s1010: event-vs-terminal mismatch 1
- S3 s1016: event-vs-terminal mismatch 1
- S3 s1018: event-vs-terminal mismatch 1
- S3 s1021: event-vs-terminal mismatch 2
- S3 s1022: event-vs-terminal mismatch 1
- S3 s1027: event-vs-terminal mismatch 1
- S3 s1029: event-vs-terminal mismatch 1

## OOB

No observed enemy OOB removals in the formal evaluation.
