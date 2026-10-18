# 12 — MINIMAL VALIDATION
- H1 (flag OFF equivalence): PASS (unit-level; V2 code paths are bookkeeping-only; no behaviour read).
- H2 (offline replay on E6 ON trace): verifier reports **209 `ACTIVE_AFTER_KILL` unit-steps** and
  **139 revive events** (first usv13 @7830) → lifecycle contract detects the defect.
- H3 (minimal integration): used the two required deterministic traces W2-4 ACE seed 43001:
  OFF **12/6 (2.000)** vs ON **9/20 (0.450)** with first action divergence step 272 (t=8160).
  These are behaviour-consistency checks, NOT a combat-benefit claim.
- Total full runs this round: **2** (W2-4 OFF trace, W2-4 ON trace). No C10/C11, no extra seeds.
