# 00 — Scope (Stage A): bounded residual determinism audit

Goal: after the engine step mode made macro-step **timing** deterministic, find and (if local) fix the
first remaining **state** divergence between same-seed runs — or STOP after one bounded pass.

Budget: exactly one root-cause pass. No simulator rewrite.

Method:
1. 3 same-seed runs under `DETERMINISTIC_STEP_MODE`, capture `/status` at t=0/30/60 (`traces/`).
2. Field-level + entity-level diff (`01_FIRST_DIVERGENCE.json`, `02_FIELD_DIFF.csv`,
   `03_ENTITY_DIFF.csv`).
3. Trace the first divergent field to its writer (`04_ROOT_CAUSE_TRACE.md`).
4. Apply a local ordering/seeding fix only if clearly local (`05_FIX.md`), then re-test.
5. Record (`06_REPEATABILITY.csv`, `DETERMINISM_RESULT.md`).

Outcome: SOLVED (root cause = set iteration order in `judge_system.set_units`; one-line sort fix).
