# LA-F1 Root-Cause Report (0 new episodes)

Corpus: W5 baseline, 24 episodes (11001/11002), reliable game logs.
No-lock USV-target assignments analysed: 396 of 1395 (71.6% lock rate).

## Subcause breakdown (single primary per assignment)

| rank | family | count | share | strategies | profile |
|---|---|---|---|---|---|
| 1 | LA1-E WHITE_DIED_BEFORE_CLOSURE | 191 | 48.2% | 6 | vis=0.53 (half-lost), min_distance=102 km (far) |
| 2 | LA1-D GEOMETRY_OSCILLATION | 97 | 24.5% | 5 | vis=0.98, min_d=47 km, osc=42.6 |
| 3 | LA1-F LEGAL_LOCK_MISSED | 55 | 13.9% | 4 | vis=0.91, min_d=20 km (< 40 km but no lock) |
| 4 | LA1-A TRACK_LOST_DURING_APPROACH | 30 | 7.6% | 5 | vis=0.07, min_d=94 km |
| 5 | LA1-I OTHER | 16 | 4.0% | 1 | — |
| 6 | LA1-C NO_CLOSING_PROGRESS | 7 | 1.8% | 2 | receding |

## Dominant root cause: **LA1-E (48.2%, 6/6 strategies)** — DOMINANT_ROOT_CAUSE_FOUND
The single largest LA-F1 subcause is that the assigned White USV **dies before reaching lock range**.
Its profile is a **far, half-lost target** (mean min-distance 102 km, visibility 0.53): the USV is
committed to a distant, intermittently-tracked target, closes without ever getting into lock range, and
is killed while exposed.

## Success vs failure (control group)
| group | visible_frac | osc | close600 (m) | pos_closing_frac |
|---|---|---|---|---|
| successful lock | 0.96 | 32.8 | 5508 | 0.44 |
| LA-F1 failure | 0.68 | 24.5 | 8639 | 0.63 |

Failing assignments are **less visible** (0.68 vs 0.96) and **closer further** (close600 larger) yet do
not lock — i.e. they are chasing far/lost targets, not failing to close per se.

## Answers to the phase questions
- **LA1-A vs LA1-B**: prediction-error (LA1-B) is NOT_MEASURED (no belief in game logs); it cannot be
  separated here.
- **LA1-C is NOT the main issue** (1.8%); most failures DO close.
- **LA1-D (oscillation) is real and second** (24.5%): visible targets, closes to ~47 km, but the USV
  oscillates and never quite enters 40 km.
- **LA1-F (legal lock missed, 13.9%)**: USVs that DID enter < 40 km still failed to lock — a
  controller/legality gap.
- **LA1-E / LA1-A together (55.8%) involve track loss**: sensing persistence is a large factor behind
  the "never closed" symptom.

## Why C2 (closing harder) was insufficient
More aggressive closing cannot help the dominant LA1-E (the USV dies while chasing a far/lost target)
nor LA1-D (the USV is already at 47 km but oscillates). This is consistent with the C2 result
(lock rate up, TTFL up, combat mixed).

## Recommended C3 mechanism (single)
Primary maps to **LA1-E -> SURVIVAL_AWARE_PRELOCK_ADMISSION** (do not commit into an exposed approach
without a plausible lock/closing + support). Secondary LA1-D -> INTERCEPT_HYSTERESIS.
Confidence: MEDIUM (LA1-E is a "died" outcome; the underlying driver is far/lost targets).
