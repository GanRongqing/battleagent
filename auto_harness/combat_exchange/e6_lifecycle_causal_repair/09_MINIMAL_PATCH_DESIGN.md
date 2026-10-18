# 09 — MINIMAL PATCH DESIGN (TARGET_LIFECYCLE_V2)
Flag `TARGET_LIFECYCLE_V2`, default **"0"**. Mutually exclusive with `OBS_TI_REVIVE` by design:
- V2 does **bookkeeping only** (lifecycle state + evidence provenance). It does NOT change tracks,
  assignments, actions, or killed_names. So V2=1 is behaviour-identical to V2=0 and to the frozen baseline.
- Enabling a *behaviour-changing* lifecycle fix (revive live targets) is deliberately NOT part of this
  patch, because E4/E6 prove it flips W2-4 from 2.000 to 0.450 via the allocator/controller interface.

States recorded (evidence-sourced): OBSERVED_ACTIVE (positioned obs), OBSERVED_BEARING, SUSPECTED_DEAD
(kill_detect inference; never CONFIRMED), DEATH_EVIDENCE_CONFLICT (positioned obs while in killed_names).
Invariants enforced: single inference never CONFIRMED; no confirmed channel exists online -> no
CONFIRMED_DEAD instances; dedupe identical transitions; no truth; episode-local (per TrackManager).

Why not the full fix: making the lifecycle fix *effective* requires the allocator/controller to
distinguish "restored live target" from "new priority engagement target" — a downstream business-semantics
change that E4 showed is dangerous. Hence BLOCKED at the interface.
