# Candidate 01 — SURVIVAL_AWARE_ENGAGEMENT

- policy_id: white-combat-0001-v1
- parent: W5 (agent_hybrid_v5.py, sha e823e7be…)
- mechanism: SURVIVAL_AWARE_ENGAGEMENT (single mechanism)

## Root-cause evidence
White USV attrition dominates CER=0.73. 81% of White deaths occurred without a valid lock,
39% isolated; committed targets are killed at high rate. => the failure is White USVs dying
while exposed (pressing targets they cannot lock / patrolling into the enemy), not kill closure.

## Rule
For each alive combat USV, if ALL of:
  1. EXPOSED: `is_locked` OR `locked_attacker` non-empty (enemy is locking this USV), AND
  2. NO KILL OPPORTUNITY: no lock held AND no track within LOCK_RANGE (40 km), AND
  3. FAR FROM SUPPORT: nearest friendly USV > 50 km,
then DISENGAGE toward the nearest friendly USV (rejoin support), overriding the normal
pursue/patrol action.

## Release / re-engage
- Re-engage automatically when: support restored (< 50 km), OR a lock/kill opportunity appears,
  OR the USV is no longer exposed. No persistent state; decided each step from live observation.

## Explicitly NOT changed
- Detection / CoverageMap / sensor / TrackManager semantics.
- Physics / weapon / radar / lock range / speed / black route / judge.
- KILL_CLOSURE and LOCAL_OVERMATCH are NOT added (one mechanism per generation).

## Fair-play
Uses only White legal observation (own state + is_locked/locked_attacker/position + tracks belief).
No hidden truth, no scenario identity, no future path.
