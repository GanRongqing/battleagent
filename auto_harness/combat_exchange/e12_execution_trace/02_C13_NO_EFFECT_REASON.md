# 02 — C13 NO-EFFECT REASON (VERIFIED)
Chain of evidence (W2-1 / ACE vs C13, seed 43001, trace ON):
1. The override **was installed and called**: `SafeUAVAgentMain.uav_mgr` is `ThreatAwareUAVManager`
   (in-process type check VERIFIED); `_global_search_fly` resolves to the override.
2. It **always took the fallback branch** `if coverage is None or pos is None or not self._threat_pos:
   return super()._global_search_fly(...)`. Trace proof: C13 emitted **1116 base `global_search` records and
   0 `c13_global_search` records** (identical to ACE's 1116 base calls).
3. The fallback was due to **`self._threat_pos` being empty** — W2-1 has essentially no positioned enemy
   tracks while global search runs (the very failure mode C13 was meant to help with). (`coverage` was not
   None: base logged `ntargets`.)
4. Therefore candidate centers and actions were **identical** to ACE (first 3 centers equal:
   (15000,125000),(15000,95000),(15000,155000)); trajectories identical (`3cf09e4fd0a6` for ACE, C13
   trace-ON, and C13 trace-OFF).
=> C13 had no effect because **its guard condition was never true (no known positioned threats)**, i.e. it
   was `_global_search_fly`-fallback, not a wiring failure. `_global_search_fly` **was called** 1116 times.
Classification: **VERIFIED**.

## Debug ON/OFF neutrality
C13 W2-1 trace-ON = `3cf09e4fd0a6` = C13 trace-OFF (E11 `e11_c13_a`) = ACE. Instrumentation is
behaviour-neutral. **VERIFIED.**
