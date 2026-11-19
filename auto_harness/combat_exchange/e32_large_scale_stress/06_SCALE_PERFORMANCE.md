# 06 — SCALE PERFORMANCE (symmetric)
| id | platforms/side | total | K/L | CER | result | wall (s) |
|---|---|---:|---|---:|---|---:|
| L1 | 30 | 60 | 15/3 | 5.000 | Victory | 525.7 |
| L2 | 40 | 80 | 20/3 | 6.667 | Victory | 850.5 |
| L3 | 60 | 120 | 30/6 | 5.000 | Victory | 1463.4 |
Wall time increases with scale (525.7→850.5→1463.4 s for 60→80→120 platforms). VERIFIED.
All three destroy every Black platform (K = Black ship count) with positive exchange. 60v60 completes normally.
INFERRED: per-episode time grows roughly with unit count; single-sample, not a scaling law.
