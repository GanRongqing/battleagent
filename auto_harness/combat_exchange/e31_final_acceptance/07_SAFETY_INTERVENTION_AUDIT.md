# 07 — SAFETY INTERVENTION AUDIT (final buffer)
`SAFETY_TRACE` aggregate over 13 episodes (13 agent processes):
| counter | value | meaning |
|---|---:|---|
| rewrites | 40538 | total course rewrites |
| predicted_out | 3972 | predicted to leave polygon next step |
| preventive_buffer | 36523 | inside & near boundary (<5km) & approaching → preventive turn |
| current_out | 43 | already outside (recovery) |
| unexpected | **0** | rewrites with no geometric justification |
| unnecessary (=preventive) | 36523 | label collision: these are the legitimate preventive buffer turns (see note) |
Note: `unneeded` and `preventive` both count inside→inside preventive turns; per the task, preventive buffer
turns are NOT errors. The meaningful error metric `unexpected_rewrites = 0`.
Large preventive count is driven by UAV tether hovering near the W2 eastern edge (front+30km); it did not change
combat (K/L identical to E30 for all 13). Interior (far-from-boundary) motion is never rewritten by construction.
