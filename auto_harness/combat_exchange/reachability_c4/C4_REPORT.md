# C4 — white-combat-0005-v1 REACHABILITY_WEIGHTED_COMMITMENT

Parent: ACE (`white-combat-0002-v1`). Mechanism: ONE.

## Motivation (from `c3_root_cause_and_determinism/la_f1_audit`)
Dominant residual no-lock cause = **LA1-E WHITE_DIED_BEFORE_CLOSURE (48.2%, 6/6 strategies)**:
a committed USV dies while still transiting to its target (profile: far, min ~102 km, half-lost
vis~0.53). W5/ACE score targets by breakthrough-proximity + confidence but ignore the **travel cost
from the free USVs**, so multiple USVs are sent on long exposed transits that end in death pre-lock.

## Mechanism (exactly one)
REACHABILITY DECAY applied to the **concentration pass (Pass 2) only**:
- Pass 1 (coverage floor) UNCHANGED — every actionable ship still gets >= 1 attacker (no free runner).
- Pass 2 value = `base_value * reach`, where
  `reach = clamp(REACH_FLOOR=0.25, 1 - d_near/REACH_SCALE=250km, 1)` and `d_near` = distance from the
  nearest FREE combat USV to the target. Far targets attract fewer overmatch attackers; near targets
  keep their concentration.
- Emergency exemption: target inside the urgent line (x < URGENT_X) ⇒ `reach = 1`.

Does NOT touch detection/track/coverage/lock/weapon/ranges/speed/scenario/sim/judge; legal
observation + TrackManager belief only (no hidden truth).

## Files
- `agent_hybrid_reach_commit.py` — `ReachabilityAllocator(ExpandingAllocator)` + `ReachCommitAgentMain`.
- `test_reach_commit.py` — unit tests.
- `run_agent_wrapper.py` / `run_combat.py` — added `reach` option.

## Unit tests — 6/6 PASS
```
PASS A_coverage_floor_unchanged
PASS B_reach_decay_prefers_near_target
PASS C_urgent_target_exempt_from_decay
PASS D_matches_ace_when_all_near
PASS E_reach_factor_bounds
PASS F_no_free_usv_noop
```
Key: B proves a far target (same breakthrough-x, 300 km lateral) gets **only coverage (1 attacker)**
while the near target receives the concentration; D proves it is a strict no-op when all targets are
reachable (so it cannot regress the near-field behaviour).

## Diagnostic (S1/S6, seed 12301) — INCOMPLETE
| strat | C4 result (from run log) | ACE (same seed, prior) |
|-------|--------------------------|------------------------|
| S1 | no contact observed, 0 kills, 0 losses (episode did not terminate within 600 s wall) | 14/8 |
| S6 | 12 kills / 9 losses at step 640 (also did not terminate in 600 s) | 10/17 |

S6 is directionally consistent with the hypothesis (fewer white losses, more kills) but **S1 is
no-contact and both runs were cut by the harness timeout**, so this is NOT a valid comparison.
S1 no-contact is very unlikely to be caused by C4 (C4 changes only Pass-2 allocation, not sensing);
it is more likely seed/scenario timing.

## Status
- Mechanism implemented, unit-tested (6/6), behaviour-gated (no-op when all reachable).
- Diagnostic **INCONCLUSIVE** (episodes not completed). Needs paired fresh-seed runs (>= 4 seeds x
  S1/S6) with a longer harness timeout before any keep/drop decision.
- Recommendation: **HOLD** (do not claim KEEP/DROP yet).
