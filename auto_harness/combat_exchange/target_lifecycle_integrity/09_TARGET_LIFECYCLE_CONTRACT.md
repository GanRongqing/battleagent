# 09 — TARGET LIFECYCLE CONTRACT (design only; NOT deployed)

## States
`UNKNOWN | OBSERVED | STALE | SUSPECTED_DEAD | DEATH_EVIDENCE_CONFLICT | CONFIRMED_DEAD`
(analysis reference; not asserted final).

## Evidence types (each with source + timestamp)
- `POSITIONED_OBS(t, id)` from `obs.active` — **proves ALIVE at t** (engine: dead not detectable).
- `BEARING_OBS(t)` from `obs.passive` — proves presence of *an* emitter, NOT position/identity.
- `AGENT_KILL_INFERENCE(t, id, basis)` — a *belief*, never proof; retains `basis`
  (`kill_delta_attribution` | `corpse_stationary` | ...).
- `CONFIRMATION(t, id)` — an independent stronger check if one ever exists.

## Transition invariants (testable)
1. `POSITIONED_OBS` may move a target to OBSERVED; it MUST clear any `SUSPECTED_DEAD`/`CONFIRMED_DEAD`
   flag for that id (a live contact cannot remain dead). → prevents FALSE_DEATH persistence.
2. A single `AGENT_KILL_INFERENCE` may set at most `SUSPECTED_DEAD`, **never** `CONFIRMED_DEAD`.
3. `CONFIRMED_DEAD` requires ≥2 independent kill evidences OR a non-observation timeout ≥ T_dead
   (policy-defined), and is still revocable by a later `POSITIONED_OBS` (log the revocation).
4. Absence of observation is NOT death evidence (→ STALE, not dead).
5. Cached coordinates are not a new observation (no timestamp advance ⇒ no state advance).
6. Conflicting evidence ⇒ `DEATH_EVIDENCE_CONFLICT` (do not silently overwrite); keep both records.
7. IDs are opaque; re-use/ambiguity ⇒ UNKNOWN, never merge.
8. Every transition stores: from, to, event, source, timestamp, reason. Episode reset clears all.
9. Time is `obs.now` (engine time); require monotonic non-decreasing per target.
10. Offline engine truth is NOT an input (no truth in runtime).

## Fallback
If evidence is missing/conflicting → keep the previous state and act conservatively (no new engagement
commitment based solely on an AGENT_KILL_INFERENCE).
