# 11 — PRE-LOCK DEATH ANALYSIS (W2-6, seed 43001)

Death categories (from per-unit timeline; `own_lock` = ever `is_locking`):
| category | definition | W2-6 ACE | W2-6 C10 | W2-4 ACE |
|---|---|---:|---:|---:|
| A | died with NO positioned contact at all | 6 | 4 | 1 |
| B | positioned but died before reaching ≤40 km | see 03 csv | see 03 csv | 0 |
| C | reached ≤40 km but never own-locked | 2 (last report: 3) | 1 | 3 |
| **pre-lock total** | died before ever own-locking | **8** | **5** | **1** |
| D | own-locked then died | 10 | 11 | 5 |
| E | lost lock then died | (subset of D) | (subset of D) | (subset of D) |

The dominant extra losses on W2-6 vs W2-4 are **category A/B — units that die before they ever lock**.
Engine mechanism (01): the **first** incoming hit (one completed 300 s enemy lock) **freezes the victim
for 300 s** (motor stop, radar off) — so a unit that takes one hit cannot move or lock for 300 s, and the
second hit kills it. This is the **freeze → second-hit kill chain**: a unit's first hit almost guarantees
death because it cannot fight back during the freeze.

ACE: 8/18 deaths are pre-lock. C10 reduces to 5/16 (its packages get more units locking before the
freeze), but the residual pre-lock deaths still cap the exchange.
