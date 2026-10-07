# 21 — Final Report: Exact W2-1 vs W2-2 Forensic Replay

Source = EXISTING game logs (0 new replay): W2-1 = game_5 (横向编队-中央汇聚箭头突防, 993 steps, Defeat),
W2-2 = game_9 (菱形编队-接近后扇形展开突防, 509 steps, Victory). ACE unchanged; truth (per-unit lock/
death) used OFFLINE only; no new instrumentation added (game logs already contain per-unit is_locked /
locked_attacker / is_alive, so no invariance risk).

1. Exact chain difference (the only valid basis):
   TRUE→OBSERVED→FRESH→LEGALLY_LOCKABLE→ACTIVE_LOCK→FIRE→HIT
   W2-1 fails at **ACTIVE_LOCK conversion**: only **7/20** units ever lock (vs **13/15** for W2-2), and
   W2-1's own locks start ~2,070 s AFTER its first death.
2. Both cases: every White death was preceded by a Black lock (attacker id present) → **not** an
   unobserved-attacker problem; the White knows it is being attacked.
3. W2-1 first hostile damage T_EP ≈ 26,850 s; first death T_EP ≈ 27,150 s (≈300 s later).
4. W2-1 vs W2-2 key difference = **whether the White converts contact into an own lock and wins the
   local exchange**, not whether it detects the enemy.
5. Earliest actionable divergence = ENGAGEMENT/LOCK conversion (White inside enemy envelope, failing to
   establish its own).
6. Sensor/weapon envelope asymmetry = NOT_MEASURED (engine ranges not traced; no guessed thresholds).
7. C5 failed (no leverage: failure not in stale-track reacquisition). C6B failed (NO_TRIGGER: units are
   cohesive, not isolated).

## Next mechanism concept (DO NOT IMPLEMENT)
LOCAL_OVERMATCH / SYNCHRONIZED_FIRE / KILL_CLOSURE.
confidence = MEDIUM.
