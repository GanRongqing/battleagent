# 03 — DEATH EVENT INTEGRITY (VERIFIED)
Cross-checked per-episode: UAV alive→dead transitions vs logged “white_uavN 被击毁” events.
| case | scenario | UAV deaths (state transitions) | UAV kill events | match |
|---|---|---|---|---|
| C10 | W2-5 | 10 | 10 | VERIFIED |
| ACE | W2-5 | 10 | 10 | VERIFIED |
| ACE | W2-6 | 10 | 10 | VERIFIED |
No spurious/missing UAV death events. (Breakthrough/out-of-area kills are separate and are not counted as
combat kills in the CER; the metric uses `[META] enemy_kills` vs White USV losses.)
