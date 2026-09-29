# 00 — C4 Evaluation Plan (Stage B)

Policy A: ACE = `white-combat-0002-v1` (agent `expand`)
Policy B: C4  = `white-combat-0005-v1` (agent `reach`)
Strategies: S1 (`横向编队-中央汇聚箭头突防`), S6 (`菱形编队-MUSV外侧绕行SUSV中央收缩`)
Seeds (fresh, paired): 20001, 20002, 20003, 20004  → 4 × 2 × 2 = **16 episodes**

## Mode
Stage A = SOLVED ⇒ run under `DETERMINISTIC_STEP_MODE=true` so same seed = **strict paired
trajectory initial condition**. (The judge_system ordering fix is active in all modes.)

## Timeout
Raised to 1800 s/episode; record wall-clock, sim-time cutoff, and terminal reason. If a run is cut,
mark it INVALID rather than judging it (S1 previously hit a no-contact long episode).

## Metrics
- Combat: black kills, white USV losses, CER=kills/losses; pooled CER = Σkills/Σlosses (never mean).
- Mechanism (from per-step agent logs): Pass-1 coverage proxy (tracks with >=1 owner), Pass-2 extra
  commitments (lock count vs tracked), assigned→lock conversion, death-before-own-lock (USV lost while
  never having appeared as `lock` for it), long-no-lock approach. Reachability bins from C4 formula:
  HIGH (reach=1, urgent or d<=0), MED, LOW (reach=0.25).
- Paired-seed comparison ACE vs C4 per (strategy, seed).

## Outputs
`auto_harness/combat_exchange/c4_reachability_weighted_commitment/`:
`fresh_eval/{raw,summaries,figures}` + `01_EPISODE_RESULTS.csv`, `02_MECHANISM_METRICS.csv`,
`03_REACHABILITY_BINS.csv`, `04_COMBAT_SUMMARY.csv`, `05_PAIRED_SEED_COMPARISON.csv`,
`C4_CONFIRMATION_REPORT.md`, FIG1..FIG6.

## Gates
- Mechanism PASS: Pass-1 coverage not materially down; LOW-reachability Pass-2 commitment clearly
  down; HIGH-reachability concentration not erased; death-before-lock or long-no-lock improves.
- Verdict KEEP only if Mechanism PASS **and** pooled CER clearly better with no systematic strategy
  regression. Otherwise PARTIAL / DROP / INCONCLUSIVE.
- No parameter tuning, no new heuristics, no N10/N30 auto-expansion.
