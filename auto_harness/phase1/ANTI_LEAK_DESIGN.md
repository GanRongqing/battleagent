# ANTI-LEAK CONTAINMENT DESIGN — white-auto-0001-v1

Baseline: W5 (agent_hybrid_v5.py) FROZEN. Candidate: agent_hybrid_w8_containment.py.
Only the allocator (WHO is assigned) is overlaid; execution HOW is untouched.

## Evidence (Phase 0, S2 x B3, N=100)
- 35/35 non-clean episodes have exactly one breakthrough; 26 F-LEAK (all enemies
  eventually killed) + 9 F-ATTRITION (survivors/loss).
- Detection / first-lock / first-kill are NOT discriminative; lost-track/reacquire
  raw counts are a duration artifact (miner v2: per-1000-step rates LOWER in failures).
- Failure signature = single leak + long resolution tail + forward-containment gap.

## Mechanisms
M1 crossing-risk estimator: legal track belief (predicted position + last velocity)
   -> crossing ETA to BREAK_X (50000). vx >= -0.05 => UNKNOWN. Levels:
   CRITICAL <=3000s, HIGH <=6000s, MEDIUM <=10000s.
M2 boundary coverage checker: effective blocker = an assigned USV that is boundary-side
   of the target (x <= target.x + 5km) OR intercept-feasible (dist/15 m/s <= ETA).
M3 minimal containment assignment: only when risk>=HIGH and no effective blocker.
   Assign exactly ONE blocker: free USV first, else bounded preemption from a target
   with >=2 assigned. TTL 900 sim-s hysteresis; release on expiry / kill / no position.

## Explicitly NOT in v1
global front re-layout, pursuit-depth cap, UAV doctrine, kill-chain overlay, sensor
screen, controller/BT rewrite, LLM change. (Attribution.)

## Fair play
Uses only legal White track beliefs; no hidden Black truth, no seed/version cheat.

## Expected / weakness
Expected: fewer single breakthroughs without worsening loss/resolution.
Weakness: reserve may thin the frontline; predictor may false-positive on maneuvering
targets; wrong preemption can delay engagement; low benefit vs non-breakthrough opponents.
