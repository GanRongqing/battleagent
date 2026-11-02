# 02 — SCENARIO SELECTION (frozen before running)
Selected 7 non-W2 configs from `hsystem/simserver/config/sces.json` / `sim_script/20250819TZB`:
S10 (5+5v5+5), S15 (8+7v8+7, asymmetric composition), S20 (10+10v10+10), S30 (15+15v15+15),
S10RW (5+5 random-waypoint black), EXTD (external dispersed), EXTT (external two-wave).
They are **not W2 aliases**: W2 uses route-based Chinese plan scripts (fixed arrow/fan/flank/mirror/shrink
routes, 20 USV + 10 UAV White vs route Black); the scale scenarios use `scenario_builder` with straight_west
or random_waypoint Black and different fleet counts; external_* use prebuilt `TzbEngine` scenarios.
Selection rationale fixed before any C10/C30 run (avoid cherry-picking).
