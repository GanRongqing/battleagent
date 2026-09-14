# W6-dev4 Quality Diagnosis

REALLOCATION QUALITY
GOOD = 5
NEUTRAL = 0
BAD = 2 (both very-late transient free-adds, harmless: no death, no coverage collapse)
AMBIGUOUS = 0

NEAR-MISS (offline proxy, 2035 states)
total (imminent corridors) = 895 states
potentially beneficial (FREE platform whose best-ETA target is imminent) = 777 states (~38%)
blocked live mainly by = trigger only on uncovered/deficit corridors + step cadence + free-only
blocked by cooldown = not a factor measured
blocked by hysteresis = rare (W5 already assigns nearest owners)
blocked by commitment = active-lock platforms correctly excluded (0 hard violations)

PRIMARY ROOT CAUSE =
Live dev4 reallocation is throttled to a narrow trigger (only "uncovered/deficit imminent"
targets + FREE platforms + step cadence), so the abundant FREE→imminent opportunity (~38% of
states) is mostly unrealised; the few realised ones are mostly GOOD.

RECOMMENDED NEXT CHANGE (ONE) =
Extend the dev4 reallocation trigger to commit a FREE platform to ANY imminent (risk>=HIGH)
corridor with < emergency concentration, provided the FREE platform's ETA is within 1.5x of the
current best lead there (WHO/TARGET only; no weights/hysteresis/controller/HOW change).
