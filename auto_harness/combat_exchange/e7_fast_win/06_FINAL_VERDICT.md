# 06 — FINAL VERDICT (E7)

## Root cause (confirmed by code + E6 trace + E7 unit tests)
`OBS_TI_REVIVE` revoked an inferred death in `killed_names` only; `_KILLED` (module-global, updated
unconditionally in `step_once`) still held the target. Downstream consumers of `_KILLED` (allocator
candidate filter l.1837; controller target release l.2057; opportunistic lock l.2143) therefore kept
treating a restored, legally-observed live target as dead — an inconsistent lifecycle handoff.
Evidence: E6 trace step 261 (killed_names empty on ON, track restored) + code path l.2821.

## Single mechanism
`LIFECYCLE_HANDOFF_V1` (default **0**): on a fresh positioned observation that revokes an inferred death,
clear BOTH `killed_names` and `_KILLED` atomically. No truth; no engine/tactics change.

## Gates
- Gate A: 10/10 new + E6 16/16 + E5 12/12 + obs 7/7. Flag-OFF equivalence and episode isolation PASS.
- Gate B: offline replay reproduced the inter-store inconsistency and 209 FD unit-steps / 139 revives.
- Gate C: W2-4 **12/5 (2.400)** no regression; W2-6 **14/13 (1.077)** positive exchange.

## Verdict: `INTERFACE_FIX_VALIDATED`
- Interface correctness: **PASS**.
- Behaviour compatibility (W2-4 control): **PASS** (no regression; improved).
- Combat result change: **YES on this deterministic trajectory** (W2-6 >1).
- Independent stochastic generalization: **NOT_ESTABLISHED** (single deterministic trajectory per scenario;
  locker hit is seed-independent post determinism-fix).

## Constraints honoured
ACE/C10/C11/Engine/Black/scenarios unchanged; `LIFECYCLE_HANDOFF_V1` default **0** (NOT promoted);
`OBS_TI_REVIVE` default 0; `TARGET_LIFECYCLE_V2` default 0; E4/E5/E6 data untouched.
No C12; no full panel; 2 trajectories total.

## Next action
Human approval before any promotion. A fresh epoch (new RNG) is required to test generalization; this
round only establishes the interface fix + a promising deterministic result.
