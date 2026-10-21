# 01 — EPISODE PROVENANCE FIX
## Why the earlier misattribution happened
- `worker/base_server.log` is the **process** stdout shared across the worker's life; it had no
  episode/scenario tag, and the judge's breach print is plain text → mixing W2-4 (w1) with W2-5 (w3).
- Agent log names `ep_{seed}_{agent}.log` lacked scenario/episode → overwrite/mis-association risk.
- Duplicate game logs (same episode saved twice) could be mistaken for two runs.

## What was added (read-only / default OFF)
1. **Episode-tagged breach diagnostic** in `judge_system._judge` (env `BREACH_TRACE`, `EPISODE_ID`):
   one JSONL line per breach with `episode, kind, time, unit, x, y, breakthrough_count`. Writes only;
   never enters `/status`, TrackManager, or the agent.
2. **Episode identity helpers** (`provenance.py`, tested 5/5): unique `episode_id`, scenario-included
   agent log names, attempt ids, and content-hash dedupe of game logs.
3. **Episode manifest** (`02_EPISODE_MANIFEST.json`) recording run/id/attempt/worker/scenario/route digest/
   policy/seed/engine hash/game log/result.

## Process vs episode boundary
- For precise attribution this round used **one episode per invocation** (unique `--run-id`, workers=1) and
  set `EPISODE_ID`/`BREACH_TRACE` at the invocation, inherited by base_server→sim_server→judge.
- Multi-episode workers remain **not provenance-safe** (env is process-scoped); documented as a limitation.

## Behaviour neutrality (VERIFIED)
E15 W2-5 C10 with `BREACH_TRACE=1` reproduces the E9 baseline exactly: trajectory `384b46b27af4`,
27/14, Defeat — identical to the un-instrumented baseline. Trace ON/OFF neutral. VERIFIED.
