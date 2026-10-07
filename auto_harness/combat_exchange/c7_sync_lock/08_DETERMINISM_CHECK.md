# 08 — DETERMINISM CHECK  (GATE: FAIL)

Command: `python run_c7_eval.py --agent sync --strats W2-1 --seeds 43001 --runs 2 --det`

## Result
- OUTCOME identical across both runs: CER 0.1, Black_Kills 2, White_USV_Losses 20, Result.Defeat,
  Ever_OwnLock 7, Hostile_Locked 20, HostileLocked_Never_OwnLock 13, First_Death 07:32:30,
  First_OwnLock 08:07:00, Alive_End 0.
- Per-macro-step STATE HASH: **NOT identical** -> gate FAIL.
  - run1 total_steps=999, run2 total_steps=993 (6-step terminal offset).
  - Aligned at offset 0, the first **945 / 993** steps are byte-identical; divergence at step 945
    (T_EP 07:53:00).
  - Divergence = a **tie-flip between two White USVs**: `white_usv6`/`white_usv15` swap
    `is_frozen` (True/False <-> False/True), `locked_times` (1<->0), and x-position
    (119591<->120173). Two units differing; alive/kill counts identical.

## Root cause (engine, NOT C7)
`hsystem/simulation/arsenal/judge_system.py::_judge()` iterates Python `set`s whose order is by
object memory address (varies per process):
- `self.units` (lines 77, 108, 117)
- `self.black_ships` (line 99)
- `self.white_ships` (line 107)
The earlier determinism fix (commit 3a96b75) only added sorted `self.units_all` (used solely for the
lock-count aggregation at line 130); the death/breach/collision loops still iterate raw sets.
This is the same nondeterminism class as the fixed `set_units` bug, and it manifests only in long
runs (latent for 945 steps, surfaces near the terminal).

C7's own logic is deterministic (pure function of legal state; detection + package selection are
deterministic). The residual is in the frozen engine/judge layer.

## Status
Per the C7 gate ("Otherwise STOP"), the C7 evaluation is HALTED pending a decision.
