# 09 — E8 FINAL REPORT
- No code changes. E7 reused and re-verified from raw results (W2-6 14/13, W2-4 12/5).
- E7 winning config confirmed from the E7 command + source: HANDOFF=1, OBS_TI_REVIVE=0, V2=0.
- New runs (4, budget consumed): W2-2 ACE 0/20, W2-1 ACE 0/20, W2-6 C10 12/7, W2-4 C10 12/7.
- C10 pair invalid (identical enemy state = same route) → INCONCLUSIVE.
- W2-2/W2-1 pair identical → scenario separation unproven.
- Decision: freeze **ACE + LIFECYCLE_HANDOFF_V1=1** as FROZEN_VALIDATION_CANDIDATE; keep flags OFF by
  default; fresh-RNG validation required; do not promote C10.

## Verdict summary
- E7 interface fix: still the best evidence-supported candidate (E7 valid).
- C10 incremental: INCONCLUSIVE.
- Combat generalization: NOT_ESTABLISHED.
- Next: fix runner scenario separation + fresh-RNG epoch (see 08).
