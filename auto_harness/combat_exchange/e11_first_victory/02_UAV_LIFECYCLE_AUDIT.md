# 02 — UAV LIFECYCLE AUDIT (W2-5 C10)
- Launch: all 10 airborne early; roles SEARCH/SCREEN/GLOBAL_SEARCH.
- At 06:56:30 all 10 alive at x=213–245, y=−72…−142; nearest known Black 12–28 km.
- At 06:57:00 all 10 destroyed (same step) — consistent with flying into Black's envelope, not battery
  exhaustion (they were at ~4 h with long battery).
- `_global_search_fly(name,pos,coverage,now,n_airborne)`:
  `targets = coverage.best_unobserved(now,k)` → `center = targets[idx]` → `_fly(...)`.
  **No threat field is consulted.** `CoverageMap` only tracks coverage, not threats.
- Contract gap: the search target is chosen for *coverage gain only*, ignoring the unarmed UAV's
  vulnerability and known enemy positions.
