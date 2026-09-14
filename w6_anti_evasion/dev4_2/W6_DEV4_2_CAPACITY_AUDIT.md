# W6-dev4.2 Capacity Audit (READ-ONLY)

Reused semantics found in the current code (legal-only), to build reinforcement_need /
deadline / coverage safety WITHOUT inventing thresholds where a semantic exists.

1. Risk / deadline: `BreakthroughRiskEstimator.estimate` (anti_evasion/breakthrough_risk.py)
   gives, per tracked ship with finite `breakthrough_eta` (time until x<=BREAK_X):
   `breakthrough_eta`, `best_interceptor_eta`, `interceptor_deficit = b_eta - i_eta*(1+safety)`,
   `risk_score`. "In time" (feasible before the line) is already encoded as
   `deficit >= 0`, i.e. `i_eta*(1+SCREEN_ETA_SAFETY) <= b_eta`. Reuse this as the deadline
   feasibility test (no new seconds).
2. Engagement capacity: the frozen W5 allocator saturates per-target attackers at
   `intent.emergency_focus_level` (default 3) — the scale-agnostic "max attackers per threat"
   semantic (`ThreatAllocator`, `:1813` `emg`). dev4.1's cap=3 is this same value. Reused,
   documented as a temporary safety guard (matching W5's own saturation ceiling), not tuned.
3. "Enough for the threat": a corridor that already has >=1 committed interceptor whose
   plan ETA meets the deadline (deficit>=0) is HIGH-sufficient (required=1); a CRITICAL
   corridor requests a backup (required=2). required is derived from risk tier, not fleet size.
4. Coverage safety: no per-platform "coverage contribution" API exists beyond `CoverageMap`
   (grid, sensing-derived) and the legal `uncovered` corridor set (high-risk with deficit<0 or
   infeasible plan). Reuse: moving FREE P to C is COVERAGE_UNSAFE if some other HIGH/CRITICAL
   corridor C2 would be left with zero candidate interceptor able to meet its deadline after P
   leaves (P was its only in-time candidate).
5. Lock/frozen: active lock or frozen engagement already counts as effective in-time capacity
   (the attacker is engaged) and marks HARD (protected).

Components reused: `breakthrough_eta`/`deficit` (deadline), `intent.emergency_focus_level`
(capacity ceiling), W6 `planner` ETAs, `CoverageMap`-independent uncovered logic.
NOT reused (avoided): relative-ETA ratio gates (dev4.1 failure), fixed sim-seconds deadlines,
fleet-size counts.
