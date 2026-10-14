# 00 — CURRENT BASELINE (E2, POST_SEED_PLUMBING_FIX) — 40/40 VALID

## Freeze
- Engine epoch: **E2** (seed plumbing fixed; deterministic step mode; locker deterministic hit).
- Parent: ACE `agent_hybrid_allocator_expand.py` SHA256 `7527253c…dc809497`.
- Candidate under study: C7 `agent_hybrid_sync_lock.py` SHA256 `98b655e8…fd8f98`.
- Runner: `run_c7_paired.py`/`run_e2_eval.py` + parallel completion (`e2c2`); all E2 rows share epoch E2.
- Do NOT mix E1/E2.

## E2 main results (Σkills/Σlosses, 5 seeds each)
| 敌方策略 | 版本 | 局数 | 击毁黑方 | 白方损失 | 战损交换比 | 正交换局数 |
|---|---|---:|---:|---:|---:|---:|
| W2-1 | ACE | 5 | 0 | 100 | 0.000 | 0/5 |
| W2-1 | C7  | 5 | 0 | 100 | 0.000 | 0/5 |
| W2-6 | ACE | 5 | 50 | 90 | 0.556 | 0/5 |
| W2-6 | C7  | 5 | 55 | 80 | **0.688** | 0/5 |
| W2-2 | ACE | 5 | 20 | 95 | 0.211 | 0/5 |
| W2-2 | C7  | 5 | 20 | 95 | 0.211 | 0/5 |
| W2-4 | ACE | 5 | 60 | 30 | **2.000** | 5/5 |
| W2-4 | C7  | 5 | 56 | 41 | 1.366 | 3/5 |

## Own-lock (mechanism)
- W2-6: ACE 11 units ever own-lock; C7 **15** (hostile-locked-never-own-lock 8 -> 5).
- W2-4: ACE 14; C7 14 (unchanged) — C7 regresses outcome without changing own-lock.

## Control regression
- W2-4 (positive control): ACE 2.000 -> C7 1.366 (-32%); exchange wins 5/5 -> 3/5. **CONTROL_REGRESSION.**
- W2-2 (control): unchanged.
- W2-1: zero-lock, seed-insensitive (no positional in-range contact) — not this round's target.

## Verdict carried in
C7 = CONTROL_REGRESSION (do not promote). Focus this round: **W2-6 partial gain** (0.556 -> 0.688),
explain it and try to convert it toward exchange > 1 without breaking W2-4.
