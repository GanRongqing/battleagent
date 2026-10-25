# 06 — C18 SENSOR_GEOMETRY_AWARE_SEARCH (area-bounded coverage)
`agent_hybrid_coverage_bounds.py` (white-combat-0018-v1, parent C17). ONE mechanism: replace the coverage
grid with **area-aligned bounds** x∈[0,370.4] km, y∈[-280,+280] km (cell size / 3x3 marking / weight /
`best_unobserved` unchanged), so `best_unobserved` can no longer propose out-of-area cells and can represent
the southern half. No scenario/route/strategy ID, no truth, no black-state read; C10 USV logic and C17
bounding untouched.
Tests `test_coverage_bounds.py` **6/6**: grid inside area; no y>280 / y<−280 cells; cell↔center roundtrip;
best_unobserved stays in area; fresh-map episode isolation; C17 clamp still inherited.
Sector-awareness (±30°) is **VERIFIED as a second defect** but NOT changed in C18 (kept isolated for clean
attribution); recommending it as a separate follow-up.
