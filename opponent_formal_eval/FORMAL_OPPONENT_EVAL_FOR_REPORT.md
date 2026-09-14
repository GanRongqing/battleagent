# Formal Opponent Evaluation (B0 vs B3) — report

## Setup

- Frozen White (agent/skill/prompt/controllers), frozen simulator physics.
- B0_RANDOM (random-waypoint baseline) vs B3_ADAPTIVE (legal observation-driven adaptive).
- Scales: 5+5 vs10, 10+10 vs20, 15+15 vs30; N=30 each; 180 episodes; paired seeds 1001–1030.

## Main results

| Scale | Opponent | N | Clean Win | Enemy Kills | USV Loss | Explored km² | Peak Sim Threats | Resolve Time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 5+5 vs10 | B0 | 30 | 29 | 9.967 | 1.733 | 57455.833 | 10.0 | 12094.873 |
| 5+5 vs10 | B3 | 30 | 25 | 9.8 | 0.567 | 81894.167 | 9.9 | 21216.233 |
| 10+10 vs20 | B0 | 30 | 28 | 19.867 | 4.1 | 67085.833 | 20.0 | 14187.4 |
| 10+10 vs20 | B3 | 30 | 24 | 19.733 | 3.5 | 93022.5 | 20.0 | 23772.033 |
| 15+15 vs30 | B0 | 30 | 28 | 29.933 | 6.667 | 74610.0 | 30.0 | 13518.929 |
| 15+15 vs30 | B3 | 30 | 25 | 29.767 | 7.1 | 101271.667 | 30.0 | 22326.033 |

## Paired effect (Δ = B3−B0)

| Scale | Δ Clean | Δ Loss | Δ Explored | Δ Peak Threat | Δ Resolve |
|---|---:|---:|---:|---:|---:|
| 5+5 vs10 | -0.133 | -1.167 | 24438.333 | -0.1 | 9121.36 |
| 10+10 vs20 | -0.133 | -0.6 | 25936.667 | 0.0 | 9584.633 |
| 15+15 vs30 | -0.1 | 0.433 | 26661.667 | 0.0 | 8804.679 |

## Key findings

- See FORMAL_OPPONENT_EVAL.md and aggregate/paired CSVs for full numbers.
- N=30 per setting; effect sizes + CI reported; no significance hacking.
