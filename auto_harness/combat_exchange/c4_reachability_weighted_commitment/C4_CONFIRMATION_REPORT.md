# C4_CONFIRMATION_REPORT.md — Stage B

## 1. Stage A determinism final status
**SOLVED.** Root cause = `set` iteration order in `judge_system.set_units` (varies per process);
fixed by sorting `units_all` by name. 3×30-macro-step order-dependent runs are STATE-IDENTICAL.

## 2. Same-seed semantics this round
**Strict paired trajectory initial condition** (physics + ordering deterministic). The eval was run
under `DETERMINISTIC_STEP_MODE`. Caveat: seeds 20001–20004 turned out to be effectively degenerate
(see §11), so pairing is exact but the sampled initial conditions are near-identical.

## 3. Did C4 reduce far/low-persistence extra commitment?
**NOT DIRECTLY MEASURABLE in this run** (no per-target reachability instrumentation). Proxy metrics
(`02_MECHANISM_METRICS.csv`) show **no change** vs ACE: mean coverage_frac 0.027 (ACE) vs 0.028 (C4);
mean max_lock 1.0 both; mean max_engaged 1.5 both. `03_REACHABILITY_BINS.csv` = NOT_MEASURED.

## 4. Pass-1 coverage kept?
Proxy: unchanged (0.027 → 0.028). No evidence of coverage loss.

## 5. Reachable-target concentration kept?
Proxy: unchanged (max_engaged 1.5 both). Note the absolute level is very low → in this regime the
allocator almost never performs Pass-2 concentration, so the C4 multiplier has little to act on.

## 6. Death-before-own-lock?
Proxy: unchanged (4/8 episodes both).

## 7. Assigned→lock?
Proxy: unchanged (mean max simultaneous locks = 1.0 both).

## 8. S1 combat improved?  §9. S6 combat improved?
| strat | ACE kills/losses | ACE CER | C4 kills/losses | C4 CER |
|-------|------------------|---------|-----------------|--------|
| S1 | 7/80 | 0.088 | 8/80 | 0.100 |
| S6 | 12/80 | 0.150 | 13/79 | 0.165 |

Both are within seed noise; no clear improvement.

## 10. Overall pooled CER
- ACE = 19 / 160 = **0.119**
- C4  = 21 / 159 = **0.132**
(marginal, not clearly separated)

## 11. Did the S6 12/9 vs 10/17 initial signal replicate?
**NO.** With the fixed ordering + fresh seeds, ACE S6 = 3/20 per seed (12/80 pooled) and C4 S6 =
13/79. The earlier 12/9-vs-10/17 single-episode signal did **not** replicate. All seeds 20001–20004
gave near-identical outcomes ⇒ the seed axis is degenerate here and the earlier signal was
single-seed noise.

## Note on metric source
`run_combat.py` counts unique `[KILL]` lines; the canonical `[META] enemy_kills` (reward
`black_killed`) differs (e.g. S1: 0 vs 7). This report uses the canonical `[META]` value.

## 12. C4 verdict
**INCONCLUSIVE (mechanism unconfirmed).**
- Mechanism: proxies unchanged; the reachability multiplier had little to act on (very low Pass-2
  activity) and the exact reachability-bin metric needs allocator instrumentation.
- Outcome: C4 marginally higher CER (0.132 vs 0.119) but inside the noise of a degenerate region
  where the white force is wiped (≈0–3 kills, ~20 losses per episode).
- Per gate: "combat CER up but mechanism metrics unchanged" ⇒ **MECHANISM UNCONFIRMED**, not KEEP.
- Recommendation: **DROP C4 as a standalone candidate** (do NOT promote); do not continue N10/N30.
