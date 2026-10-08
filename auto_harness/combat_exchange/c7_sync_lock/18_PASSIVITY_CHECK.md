# 18 — PASSIVITY CHECK
| Group | ACE Black kills | C7 Black kills |
|---|---|---|
| W2-1 | 0 | 0 |
| W2-6 | 50 | 55 |
| W2-2 | 20 | 20 |
| W2-4 | 60 | 56 |

No case shows kills/engagement collapsing while survival improves. W2-6 kills **rise** (50->55). W2-1 is
flat (0/0, both arms). No `NO_OP/HOLD` blow-up. Bounded timers (MAX_SYNC_TIME) guarantee no permanent
waiting.
Verdict: **passivity regression = NO.**
