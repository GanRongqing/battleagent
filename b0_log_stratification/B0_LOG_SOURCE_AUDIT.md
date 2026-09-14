# B0 Log Source Audit (READ-ONLY)

Goal: enumerate all valid B0_RANDOM evidence and decide which episodes carry the
geometry/velocity needed for the 27-class stratification.

| source | path | episodes | profile | validity | black geometry? | velocity? | used |
|---|---|---|---|---|---|---|---|
| legacy formal | logs_formal/S*_s*.log | 90 (S1/S2/S3 x 1001-1030) | B0 (default) | valid games | NO (White log only) | NO | excluded (cannot compute length/width/speed) |
| B0 common calibration | policy_system/calibration/traces/B0_RANDOM | 10 (S2 7001-7010) | B0 | valid | YES (black_behavior_trace) | YES | YES |
| B0 fresh | policy_system/evolution/auto_0001/fresh_b0 | 10 (S2 7101-7110) | B0 | valid | YES | YES | YES |
| B0 cross S1 | policy_system/evolution/auto_0001/cross_S1_b0 | 5 (S1 7201-7205) | B0 | valid | YES | YES | YES |
| B0 cross S3 | policy_system/evolution/auto_0001/cross_S3_b0 | 5 (S3 7201-7205) | B0 | valid | YES | YES | YES |

- fp-v1 B0 fingerprint source = logs_formal (93 files incl. 3 non-episode logs); these are
  valid games but carry no Black in-game geometry/velocity, so they cannot enter the
  length/width/speed stratification.
- Historical invalid opponent-profile smoke (profile not propagated to the simulator) is
  NOT part of any B0 source above; it is excluded by construction and was already removed
  in earlier work.
- Auto Harness corpus 6001-6100 is B3_ADAPTIVE, not B0 -> not a B0 source.
- Duplicates: episode identity = trace_hash (sha256 of the black_behavior_trace sidecar).
  All 30 candidate traces are unique -> duplicates removed = 0.
- Invalid within candidates: 2 episodes (calibration s7003, fresh s7107) have an episode
  median speed < 1 m/s (trace/velocity artifact; B0 combat USVs are commanded at 10 m/s).
  These are marked invalid/unclassified, NOT assigned to a class and NOT set to 0.

Result: valid_unique_B0_logs = 28 (of 120 B0 games; 90 lack Black geometry, 2 have an
unusable velocity signal).
