# W2-1 Structural Failure Verdict

## Timebase
- episode_start_abs = 270 s (first logged step); first_death_abs = 27,270 s; first_death_relative ≈ 27,000 s.
- 6270 vs 27270 explanation = **pooling artifact** (6270 = median over all 30 WAVE2 episodes; W2-1 is
  the outlier within LOSS).

## Dominant Death Mode
**OBSERVED_NOT_ENGAGEABLE** (with UNOBSERVED component) — the White holds lost/stale tracks but dies
without own lock/hit.

## Death Mode Distribution
OBSERVED_NOT_ENGAGEABLE 14 (0.70) / CONTROLLER_NAVIGATION_PATHOLOGY 2 (0.10) / OTHER 4 (0.20).
(Partial: per-unit killer attribution not in frozen logs -> some deaths are "mixed"/unresolved.)

## First Actionable Warning
time ≈ 6,870 s (first stale tracks: vis=0, lost=4) — the White can see enemies existed but not hold them.

## First Irreversible Failure
time = 27,270 s (first combat-USV deaths, vis=0) — collapse begins.

## Earliest Actionable Divergence
**SENSING_VISIBILITY** (leaning) / ENGAGEMENT_RANGE — track->own-lock conversion at engagement range.

## C6B Trigger
triggered = **NO** ; action overrides = 0 ; reason = **NO_TRIGGER** (own-geometry cohesion gate never
armed; W2-1 units collapse together, not as isolated spearheads).

## W2-1 vs W2-2 Key Difference
W2-2 gets a live contact at ≈6,270 s and **holds it**, converting to locks/hits and surviving. W2-1
gets only stale tracks and dies before converting track->lock.

## Confidence
MEDIUM (timeline clear; per-unit killer/HP provenance NOT_MEASURED in frozen logs).

## Next Mechanism Concept (DO NOT IMPLEMENT)
SENSOR / EARLY-WARNING / track-maintenance at engagement range (concept only).
