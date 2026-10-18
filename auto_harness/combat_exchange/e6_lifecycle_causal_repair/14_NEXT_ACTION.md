# 14 — NEXT ACTION
1. Keep `OBS_TI_REVIVE=0` and `TARGET_LIFECYCLE_V2=0` defaults (bookkeeping patch may be enabled for
   auditing only).
2. Required next design (not implemented): a downstream engagement interface that distinguishes
   `RESTORED_LIVE_TARGET` from a fresh priority target, so a revived live contact does not pull units
   into a losing local exchange. Only then run a **fresh epoch** combat evaluation (E7) of the
   behaviour-changing fix.
3. Also fix the duplicate global `_KILLED` (never cleared) as part of that design.
No C12; no further oracle/truth use.
