# 12 — FINAL ROOT CAUSE

## Q1 — kill_detect false-positive cause
`agent_hybrid_v5.py::kill_detect` (l.537-560):
- **engaged_missing heuristic**: when `obs.black_killed - prev > 0`, it takes engaged tracks that are
  absent from `obs.active` THIS tick and marks them killed. Because `active` is the per-tick live radar
  set, a brief radar dropout / LOS gap on a live, engaged target (or attributing the kill to the wrong
  engaged target) produces a **FALSE_DEATH**.
- **corpse test**: `stationary_duration >= CORPSE_AGE` marks a live target dead if its position stops
  updating (stationary or <5 m/step). → FALSE_DEATH.
Evidence: in W2-6 OFF, every `[KILL]` target (usv17/18/19/20/11/16/13/12/14) is still in `active` at the
kill tick → 9 FALSE_DEATH targets (1 unverified).

## Q2 — why a dead target may still appear in legal radar
It essentially does not: `kill()` sets `isactive=False` (entity.pyx:35) and radar scans `actives()`
(radar.pyx:261/631). Only a <=1-tick same-tick ordering artifact is possible. So `active⇒alive`.

## Q3 — how many correct vs wrong revivals
Structurally every revive is a **TRUE_REVIVAL** (it requires a positioned `active` contact ⇒ alive);
**FALSE_REVIVAL = 0** by construction. Exact revive-event counts are NOT_MEASURED (E4 ON did not log
revive events); target-level FALSE_DEATH counts: W2-6 OFF 9, W2-6 ON 14, W2-4 ON 10.

## Q4 — W2-4 first divergence
First action divergence step 260 / 02:10:30 (small course change); active_enemies diverge at 261.
First internal state (first revive event) NOT_MEASURED (needs logging).

## Q5 — is the W2-4 regression caused by false revival of dead targets?
**NO — the false-revival hypothesis is REJECTED** by the engine semantics (revived targets are alive).
The regression is a **downstream behavioural** consequence of re-engaging live targets.
Exact causal chain beyond the first action divergence: **CAUSAL_ATTRIBUTION = INCONCLUSIVE**
(needs revive-event instrumentation).

## Q6 — invariants
See `09_TARGET_LIFECYCLE_CONTRACT.md` (positioned-obs revives; single inference ≤ SUSPECTED_DEAD;
absence≠death; conflict preserved; no truth).

## Q7 — decision
The **FALSE_DEATH** problem (kill_detect marking live targets dead) is well evidenced and is the real
defect. The naive blanket REVIVE is NOT the fix (E4: W2-4 regression). A targeted fix must change
`kill_detect`'s evidence rules (per contract), not the TrackManager suppression alone.

Confidence: HIGH for Q1/Q2/Q5-rejection; MEDIUM for the exact W2-4 causal chain.
