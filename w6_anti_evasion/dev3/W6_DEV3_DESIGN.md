# W6-dev3 Design — Allocator-Centric Anti-Evasion

## 1. Hypothesis

W6-dev2's sensing (prediction / risk / handoff / screen) is real and its exploration
benefit is real, but its *execution coupling* broke the validated legacy standoff/engagement
semantics:
- `_w6_intercept` overrides `EnemyTrack.predicted_position`, which ~15 sites in the W5 stack
  read (allocator, threat score, standoff bands, opportunistic lock, kill/stale, summarizer).
- the screen-deploy block rewrites free-USV `move` actions to screen coordinates.

Both change **HOW** a ship navigates/engages, which the W5 controller already does well.
dev3 therefore removes the HOW overrides and keeps only **WHO/WHAT/TARGET** changes.

## 2. Architecture

```
TrackManager
   ↓
W6 state features (prediction/risk/coverage/pursuit cost)   [computed, scalars only]
   ↓
W6 Allocator overlay over the FROZEN W5 allocator:
   base_alloc = ThreatAllocator.allocate_usvs(...)   (W5 semantics: coverage floor +
                                                        marginal concentration + reserve)
   overlay = { risk-adaptive reserve   (mode dev3/prediction_only)
               protected handoff        (owner change only, dev3)
               risk reinforcement       (commit a free USV to an uncovered imminent
                                         breakthrough threat, dev3) }
   → alloc {target: [usv]}
   ↓
LEGACY W5 USVController.step / UAVManager.step   (UNCHANGED code path)
   ↓
ActionSafety → Simulator
```

Invariant: **an execution override writes 0 navigation commands in dev3**. Prediction never
becomes a waypoint; it becomes an ETA / risk / reserve scalar.

## 3. Modes (config `W6_MODE`)

| mode | predictive waypoint | screen move deploy | W6 alloc overlay | purpose |
|---|---|---|---|---|
| `w5` | – (W6 off) | – | none | baseline A |
| `dev2` (default) | on | on | dev2 collapse allocator | baseline B (current) |
| `dev3` | **off** | **off** | handoff + reinforce + adaptive reserve | candidate C |
| `prediction_only` | **off** | **off** | adaptive reserve only (no handoff/reinforce) | variant D |

`controller_mode = LEGACY_W5`, `execution_override = false` for dev3 & prediction_only.

## 4. dev3 allocator overlay semantics (allocator layer only)

- Passthrough preserves W5 concentration + reserve (fixes dev2's collapse-to-one).
- Risk-adaptive reserve: base reserve_ratio (0.20) raised toward 0.4 when many high-risk /
  critical corridors and free-USV availability allow; never fixed-count.
- Protected handoff: for a target whose committed interceptor lead ETA >> best *free*
  alternative ETA (hysteresis ≥ 25%), and no active lock / frozen / damage-chain, reassign
  ownership to the free alternative. Movement/standoff/lock of the new owner is legacy.
- Risk reinforcement: when a track has finite breakthrough horizon and
  `interceptor_deficit < 0` (too late) or no feasible plan, and a free USV exists, commit
  the best-ETA free USV (if target not already at emergency concentration). Counts as a
  defensive_reserve_event.
- Endgame: no reserve/reinforce when only one threat remains.

## 5. Legacy-controller preservation

Because we never set `_w6_intercept` and never rewrite moves in dev3 modes, identical
`(platform, task, target)` under identical legal state ⇒ identical
`USVController.step` primitive output as W5 (verified by unit tests T22/T25/T26).
