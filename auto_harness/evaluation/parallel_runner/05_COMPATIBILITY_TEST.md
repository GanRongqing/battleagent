# 05 — COMPATIBILITY TEST

## Result schema
`result_aggregator.EP_FIELDS` is IDENTICAL to the E2 runner schema:
```
Strategy, Policy, Seed, Actual_Engine_Seed, Valid, Black_Killed, White_USV_Lost,
White_UAV_Lost, Exchange_Ratio, Exchange_Result, Terminal_Result, Sim_Time, Wall_Time
```
(`parallel_episodes.csv` adds only extra path columns downstream readers ignore.)

## Main metric definition (unchanged)
战损交换比 = Σ击毁黑方作战 USV / Σ损失白方作战 USV  (pooled, never mean-of-ratios);
正交换局数 = episodes with Black_Killed > White_USV_Lost. UAV excluded from the denominator.

## Backward compatibility
- The parallel runner does NOT touch or overwrite any existing E2 CSV
  (`auto_harness/combat_exchange/e2_ace_c7_seed_independent/*`); it writes to
  `auto_harness/evaluation/parallel_runner/` and `/tmp/opencode/parallel_runs/<run_id>/`.
- The E2 reader (same column names) can consume `parallel_episodes.csv` unchanged.
- Historical epochs (E0/E1/E2) are preserved; the parallel runner minted epoch `E2`/`EQ`/`BENCH` only
  for its own verification runs, kept separate from the frozen E2 samples.

## Verified sample
`parallel_episodes.csv` (from a 1-job resume run) reproduces the E2 result for W2-1 ACE 43001
(0 kills / 20 losses / Result.Defeat).
