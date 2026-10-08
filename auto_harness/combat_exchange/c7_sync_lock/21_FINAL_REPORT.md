# 21 — C7 FINAL REPORT

Candidate: white-combat-0008-v1  agent_hybrid_sync_lock.py  SHA256=98b655e86a4f632c85e8a96023c966d39bedb636a4a469451a1548787efd8f98
Parent: ACE (7527253c6d5a4bba198e478a990443354ecf5d8cf4e1c98ace66ce50dc809497)

## Pipeline
- Stage A actionability: ACTIONABLE (W2-1 7/20 own-lock vs W2-2 13/15; pre-fix engine).
- Unit tests: 15/15.
- Determinism gate: **PASS** — required a deeper engine fix (order-independent deterministic lock-hit in
  `locker.py`; the judge_system fix and PYTHONHASHSEED=0 alone were insufficient).
- Eval: full **ACE re-baseline** (engine RNG changed) + C7, W2-1/W2-6/W2-2/W2-4 x seeds 43001-43005
  = 20 + 20 episodes.

## Headline
- W2-6 (hard): ACE CER 0.556 / 11 own-lock -> C7 0.688 / 15 own-lock (+24% CER, +36% own-lock; HARD case gain).
- W2-1 (hard): no effect (0/0).
- W2-4 (control): ACE 2.000 -> C7 1.366 (-32%; exchange wins 5/5 -> 3/5) -> CONTROL_REGRESSION.
- W2-2 (control): no effect.

## Verdict: CONTROL_REGRESSION (confidence MEDIUM)
Mechanism supported on W2-6; decisive control regression on W2-4. Do not proceed to 12-strategy
regression; do not auto-tune.

## Caveat
Under the fixed engine, the nominal seed is still not fed to the engine (fixed `seed_det.txt`), so
per-strategy rows are near-identical across nominal seeds; W2-4 split into two clusters (1.714 / 1.0),
indicating residual run-to-run variation beyond the locker fix. Results are directional, not precise.
