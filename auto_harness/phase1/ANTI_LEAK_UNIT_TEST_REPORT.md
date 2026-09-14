# Anti-Leak Unit / Fair-Play / Equivalence Test Report

test_anti_leak.py = 12/12 PASS (WC-T1..T10 + W5-equivalence + source audit).

| test | requirement | result |
|---|---|---|
| WC-T1 | target moving away -> no trigger | PASS |
| WC-T2 | toward boundary but effective blocker -> no new blocker | PASS |
| WC-T3 | HIGH + no blocker + FREE -> exactly one extra blocker | PASS |
| WC-T4 | no free -> bounded preemption | PASS |
| WC-T5 | CRITICAL one blocker; no duplicate while present | PASS |
| WC-T6 | hysteresis: held before TTL, released after | PASS |
| WC-T7 | target killed -> release | PASS |
| WC-T8 | no risk -> identical to W5 | PASS |
| WC-T9 | hidden-truth counterfactual (same legal obs -> same action) | PASS |
| WC-T10 | variable cardinality 5/10/15 | PASS |
| equivalence | W5-equivalence outside trigger, 500 states 100% identical | PASS |
| fair-play | legal tracks only; no hidden truth / version cheat | PASS |

execution_override = false (allocator-only overlay).
