# 14 — C6B Trigger Audit (W2-1 seed 43001)

- admission evaluations: per assigned pre-lock USV each step (many)
- SHAPE_AND_WAIT trigger count: **0** (grep of C6B log = 0 admission events)
- action overrides: 0 ; unique USVs overridden: 0

**CASE 1: trigger count = 0** -> C6B never covered the real W2-1 failure state.
Reason: W2-1's USVs are rarely "forward-overextended beyond local friendly support" by the gate's
own-geometry definition (they die together in a tight collapse, not as isolated spearheads), so the
pre-lock cohesion gate is never armed. Stage-A signal (own-geometry cohesion) did not match the actual
failure state. ACE vs C6B W2-1 action trace is identical (no first action divergence).
