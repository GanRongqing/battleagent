# 01 — LOCK ENGINE SEMANTICS (VERIFIED against `locker.py` / `engine.py`)
- Factions: **White Agent = RED**, Black = **BLUE** (locker/engine naming).
- Lock command requires target in the detected set **and distance < 40 km**; registers a chain on the
  **target's** locker (`target.locker.is_locked(attacker)`), sets the attacker's single outgoing lock.
- A chain completes when it stays < 40 km for **> 300 s** (`_locked_work`); on completion one hit roll:
  `_stable_rand(attacker,target,int(t)) > 0.2` → **hit ~80%**, else miss. The chain resets either way.
- A hit sets that chain's `locked_times += 1` and **freezes** the target for 300 s (freeze ≠ lock start).
- Kill when `sum(locked_times over all attacker chains) >= 2` (two cumulative hits, possibly from
  different attackers); also kills one carried plane.
- Chains from different attackers are independent; `locked_times` is NOT reset on unfreeze.
- Range break = chain `locked=False` (no hit); it can be re-locked later (LOCK_RESTART).
- Action can be legal (`/legal_actions`) yet fail if the attacker already holds another lock (`is_locking` false).
All confirmed — **engine combat rules unchanged**.
