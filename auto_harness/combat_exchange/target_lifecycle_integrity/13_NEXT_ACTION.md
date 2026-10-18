# 13 — NEXT ACTION
1. **Do not re-enable the naive `OBS_TI_REVIVE`** (E4 proved control regression; default stays 0).
2. Proposal (not deployed): replace `kill_detect`'s single-inference death with the lifecycle contract:
   - a kill *inference* only marks `SUSPECTED_DEAD`;
   - a later positioned active observation revokes it and restores the track (this is the legitimate
     part of REVIVE, but scoped to inference revocation);
   - corpse test requires temporal persistence + re-confirmation, not one stationary window.
3. To attribute the W2-4 regression precisely: add **logging-only revive/kill event tracing** and replay
   W2-4 OFF/ON once (NEED_INSTRUMENTATION if exact first-revive timing is required).
4. Then re-evaluate in a **new epoch** (do not mix with E2/E3/E4).
No C12; no production change this round.
