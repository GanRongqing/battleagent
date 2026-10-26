# 05 — ENGAGEMENT RACE TIMELINE (C19 W2-1, from LOCK_TRACE ON)
| time (engine s) | episode | event |
|---|---|---|
| 10406 | 02:53:26 | **Black first LOCK_START** (67 chains total) |
| 10707 | 02:58:27 | **Black first WINDOW_COMPLETE / HIT / FREEZE**; first White USV deaths (40 hits, mass) |
| 10920 | 03:02:00 | **White first LOCK_START** (11 chains total) |
| 11221 | 03:07:01 | **White first WINDOW_COMPLETE / HIT**; **all 4 Black kills** |
- Before the first White loss, White completed **0** chains; Black had already delivered 40 hits/40 freezes.
- White began locking **214 s after** Black's first kill; all White kills land at one instant (11221).
- White chain quality was fine: 11 chains, **0 breaks**, all completed, 10 hits/1 miss (91%).
- Black: 67 chains, 48 complete, 40 hits/8 miss.
**Conclusion**: White's problem is **too few, too-late chains** (11 vs 67), not hit conversion or
interruption. Root cause is detection-to-lock latency: White USV radar ~20 km while lock range is 40 km,
so White only acquires/positions Black late, after Black (which locks at 40 km) already mass-froze White.
