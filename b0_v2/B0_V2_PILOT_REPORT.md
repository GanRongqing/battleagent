# B0-v2 Pilot Report (seeds 9001-9009, S2 x W5, N=9)

| seed | episode_target_speed | actual median speed |
|---|---|---|
| 9001 | 9.731 | 9.731 |
| 9002 | 5.375 | 5.375 |
| 9003 | 8.742 | 8.742 |
| 9004 | 6.588 | 6.588 |
| 9005 | 5.402 | 5.402 |
| 9006 | 7.660 | 7.660 |
| 9007 | 7.141 | 7.141 |
| 9008 | 9.999 | 9.999 |
| 9009 | 5.251 | 5.251 |

- target: min 5.251, max 9.999, std 1.746, unique 9
- actual: min 5.251, max 9.999, std 1.746, unique 9
- actual follows target (|diff| < 0.2): PASS
- pilot independent thresholds: length q33=44661.6 q67=56036.3; width q33=2765.2 q67=3964.4;
  speed q33=6.193 q67=8.021 -> speed axis non-degenerate = YES
- pilot marginals 3/3/3 all axes; occupied 8/27 (N=9 sparse, expected)
- requested = effective = black-b0-v2 per episode meta; no adaptive controller registered.

PILOT GATE = PASS. Proceeding to full N=90 (seeds 9001-9090).
