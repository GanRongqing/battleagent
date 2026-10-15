# 05 — C11 DESIGN: SPARE_SUPPORT_ONLY
- File `agent_hybrid_spare_support.py`, id `white-combat-0011-v1`, parent **C10**.
- ONE semantic change vs C10: a support candidate must be **unengaged** — farther than 40 000 m from any
  visible positioned track (`_engaged`). Otherwise C11 == C10 (same budget MAX_TOTAL_PACKAGES=3, same
  package, same lead slowing).
- Activation: C10 would form a package AND the chosen support would be engaged → suppressed.
- Active state: package formed only when a spare support exists.
- Termination/timeout/fallback: identical to C10 (member lock / target gone / MAX_SYNC_TIME=1200 s).
- Invalid-state recovery: unchanged (target/owner re-evaluated each step).
- Observables: `is_locking`, own positions, tracks (`is_visible`,`has_position`,`predicted_position`).
  No truth, no strategy name, no hard-coded time/unit IDs.
