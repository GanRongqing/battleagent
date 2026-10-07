# 05 — C5 SEMANTIC DIFF (vs ACE / white-combat-0002-v1)

UNCHANGED:
- allocator (ThreatAllocator / ExpandingAllocator commitment + reserve release)
- coverage / mission / GLOBAL_REACQUIRE screen
- lock legality, fire legality, ActionSafety
- retreat logic (none added), survival logic, kill-closure logic
- predictor drives MOVE only; no LLM tactical control

CHANGED (only for an ASSIGNED USV whose target is stale-but-present before first effective engagement):
- movement during the stale window uses a deterministic predictor bank (P0 constant-velocity,
  P1 recent-velocity, P2 turn-aware-if-maneuver-evidence), selected by lowest online EMA error;
- bounded by MAX_REACQUIRE_TIME=900s and uncertainty (t.uncertainty > U_MAX=40km) -> EXPIRED -> parent.
- When every assigned target is FRESH: EXACT no-op vs ACE (unit test 8).
- Non-assigned stale targets: no effect (unit test 9); ownership semantics restored on EXPIRED (test 10).

Note: the frozen parent ALREADY retains stale ownership + approaches the constant-velocity
predicted_position (agent_hybrid_v5.py:2048,2098). C5's delta is the predictor bank + explicit
uncertainty/timeout bound; expected effect is therefore bounded.
