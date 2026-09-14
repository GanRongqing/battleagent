# B0-B3 Common Policy Calibration Report

## 1. Objective

Prove policy identity from behavior (not names/params): do B0/B1/B2/B3 show stable, explainable empirical behavioral differences under fully common conditions?

## 2. Experimental Controls

- White: frozen W5 (agent_hybrid_v5.py)
- Scenario: S2 (White 10 USV + 10 UAV vs Black 20 combat USV)
- Seeds: 7001-7010 (DEV calibration, POLICY_FINGERPRINT_CALIBRATION_DEV)
- Instrumentation: cal-v1 (identical metric pipeline to formal runs; read-only /status sampler)
- Fingerprint: fp-v2 (behavioral + response separated)

## 3. Artifact Integrity

- B0..B3 sealed artifact bundles unique (see policy_artifacts).

## 4. Policy Propagation Proof

- B0 n=10/10
- B1 n=10/10
- B2 n=10/10
- B3 n=10/10 (each episode meta records requested=effective; B3 additionally has adaptive event sidecar per episode)

## 5. Behavioral Fingerprint v2

- behavioral block: temporal/spatial/coordination/adaptation groups; availability available/proxy/unavailable.
- adaptation from real runtime events (B3) or real zeros (B0/B1/B2: no replan mechanism).

## 6. Response Signatures

- response block kept separate (white_outcome).

## 7. Pairwise Difference Matrix

- see POLICY_DIFFERENCE_MATRIX_V2.csv and pair reports.

## 13. Multi-Seed Stability

- B0 vs B1: stable
- B0 vs B2: stable
- B0 vs B3: stable
- B1 vs B2: unstable
- B1 vs B3: stable
- B2 vs B3: stable

## 14. Within-Policy Variance

- see FP_V2_DISTANCE_CALIBRATION.md.

## 15. Strength vs Value

- A policy can be behaviorally distinct yet weak (low Black win / low White burden); behavioral novelty and evaluation value are assessed separately.

## 16. Admission Verdict

- B0 vs B1: **EMPIRICALLY_DISTINCT**
- B0 vs B2: **EMPIRICALLY_DISTINCT**
- B0 vs B3: **EMPIRICALLY_DISTINCT**
- B1 vs B2: **INCONCLUSIVE**
- B1 vs B3: **EMPIRICALLY_DISTINCT**
- B2 vs B3: **EMPIRICALLY_DISTINCT**

## 17. Remaining Gaps

- Multi-scenario (S1/S3): NOT_YET validated.
- In-game Black ground-truth spatial geometry (all ships) is not recorded by the simulator; spatial/coordination features are White-radar-visible proxies.
- contact_to_replan_latency and phase_switch_count unavailable (no per-event timestamps / no phase concept observable from current logs).