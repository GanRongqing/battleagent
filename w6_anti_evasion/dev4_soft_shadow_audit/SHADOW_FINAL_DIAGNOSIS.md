# Protected SOFT Trigger — Live Shadow Diagnosis
LIVE DATA runs=3 seeds=4001-4003 decisions=2165
SHADOW raw=1487 rate=0.687/dec unique=156 raw/unique=9.5 unique/run~52
STABILITY stable300=52 stable600=32 stable1200=16
REVERSAL/decay: ~80% of opportunities gone by 600s (mean duration ~302s)
PROTECTION near-lock violations=0 unique=0 coverage=0
CASE QUALITY (heuristic) STRONG_GOOD(upper, stable600)=32 PLAUSIBLE~20 TRANSIENT~104 BAD=0
ATTRIBUTION risk-shift=156 (definition) prediction/coverage: see offline SOFT audit
RUNTIME latency=not-measured; perturbation low by design (pure read+append)
DETERMINISM PASS | HIDDEN-TRUTH PASS | DECISION-NEUTRAL PASS
FINAL CASE = B (temporally transient) with a minority stable>=600s subset (potential A)
PRIMARY FINDING = unique opportunities exist (~52/run) but are mostly transient (median ~300 s);
only ~20% persist >=600 s -> direct live SOFT rebalancing risks churn.
ONE RECOMMENDED NEXT STEP = investigate stability/persistence abstraction (e.g., only act on
opportunities that persist >=600 s) BEFORE any live implementation; no live trigger now.
