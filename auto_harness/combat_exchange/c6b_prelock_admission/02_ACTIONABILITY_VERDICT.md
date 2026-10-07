# C6B Stage A — Actionability Verdict

## Verdict: PARTIALLY_ACTIONABLE (own-geometry part) / INSUFFICIENT (target-dependent part)

Observable at runtime WITHOUT truth:
- own USV position/heading/speed (obs.usvs) — legal
- local friendly count + nearest-support distance (obs.usvs) — legal
- forward overextension vs local friendly centroid — derived, legal
- own active lock (`is_locking`) and being-locked (`is_locked`/`locked_attacker`) — legal
- current assignment (`usv_ctrl.targets`) + assigned-target existence/visibility — legal
- time closing without own lock — derived from own motion + assignment — legal

NOT available pre-death in hard cases: the causal audit showed some LOSS cases die at/near first
contact (median first death 6270s ≈ median first contact 6570s), so **target-dependent admission is
unreliable**; only **own-formation cohesion** signals are reliably present pre-death.

=> Proceed with a MINIMAL own-geometry cohesion/overextension governor (no truth, no route/strategy ID).
Do NOT build an enemy-truth based survival rule.
