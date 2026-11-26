# 09 — BOUNDARY & RUNTIME AUDIT
- Safety: all **16 valid episodes** `available=True`; `unexpected_rewrites=0`; rewrites = preventive_buffer only
  (units near boundary). **PASS**
- Engine AREA_TRACE: **no events** → **White USV AREA_OUT = 0, White UAV AREA_OUT = 0** (both sides ship-only; Black
  area-out also 0). **PASS**
- Runtime: serial single-worker; batch wall for F01–F15 = **9842.2 s**; F16 rerun = **592.8 s**. Per-episode wall not
  recorded individually in batch mode → NOT_MEASURED per episode (avg ≈ 656 s).
- F16 first attempt failed at `/start` (400): a scenario-registration typo (missing comma) in `AVAILABLE_SCRIPTS`
  merged `E34-路线16` with the next entry; fixed (registration only, no combat change) and rerun successfully.
  The failed attempt is not counted.
