# 17 — CONTROL REGRESSION CHECK
| Control | ACE pooled CER | C7 pooled CER | delta | ACE exchange wins | C7 exchange wins |
|---|---|---|---|---|---|
| W2-2 | 0.211 | 0.211 | 0% | 0/5 | 0/5 |
| W2-4 | 2.000 | 1.366 | **-32%** | 5/5 WIN | 3/5 WIN, 2/5 TIE |

W2-2: no change. W2-4: **-32% pooled CER** and exchange-win degradation (5/5 -> 3/5) -> triggers the
CONTROL_REGRESSION signal (>20% drop or obvious exchange-win degradation).
Note: W2-4's own-lock count is UNCHANGED (14->14); the harm comes from C7 forming packages on targets
ACE was already winning (W2-4 had the most package formations: 30 of 40), perturbing an already-working
engagement.
Verdict: **control regression = YES (localized to W2-4).**
