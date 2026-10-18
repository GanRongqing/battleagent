# 01 — E5 FINDINGS VERIFICATION
Re-checked against source and the E5 artifacts:
1. `kill()` sets `isactive=False` — hsystem/simulation/core/entity.pyx:33-35. VERIFIED.
2. Radar scans `engine.actives()` — base_engine.pyx:788, used at radar.pyx:261 and :631. VERIFIED.
3. `white_observation`/`active_enemies` is built per tick from `raw` (no cache) — main.py `_analyze_intel`
   (l.680) + `_record_step` post-advance snapshot. VERIFIED.
4. `active` with position ⇒ alive (modulo <=1-tick same-tick ordering). VERIFIED.
5. FALSE_REVIVAL = 0 (structural) — revive requires a positioned active contact. VERIFIED.
6. W2-4 regression is NOT ghost revival. VERIFIED (so do NOT revive the ghost hypothesis).
7. `kill_detect` evidence composition — agent_hybrid_v5.py:545-566: `engaged_missing` (on black-kill delta)
   + corpse (`stationary_duration>=CORPSE_AGE`). VERIFIED.
8. `killed_names` consumers — see 07 (also a SECOND store `_KILLED`). NEW FINDING.
E5 verifier path: `target_lifecycle_integrity/target_lifecycle_verifier.py`; its 12 tests still pass.
