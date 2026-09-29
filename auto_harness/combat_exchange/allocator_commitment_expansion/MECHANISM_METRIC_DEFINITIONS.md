# Mechanism Metric Definitions

This phase retires the F1-A fraction as the primary cross-policy mechanism metric and replaces it
with outcome-independent metrics. All metrics below are computed from the agent stdout logs using
the step-level `[ASSIGN]` PROXY (frozen W5 emits no canonical owner-map instrumentation; the proxy is
a clearly-labeled approximation, not canonical).

## 1. F1-A fraction (RETIRED as primary; kept descriptive)
- unit of analysis: target-episode
- numerator: detected-but-never-assigned (and not killed) targets
- denominator: detected-but-not-killed targets
- outcome-conditioned = **YES** (the denominator shrinks when ACE kills more)
- suitable for cross-policy comparison = **NO** (post-treatment denominator confound)
- usage: report W5 vs ACE but label "descriptive / post-treatment-conditioned".

Why misleading: ACE → more kills → "detected-but-not-killed" denominator shrinks → the remaining
targets are the harder ones → the fraction can stay flat or RISE even though absolute under-commitment
fell (observed: never-assigned 146→89, but fraction 85.4%→89.0%).

## 2. UOR — Undercommitment Opportunity Rate (primary)
- unit: target × decision-step
- numerator: sum over steps of (actionable target AND owner_count==0 AND free_combat_usv_exists)
- denominator: sum over steps of (actionable target AND free_combat_usv_exists)
- outcome-conditioned = NO
- cross-policy = YES

## 3. Assignment Coverage (primary)
- unit: target-episode
- numerator: actionable target-episodes that received >=1 assignment at least once
- denominator: actionable target-episodes (ever visible+actionable)
- outcome-conditioned = NO
- cross-policy = YES

## 4. TTFA — Time To First Assignment
- unit: target-episode (assigned only)
- first_actionable_time → first_assignment_time (assigned only)
- unassigned reported separately (not a fake large value)

## 5. IWE Rate — Idle While Work Exists (primary)
- unit: decision-step
- numerator: steps with free_combat_usv_count>0 AND zero_owner_actionable_target_count>0
- denominator: combat-active decision steps
- outcome-conditioned = NO

## 6. Commitment Utilization
- assigned_combat_usv / available_combat_usv (mean/median/p90)
- free = alive + not frozen + no current target (controller AVAILABLE state)

## FREE_USV_DEFINITION (frozen, unchanged from DEV)
alive AND combat-capable AND no valid active commitment AND no stable lock task AND no first-hit
kill-closure obligation AND no safety emergency AND not frozen/dead/unavailable.
(Reconstructed proxy: controller AVAILABLE state = not locking + no [ASSIGN] target + alive.)
