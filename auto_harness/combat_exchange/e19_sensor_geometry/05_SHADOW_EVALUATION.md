# 05 — SHADOW EVALUATION (no action change)
Replayed the C17 W2-1 trace through two coverage maps (original vs sector-aware) and compared
`best_unobserved(k=#alive)` targets: target **set differs on 54/833 steps (6.5%)**.
Also verified by code: normal `_search_fly` ignores `CoverageMap`, but `GLOBAL_SEARCH` (reached during the
751-step `GLOBAL_REACQUIRE` phase) **does** consume `best_unobserved`.
=> The coverage error is NOT purely cosmetic: it can change UAV search targets. Additionally the grid is
range-wrong (y 80–620 km) and can propose **out-of-area** cells. Actionable → proceed to one minimal candidate.
