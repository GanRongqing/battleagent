# B0_RANDOM 27-Class Stratification Report

Policy: black-b0-v1 (B0_RANDOM). Empirical class: E0. These 27 are WITHIN-policy log strata, NOT policies.

- candidates (B0 episodes with black trace): 30
- invalid excluded: 2
- valid unique logs: 28
- dataset_hash: a235a4ee9a15a950
- thresholds: length q33=53919.5 q67=61805.2; width q33=3719.0 q67=5414.1; speed q33=10.0 q67=10.0

## Marginal counts

Length: LOW=10 MID=9 HIGH=9
Width:  LOW=10 MID=9 HIGH=9
Speed:  LOW=28 MID=0 HIGH=0

## Occupancy

- occupied classes: 9
- empty classes: 18
- largest class: ('LENGTH_LOW__WIDTH_LOW__SPEED_LOW', 5)
- class entropy (bits): 3.067

Speed axis is degenerate: B0 commands constant 10 m/s (all episodes speed LOW); the effective stratification is length x width (9 strata).

## 3x3x3 counts (SPEED = LOW; MID/HIGH all zero)

| length \ width | WIDTH_LOW | WIDTH_MID | WIDTH_HIGH |
|---|---|---|---|
| LENGTH_LOW | 5 | 3 | 2 |
| LENGTH_MID | 2 | 2 | 5 |
| LENGTH_HIGH | 3 | 4 | 2 |

SPEED = MID and SPEED = HIGH: all 18 cells are 0 (speed axis degenerate).

## Invalid excluded

- calibration_B0 seed 7003: unusable velocity signal (episode median speed=0.0)
- fresh_b0 seed 7107: unusable velocity signal (episode median speed=0.0)