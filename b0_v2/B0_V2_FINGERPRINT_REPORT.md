# B0-v2 Fingerprint Report (N=27, seeds 9001-9027, S2 x frozen W5)

Scope: N=27 validates the three-axis percentile classification and the class
distribution; it does NOT claim sufficient statistical coverage of all 27 classes.

## fp-v2 behavioural proxies (B0-v2)
- continuous/adaptive replanning = 0 (no controller registered; no adaptive logic)
- phase_switch_count = 0 (no phase doctrine)
- no coordination / group structure (random waypoint, uncoordinated)
- random route identity preserved (waypoint logic identical to B0-v1 for same seed)

## B0-v1 vs B0-v2 (N=27)
- behavior_distance = 1.128 ; response_distance = 0.77
- v1 speed degenerate = True (q33==q67==10.0) ; v2 speed degenerate = False
- occupied classes: v1 = 9, v2 = 16 (N=27)
- v2 response signature: clean=1.0, breakthrough=0.0, friendly loss=4.11, kills=20.0

## E0 retention
B0-v2 retains the Random / Uncoordinated (E0) identity: no structured coordination,
no adaptive replanning, no phased switching; the only difference vs B0-v1 is legal
speed variance (within-class variant). => E0 retention = SUPPORTED.
Speed variance does NOT create a new empirical class (no E4).
