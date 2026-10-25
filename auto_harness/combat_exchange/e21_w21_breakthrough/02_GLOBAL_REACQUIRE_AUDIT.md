# 02 — GLOBAL_REACQUIRE / ENGAGEMENT-GEOMETRY AUDIT (W2-1, C10)
Source: `USVController.step` — with no assigned target: GLOBAL_REACQUIRE → move to `(SCREEN_X=120 km, own y)`;
NORMAL_COMBAT → move east `(x+100 km, y)`. `_compute_mission` flips to GLOBAL_REACQUIRE after >90 s with no
ship track.
Timeline (VERIFIED from `e9_B_c10_off`, hourly mean USV x):
| time | W2-1 mean x | W2-4 mean x |
|---|---:|---:|
| 01:00 | 131.9 | 191.9 |
| 02:00 | 203.8 | 253.5 |
| 03:00 | 131.9 | 280.3 |
| 04:00 | 119.9 | 250.4 |
| 05:00 | 119.9 | 178.4 |
| ≥06:00 | 119.9 | ~120 |
Findings (VERIFIED):
1. W2-1 advances to x≈204 km by 02:00 (where the 01:53 contact occurs) then **retreats to 120 km** and stays pinned for 4+ h.
2. It spends **751 steps in GLOBAL_REACQUIRE** (tracks exist only 240 steps), i.e., most of the episode in fixed screen.
3. W2-4 (contact retained) keeps advancing to ≈297 km — that scenario closes to 2.1 km and trades 12/7.
=> The retreat-to-fixed-screen after contact loss is the earliest legal behavioural branch that suppresses
re-acquisition/re-engagement. (NOT proven sole root cause until C19 experiment — see 04.)
Answers: enters GLOBAL_REACQUIRE ~90 s after losing the ship track (shortly after 01:53); all no-target USVs
are moved to the screen; long fixed-screen dwell = yes (≥4 h); post-switch search is effectively frozen at x=120.
