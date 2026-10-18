# 08 — MINIMAL LIFECYCLE CONTRACT
## States
`OBSERVED_ACTIVE | STALE_OR_MISSING | SUSPECTED_DEAD | CONFIRMED_DEAD`
(plus `DEATH_EVIDENCE_CONFLICT` when evidence disagrees.)

## Evidence (each keeps provenance)
- `POSITIONED_OBS(t)` — `obs.active` with position ⇒ **ALIVE at t** (engine-verified).
- `BEARING_OBS(t)` — `obs.passive` ⇒ presence only; never a position.
- `INFERRED_DEAD(t, basis)` — from kill_detect (`kill_delta_attribution` | `corpse_stationary`).

## Invariants (mapped to the task)
1. A single disappearance/timeout/engagement-end inference cannot be CONFIRMED_DEAD.
2. SUSPECTED_DEAD is revoked by a fresh `POSITIONED_OBS`.
3. CONFIRMED_DEAD must have an online-legal source (no engine truth). **Current API provides NO online
   confirmation channel** → the conservative implementation allows **no CONFIRMED_DEAD instances**.
4. Missing observation ≠ death (→ STALE_OR_MISSING).
5. Inference vs confirmation must be distinguishable at the downstream interface (separate sets/flags).
6. Every transition stores event_time, evidence_type, evidence_source, previous_state, next_state, reason.
7. Repeated identical observations do not create duplicate transition events (dedupe by id+event+time).
8. No cross-episode lifecycle state (clear on reset; `_KILLED` must be cleared).
9. No engine truth / hidden fields injected online.
10. Production default frozen unless the experiment flag is on.
