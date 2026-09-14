# Harness × Real BT Wide Validation

## 1. Frozen Configuration

- Agent / Skill / Prompt / allocator / TrackManager / GLOBAL_REACQUIRE / simulator physics / B0-B3 opponents: frozen (see config_manifest.json).

## 2. Unit / Contract Tests

- test_bt_harness_interface.py, test_bt_real_trees.py, test_bt_wide.py: see unit_test_summary.txt (all PASS).

## 3. Task Lifecycle

- submit NEW/DUPLICATE/revision/plan-revision/expired/future; cancel; preemption (priority / non-preemptible / safety-override); persistence 10 ticks; SUCCESS/FAILURE/RUNNING + memory continuation (see unit tests).

## 4. Action / Safety Feedback

- safety counters across 18 integration episodes: PASS=208368.0, CLAMPED=0.0, MODIFIED=0.0, REJECTED=0.0, OVERRIDDEN=0.0

## 5. Fair-Play / Single Writer

- direct BT network writes = 0; no-ground-truth audit PASS (poison-patch).

## 6. 18-Episode Integration Matrix (18/18 episodes recorded)

- clean wins = 0/18

- lifecycle anomalies = 0

## 7. Lifecycle Anomalies

- none

## 8. Acceptance Result

| gate | value |
|---|---:|
| engine_error | 0 |
| api_error | 0 |
| invalid_action | 0 |
| target_ownership_violations | 0 |
| action_channel_conflicts | 0 |
| direct_bt_network_writes | 0 |
| orphan_feedback_count | 0 |
| orphan_action_count | 0 |

**Acceptance: PASS** (interface-level gates must be 0; outcome clean-win is a policy attribute, not an acceptance gate).

