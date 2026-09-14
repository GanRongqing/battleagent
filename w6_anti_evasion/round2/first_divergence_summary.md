# W6 Round-2 — First-Divergence Summary (STEP 1)

Read-only trace audit of the two W6 regression cases using API game logs (legal
per-step USV/enemy data) + agent logs. No code changes.

## CASE A — B0 S1 seed2002 (W5 clean vs W6 quirk-victory / 5 USV dead)

- W5 game_7: Result.Victory, 794 steps, last_sim 14964, 10 kills.
- W6 game_8: Result.Victory(quirk, breakthrough=1), 1265 steps, last_sim 23532, 10 kills, 5 USV dead.
- First raw divergence (distance signal) ~t=3951s — but both at ~145km (trajectory noise, NOT causal).
- **First causal geometry divergence (knife-fight entry)**: t=13386s, white_usv3
  W5 dist=40.0km vs W6 dist=3.4km. W6 pulled a USV to point-blank range.
- W6 first USV death: t=8828s (alive 5→4). Losses accumulate to 5 by the end.

**Primary root cause: PREDICTION_GEOMETRY** — the W6 predictive intercept aims a USV at a
corridor point without enforcing the legacy standoff band; as the target maneuvers, the
USV chases the intercept point and is pulled inside the target's weapon band → knife-fight
→ USV destroyed → a breakthrough corridor opens (quirk victory with breakthrough).

## CASE B — B3 S1 seed2001 (W5 clean vs W6 defeat / 5 USV dead)

- W5 game_11: Result.Victory, 1118 steps, last_sim 23112.
- W6 game_12: Result.Defeat (我方所有单位被击毁), 1200 steps, last_sim 23273, 9 kills, 5 USV dead.
- First raw divergence (lock_state signal) ~t=7468s (engagement timing differs).
- W6 first USV death: t=17662s (alive 5→4), then losses to 5 → defeat.
- No single clear knife-fight entry by the 30km/40km rule → mechanism is likely a mix of
  (a) sustained close engagement losses (all 5 USVs eventually die) and (b) the adaptive
  opponent routing a ship through while White's USVs are tied up / dying.

**Primary root cause: PREDICTION_GEOMETRY (close-engagement losses) with secondary
RESOURCE_SCHEDULING (screen/coverage leaving a breakthrough lane).**

## Root-cause classification

| case | primary | secondary | evidence step/time |
|---|---|---|---|
| B0 s2002 | PREDICTION_GEOMETRY | SCREEN_OVER_RESERVE (candidate) | knife-fight t=13386 (3.4 vs 40km); first death t=8828 |
| B3 s2001 | PREDICTION_GEOMETRY | BREAKTHROUGH_SLIPPAGE | first death t=17662; defeat (all dead) |

Hypothesis to confirm via STEP 2 diagnostic ablation: the predictive-intercept standoff
geometry (not the screen) is the primary driver of W6 USV losses; the screen reserve may
contribute to breakthrough slippage.
