# 11 — UNIT TEST RESULTS
- `test_target_lifecycle_v2.py` — **16/16 PASS** (flag OFF empty state; OBSERVED_ACTIVE/BEARING;
  inference=SUSPECTED_DEAD not CONFIRMED; conflict; dedupe; no-obs≠death; provenance; id not merged;
  episode isolation; flag-neutral killed_names/tracks; OBS_TI_REVIVE default 0; verifier compat;
  suspected≠confirmed).
- E5 verifier tests — **12/12 PASS**.
- Observation-integrity tests — **7/7 PASS**.
- H1 flag-OFF neutrality — lifecycle empty; track present; killed_names/tracks identical with flag on/off.
  (Structural: V2 only adds `if self._lc_enabled` bookkeeping; no action path reads lifecycle.)
