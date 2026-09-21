# BattleAgent / Harness

A maritime multi-agent combat harness: a White agent controls USVs/UAVs against a
configurable Black opponent inside a simulator, through a POMDP HTTP API.

- GitHub: https://github.com/GanRongqing/battleagent
- Working tree: this directory (`hsystem/`). The git repository is the synced mirror
  (`../githsysys`, branch `main`).

## Current Stable Baseline

**W5** — `agent_hybrid_v5.py` (frozen).

- Source sha256: `e823e7bed219f469…` (`source_sha256`)
- Legacy frozen policy hash: `a7842b29c81cc567…` (`legacy_source_sha256`)
- See `docs/acceptance_evidence/HASH_SEMANTICS.md` for the difference.

W5 behavior is frozen. Do not modify `TrackManager`, `ThreatAllocator`, `USVController`,
`UAVManager`, `ActionSafety`, weapon/radar/physics/judge.

## Architecture

```
Simulator  ->  POMDP API (:8000)  ->  W5 Agent  ->  ActionSafety  ->  Simulator
```

Component map with line numbers: `docs/acceptance_evidence/ARCHITECTURE_SOURCE_MAP.md`.

## Quick Start

Full tutorial: `docs/Harness_策略系统运行_集成与升级教程_v1.0.*` (**TODO: not generated yet**).

Minimal:

```bash
# 1) install deps (env: hsystem_env recommended)
pip install -r hsystem/requirements.txt

# 2) start backend + API
bash docs/acceptance_evidence/RUNTIME_COMMANDS.sh   # or see BACKEND_STARTUP_REFERENCE.md

# 3) run one canonical W5 episode (LLM off)
python scripts/acceptance/run_single_w5.py

# 4) run core tests
python agent_hybrid_v5.py --selftest
python agent_hybrid_v5.py --scaletest
python test_v5_units.py
```

## Acceptance Evidence

`docs/acceptance_evidence/` — see `README.md` and `EVIDENCE_PACK_INDEX.md` there.
Verified this round: S2 × B0_RANDOM seed 1001 → `Result.Victory` clean, kills=20, usv_loss=4,
sim_time=13663, wall=309s (LLM off). See `SINGLE_EPISODE_RUN.md`.

## Evaluation

- `run_opponent_formal.py` — W5 vs Black profiles (B0–B3).
- `run_formal_eval.py` — formal evaluation.
- `run_external_opponent.py` — external opponents (dispersed / two-wave).
- `run_replay_set.py` + `verify_replay_set.py` — two-sided replay set.
- Command catalog: `docs/acceptance_evidence/EVALUATION_COMMANDS.md`.

## Policy / Skill

- `skills/` — strategic doctrine (`maritime_commander/SKILL.md`), consumed by the optional LLM commander.
- `strategy_library/` — policy cards, artifacts, fingerprints, validations (SQLite).
- `auto_harness/` — offline evolution phases (see `AUTO_HARNESS_INVENTORY.md`).

## BT / MARL

- **BT**: implemented and interface-tested (`bt_harness_interface.py`, `bt_real_trees.py`) but
  **NOT** the frozen W5 default execution path.
- **MARL**: integration point is documented (decision output: platform/task/target), not raw control.
  See `MARL_INTEGRATION_REFERENCE.md`.

## Known Issues

`docs/acceptance_evidence/KNOWN_ISSUES.md`.

## Logs

`docs/acceptance_evidence/LOGGING_REFERENCE.md`.
