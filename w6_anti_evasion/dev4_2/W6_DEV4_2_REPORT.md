# W6-dev4.2 Coverage-Safe Imminent Reinforcement

## 1. Motivation
dev4.1's relative-ETA gate (<=1.5x lead) fired 0/2035 offline: FREE platforms are far from
near-breakline imminent corridors whose owners already hold short ETAs. dev4.2 replaces the
ratio gate with the questions that matter: does the corridor lack capacity, can the FREE
platform arrive by a legal deadline, is moving it coverage-safe.

## 2. Rule (single change, FREE only)
FREE P -> imminent HIGH corridor C iff: risk>=HIGH; effective in-time capacity < required
(1 HIGH / 2 CRITICAL, derived from breakthrough-risk + committed interceptor ETAs);
ETA(P,C)*(1+SCREEN_ETA_SAFETY) <= breakthrough_eta(C) (deadline feasibility); coverage-safe
(no other need corridor loses its only in-time candidate); below emergency concentration
(per-target ceiling == W5 emergency_focus default, temporary guard).

## 3. Frozen
SOFT/HARD/reserve/handoff/weights/controller/HOW unchanged; execution override 0; ETA ratio
gate removed.

## 4-5. Offline funnel (2035 states)
imminent 895, HIGH 887, deficit 886 — but **deadline_ok = 0/2035** and fired = 0.
Root cause: FREE platforms are geometrically far from corridors already near the break line,
so their ETA never satisfies the breakthrough-horizon deadline. The gate that removes the
opportunity is DEADLINE (breakthrough horizon), exactly the semantic the audit flagged.

## 6. Historical events
All 7 dev4 events (5 GOOD, 2 BAD) are deadline-infeasible under dev4.2 and are REJECTED
(explained in DEV4_2_HISTORICAL_EVENT_AUDIT.md): they were post-deadline extra-attacker /
endgame swarm additions — harmless but tactically weak; dev4.2 intentionally does not
replicate them. GOOD is not captured; BAD is not amplified.

## 7. Safety / invariants
T47-T58 13/13; regressions green; coverage/concentration/hard invariants structurally safe;
same-state deterministic (pure predicates).

## 8. Live sanity
NOT RUN — offline acceptance (fired>0) not met (0/2035).

## 9. Decision
STOP — as specified, deadline-feasible FREE reinforcement does not exist in these states.
The finding is causal and clean: neither ETA-ratio nor breakthrough-horizon deadline is the
right eligibility axis for FREE->imminent reinforcement, because FREE platforms are always
too far to matter before the line. Recommended next step (NOT this round): either derive a
reinforcement deadline from the *engagement/second-hit* horizon of the committed interceptor
(not the break line), or accept that FREE-imminent reinforcement is only an endgame swarm of
low tactical value and pivot allocator effort to SOFT rebalancing (which the commitment
pools already gate) rather than FREE reinforcements.
