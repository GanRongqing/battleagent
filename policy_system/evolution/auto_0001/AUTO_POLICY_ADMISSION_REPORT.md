# AUTO_POLICY_ADMISSION_REPORT — black-auto-0001-v1 (FEINT_SWITCH_V1)

## Admission verdict
**EMPIRICALLY_DISTINCT_ACTIVE** (status active/sealed; evaluation_role stress_test)

## Gates
| gate | result |
|---|---|
| unique immutable policy_id | PASS (black-auto-0001-v1) |
| complete PolicyCard | PASS |
| unique bundle hash | PASS (595e0f8bf8bea1b7...) |
| fair-play (legal observation only) | PASS (AUTO-T8 + source audit) |
| variable cardinality 3/10/20/30/50 | PASS (AUTO-T2/T9) |
| profile propagation | PASS (requested=effective per episode meta) |
| S2 N>=10 fingerprint | PASS (10/10) |
| candidate vs B0-B3 compared | PASS (all 4) |
| EMPIRICALLY_DISTINCT from nearest | PASS (nearest B0, dist 1.27) |
| fresh seed set validates | PASS (7101-7110, dist 1.31, EMPIRICALLY_DISTINCT) |
| S1/S3 core signature preserved | PASS (S1 1.35, S3 1.44, multi_scenario=YES) |
| tactical coherence | PASS (phased feint->switch->main push, reserve commit) |
| evaluation value identified | PASS (distinct phased pressure; longer resolution) |

## Behavioral identity (S2 means)
- phase_switch_count = 1.6 (B0-B2 = 0, B3 continuous)
- continuous_replan_count = 13.2 (B0-B2 = 0, B3 ~620)
- reserve_fraction = 0.805 (B0-B3 ~0.03)
- role_asymmetry_index = 2.16 (B0-B3 ~0.31-0.40)
- dominant_axis_shift_count = 1.0 (B0-B3 0-0.1)

## Response signature (vs W5, S2)
- clean = 0.80, victory = 0.90, breakthrough = 0.20, friendly loss = 8.4,
  enemy kills = 19.7, resolution = 29395s

## Nearest neighbor
B0 (behavior distance 1.27). vs B2 distance 1.384; vs B3 1.435; vs B1 1.479.

## Primary distinctive behavior
Discrete phased role-asymmetric feint -> main-axis switch with reserve, low
continuous replanning.

## Primary weakness
Feint wastes time if White does not over-commit; delayed main commitment and
discrete switch raise resolution (29395s vs B0 15799s).

## Remaining gaps
- Response trigger (legal White-response detection) did not fire within the timeout
  on tested seeds; all switches used the bounded timeout fallback. A v2 could tune
  RESPONSE_RADIUS/timeout, but v1 is immutable and already empirically distinct.
