# 00 — Existing Evidence Inventory

| evidence | available | n | per-step state? | canonical assign? | lock? | hit? | kill? | white death? | visibility? |
|---|---|---|---|---|---|---|---|---|---|
| W5 baseline agent logs (11001/11002) | YES | 12 | partial (step line: avail/int/lock/frz) | NO (proxy [ASSIGN]) | aggregate only | NO | YES [KILL] | count only | TRACKS vis count |
| W5 baseline game logs | YES (reliable, sequential) | 12 | YES (usv_states position/is_locked/locked_attacker; active_enemies) | NO | is_locking (bool, no target) | NO (only white-frozen events) | YES (events) | YES (events) | YES (active_enemies) |
| W5 DEV agent logs (12101/12102) | YES | 12 | step line | proxy | aggregate | NO | YES | count | count |
| ACE DEV agent logs (12101/12102) | YES | 11 | step line | proxy | aggregate | NO | YES | count | count |
| ACE DEV game logs | CORRUPTED (parallel shared dir) | — | — | — | — | — | — | — | — |
| C1(survival) DEV agent logs | YES | 12 | step line | proxy | aggregate | NO | YES | count | count |
| ACE Fresh | INVALID (services killed mid-run) | 6 valid | — | — | — | — | YES | — | — |
| runtime_audit (run_ep4) | YES | 1 run (469 steps) | YES (A/B/E/F; E.allocator/controller) | **YES (canonical)** | via controller | no | no | no | via tracks |
| f1_root_cause_audit | YES | 12 (baseline) | — | proxy | — | — | — | — | — |

## Key limitation
Per-target **canonical assignment** exists only for `runtime_audit/run_ep4` (1 run). Per-target **lock target**
(`locking_unit`) is **NOT** present in game logs (only `is_locking` bool). So a target-level lock/hit funnel
is **NOT_MEASURED** for the full corpus; only aggregate `int`/`lock` USV-counts are available.
