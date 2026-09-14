# Protected SOFT Trigger — Live Shadow Audit
## 1 Motivation: 5876 offline strong is only an upper bound; live temporal stability unknown.
## 2 Trigger: minimal rule above (LOW/MED->HIGH/CRITICAL priority inversion), FREE-only none.
## 3 Decision neutrality: PASS (real = W5; shadow logs only).
## 4 Live dataset: 3 runs S2xB3 seeds 4001-4003, real policy W5; 2165 allocator decisions.
## 5 Raw frequency: 1487 raw proposals (0.687/decision) - frequent in raw terms.
## 6 De-dup: 156 unique opportunities (raw/unique 9.5) -> most raw are repeats of few episodes.
## 7 Temporal stability: +300s 52 (33%), +600s 32 (20%), +1200s 16 (10%); mean opportunity 302 s.
## 8 Reversal risk: implied by decay (~80% gone by 600 s) -> churn risk if implemented directly.
## 9 Priority-inversion persistence: median short (~300 s); only ~20% persist >=600 s.
## 10 Mechanism: all proposals are risk-shift LOW/MED->HIGH+ (definition); prediction/ETA &
##     coverage-recovery signals noted in offline SOFT audit (not re-attributed per-case here).
## 11 Case quality: heuristic STRONG_GOOD upper bound 32 (stable>=600), PLAUSIBLE ~20,
##     TRANSIENT ~104, BAD 0.
## 12 Runtime overhead: 2165 logged decisions; latency not measured live (PERTURBATION low by
##     design - pure read + one jsonl append per decision).
## 13 Fair play/determinism: PASS.
## 14 Final diagnosis: CASE B (trigger too transient) with a credible but minority stable
##     >=600s subset (CASE A not yet demonstrated).
## 15 Next: study stability/hysteresis abstraction; do NOT implement live trigger yet.
