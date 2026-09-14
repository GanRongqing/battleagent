# Declared vs Empirical Consistency (fp-v2, S2 common calibration)

| Policy | Declared key trait | Empirical feature | Evidence | Verdict |
|---|---|---|---|---|
| B0 | random, low coordination | coordination/timing signatures | no adaptive events; random approach timing | NO low-sync/random proxy is unavailable; replan/lane/dispersion events = 0 (true zero) |
| B1 | multi-axis spatial groups | spatial proxies (lane entropy / visible group metrics) | approach_lane_entropy, mean_visible_group_count | PARTIALLY_SUPPORTED via White-radar-visible geometry proxies (not Black ground truth) |
| B2 | coordinated pressure / timetable | arrival_front_sync, group spacing | arrival_front_sync_std_s, mean_group_spacing_km | PARTIALLY_SUPPORTED via arrival-front proxy |
| B3 | legal-observation adaptive replan | adaptive_replan/lane_shift/dispersion/detection counts | B3 runtime event counters (sidecar) | SUPPORTED if counts>0 on >=9/10 seeds (empirical) |

Honest limits: in-game Black ground-truth geometry (all 20 ships) is NOT recorded by the simulator; spatial/coordination metrics are White-radar-visible proxies (flagged proxy) and Black is not receiving any hidden White truth.
Multi-scenario (S1/S3) fingerprinting not run this round: multi_scenario = NOT_YET.