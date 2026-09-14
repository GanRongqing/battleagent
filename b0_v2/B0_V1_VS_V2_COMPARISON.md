# B0-v1 vs B0-v2 Comparison

## Q1 Why v1 speed axis degenerate?

- B0-v1 commands fixed 10 m/s (= ShipMotorTZB.max_speed); v1 speed std=0.005, unique=5 -> q33==q67.

## Q2 How v2 introduces legal speed variance?

- black-b0-v2 samples episode_target_speed ~ Uniform(5,10) m/s (deterministic, separate RNG stream); same waypoint logic as v1.

## Q3 Actual speed variance?

- v2 speed: {'n': 27, 'mean': 7.273, 'median': 7.141, 'std': 1.679, 'min': 5.163, 'max': 9.999, 'unique': 27}
- v2 speed degenerate = False

## Q4 Random/uncoordinated identity?

- no coordination/adaptation/phase logic (unit tests + source audit); E0 retention via fp (no structured replan/phase features).

## Q5 Occupied classes

- v1 occupied=9 (speed degenerate); v2 occupied=16

## Q6 Marginals

- v1 length {'LOW': 10, 'MID': 9, 'HIGH': 9}, width {'LOW': 10, 'MID': 9, 'HIGH': 9}, speed {'LOW': 28, 'MID': 0, 'HIGH': 0}
- v2 length {'LOW': 9, 'MID': 9, 'HIGH': 9}, width {'LOW': 9, 'MID': 9, 'HIGH': 9}, speed {'LOW': 9, 'MID': 9, 'HIGH': 9}

## Q7 Empty cells

- v2 empty=11/27 (feature correlation / sparse N; not forced).

## Behavior/response distance v1 vs v2

- behavior_distance=1.128 response_distance=0.77
- v2 response signature: {'victory': 1, 'clean_win': 1, 'breakthrough_count': 0.0, 'white_friendly_losses': 4.1111, 'enemy_kills': 20.0, 'explored_ratio': 0.3191, 'white_reacquire_count': 0.1852}

## Q8 Should v2 enter active pool?

- Recommendation pending full N=90 + fp; v2 is a baseline variant, not a new class.

## Q9 black-b0 alias

- Keep alias on v1 for now; consider v2 only after validation (not auto-switched).