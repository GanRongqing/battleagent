# 03 — SEED & DETERMINISM TEST

## Seed plumbing (fixed in d8329c4, preserved)
Each Worker owns `parallel_runs/<run>/w<i>/seed.txt`, exported as `RW_SEED_FILE` to its base_server
(hence to its sim_server child). The engine reads it at `/start` via `adaptation._seed_rng()`.
No shared seed file exists.

**Test B — seed independence (PASS):** different seeds -> different engine RNG init (controlled
`adaptation._seed_rng` draws), same seed reproduces. `test_seed_independence.py: PASS`.

## Test A — serial vs parallel equivalence (PASS)
Workload: W2-1 ACE 43001 + W2-4 ACE 43001.
- serial: `--workers 1`, run_id `serial_ref`, wall = 2496.6 s
- parallel: `--workers 2` (both episodes active simultaneously), run_id `eq_parallel`, wall = 1497.0 s

| episode | serial traj hash | parallel traj hash | steps | kills/losses | identical |
|---|---|---|---|---|---|
| W2-1 ACE 43001 | 8753da9445f81a9e | 8753da9445f81a9e | 991 | 0/20 = 0/20 | YES |
| W2-4 ACE 43001 | e789c219a95614f7 | e789c219a95614f7 | 1407 | 12/6 = 12/6 | YES |

Per-step state / actions / kills / losses / terminal / engine seed all identical.
**SERIAL_PARALLEL_DETERMINISM = PASS.**

## Test C — two identical seeds concurrently
Covered by isolation: workers never share a seed file; each Worker's game log lives in its own
`api_logs/`. (Dedup by job identity prevents double-counting identical jobs in one run.)

## Test D — log isolation
Per-worker dirs verified in `test_worker_isolation.py` (distinct seed file, api_logs, cwd, ports;
env `RW_SEED_FILE` and `PYTHONPATH` point at the worker's private paths). **PASS.**
