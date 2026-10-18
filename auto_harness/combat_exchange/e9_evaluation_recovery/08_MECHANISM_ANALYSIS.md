# 08 — MECHANISM ANALYSIS
## E7 reproduced under verified identity
- W2-6: ACE OFF 10/18 (0.556) -> ACE+E7 **14/13 (1.077)** — exactly the E7 result, now with Layer-3
  identity (`route5` digest `4b80fe82…`) verified. **E7's W2-6 positive exchange is REAL.**
- W2-4: ACE OFF 12/6 -> ACE+E7 **12/5 (2.400)** — reproduced. The control does not regress; it improves.
=> E7's earlier numbers were NOT an artifact of scenario miscabling.

## But E7 is TARGETED, not global
- W2-3: ACE 1.154 -> 0.588 (-49%); C10 0.800 -> 0.588. Restoring falsely-killed live targets changes
  assignment on W2-3 and degrades it.
- W2-5: ACE ~flat (1.067->1.000); **C10 1.929 -> 0.938 (-51%)** — C10's coordination plus revive hurts W2-5.
- Pooled: ACE+E7 0.633 vs ACE OFF 0.626 (+0.007, negligible); C10+E7 0.626 vs C10 OFF 0.725 (-0.099).
=> The fix produces a large local win (W2-6) and a control-scenario win (W2-4) but trades away W2-3/W2-5.

## C10 incremental value under E7
- C10 OFF is the best pooled old version (0.725), driven by W2-5 (1.929).
- C10+E7 is best on W2-6 (1.231) but loses W2-5 (0.938) and W2-4 (1.714 vs ACE+E7 2.400).
- Net: `C10_INCREMENTAL_EFFECT = NEGATIVE_TRADEOFF` (W2-6 gain at W2-4/W2-5 cost; pooled no better).
