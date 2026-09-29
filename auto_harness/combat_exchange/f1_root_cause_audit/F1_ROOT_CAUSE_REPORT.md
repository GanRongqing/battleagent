# F1 Root-Cause Report — "Detected but not committed"

## Q1. What is KC-F1=84.7% exactly?
Target-episode level (NOT step-level). Numerator = 250 unique (target, episode) that were detected
(`[DETECT]`) but never appeared in the `[ASSIGN]` proxy and never killed; denominator = 295 unique
detected-but-not-killed targets. A target uncommitted for 100 steps contributes 1, not 100.
`committed` uses the step-level `[ASSIGN]` PROXY (not canonical); a target with no `[ASSIGN]` is a
reliable lower bound on "never committed".

## Q2. How many targets were detected but never committed (whole episode)?
250 / 295 detected-but-not-killed = **84.7%** (target-episode level). This is the dominant kill-chain
failure. S5 is worst (assign_rate 42%, kill_rate 20%).

## Q3. When a target is uncommitted, is White free or occupied?
White is mostly **FREE** (34-65% of alive-USV sim-time per strategy). Saturation is essentially zero.
So uncommitted targets are NOT blocked by a lack of White capacity.

## Q4. Of the occupied White, how much is real fight vs no-lock chase?
- locking: 0-3% (S5 ≈ 0%) — White almost never holds a lock.
- assigned-but-not-locking: 7-30%, mostly "assigned to a LOST target" (target not visible), i.e. the
  USV is converging to re-detect a lost track, not holding a stable lock. S5 = 29% lost-target time.
- assigned-no-lock (visible target, no lock): 0-1% (tiny).

## Q5. No-lock chase duration?
The "assigned but not locking" time is dominated by **lost-target re-detect** (not visible-target
chase). True "assigned + visible target + no lock" is negligible (≤1%). The relevant duration is the
lost-track re-detect window (bounded by track drop age, ~180-300s).

## Q6. Does low-quality commitment block new targets?
**No.** F1-C (capacity blocked by no-lock chase) = only 14% (2-40% by strategy). F1-B (saturation) =
0%. The dominant cause is F1-A (free capacity simply not used).

## Q7. Does W5 mostly make 1v1 engagements?
Concurrent-attacker reconstruction: max concurrent attackers per committed target.
Observational kill conversion by max concurrent attackers:
- 1 attacker: 18/64 = 28%
- 2 attackers: 23/65 = 35%
- 3+ attackers: 72/135 = 53%
So W5 does produce 1v1 (and 2v1) engagements, and concentration observably converts better.

## Q8. Do 2v1/3v1 convert better?
**Observationally yes** (28% → 35% → 53%), but NOT causal (more dangerous targets may attract more
attackers — selection bias). This is only observational evidence.

## F1 decomposition (step-level, baseline)

| class | overall share |
|---|---|
| F1-A FREE_CAPACITY_NOT_ASSIGNED | **86%** |
| F1-C CAPACITY_BLOCKED_BY_NOLOCK_CHASE | 14% |
| F1-B CAPACITY_SATURATION | 0% |

F1-A dominates in EVERY strategy (60-98%).

## Root cause

**ALLOCATOR_UNDERCOMMITMENT.**

W5 has FREE combat USVs and VISIBLE Black targets, but the ThreatAllocator does not commit the free
USVs to the visible targets. Why: the frozen default StrategicIntent (LLM off) sets
`focus_level=2` (2 attackers per target) and `reserve_ratio=0.20` (reserve 20% of USVs), and the
allocator commits to only a handful of targets at a time (~7 of 20 USVs engaged; 34-65% stay free).

Consequences:
- ~86% of the time a detected target has no commitment → most Black ships transit unengaged (leak).
- The committed subset gets only 2 attackers/target (1v1/2v1), which observably converts worse than 3+.

## Verdict

dominant cause = **ALLOCATOR_UNDERCOMMITMENT** (F1-A = 86%, present in 6/6 strategies).

The earlier hypothesis ("capacity blocked by no-lock chase") is REFUTED (F1-C = 14%, F1-B = 0%).

## Next-candidate recommendation (do NOT implement now)

Per phase rule 19 (F1-A dominant → not LOCAL_OVERMATCH): the next single-mechanism candidate should
target **commitment expansion** — commit free combat USVs to more visible targets (raise engagement
from ~7 to a larger fraction of the 20 USVs), and raise attacker concentration (focus_level) toward 3
to exploit the observed 28%→53% conversion gradient.

Suggested name (for the NEXT phase, not this one):
**ALLOCATOR_COMMITMENT_EXPANSION** (primary), possibly with a focus_level bump (2→3) as a secondary
flag. Parent = W5.

Note: this is a hypothesis informed by the audit; do not pre-register the exact mechanism until the
next phase's own root-cause gate.

## Constraints respected
- Frozen W5 unchanged. No candidate created. No code change. No re-run (offline logs only).
- `[ASSIGN]` used as a clearly-labeled PROXY (canonical owner mapping is NOT present in frozen W5's
  logs; marked as a limitation, not measured canonically).
