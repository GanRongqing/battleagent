# Auto Harness Inventory

| phase | dir | purpose | outcome |
|---|---|---|---|
| phase0 | auto_harness/phase0/ | corpus mining (seeds 6001-6100, read-only) | corpus |
| phase1 | auto_harness/phase1/ | anti-leak containment (white-auto-0001-v1) | DEV supported / Fresh FAIL -> not promoted |
| phase1.5 | auto_harness/phase1_5/ | follow-up | see dir |
| phase2a | auto_harness/phase2a_lateral_coverage/ | lateral sensing coverage (white-auto-0002-v1) | DROP |
| phase2b | auto_harness/phase2b_forward_sweep/ | forward coordinated sweep (white-auto-0003-v1) | DROP (selection effect) |
| phase3 | auto_harness/phase3_assignment_engagement/ | assignment->engagement | AE-F5 later refuted |
| phase4 | auto_harness/phase4_track_freshness/ | track freshness | premise REFUTED (no candidate) |
| phase5 | auto_harness/phase5_lock_transition_audit/ | lock transition audit | NO_ACTIONABLE_ROOT_CAUSE |
| phase6 | auto_harness/phase6_oracle_decomposition/ | oracle headroom decomposition | INVALID_ORACLE - STOP |
| phase7 | auto_harness/phase7_oracle_guided/ | oracle-guided branch | WAITING_FOR_PHASE6 |
| detection audit | auto_harness/detection_quality_audit/ | detection quality | SELECTION_EFFECT |
| memory | auto_harness/evolution_memory/ | evolution ledger | — |
