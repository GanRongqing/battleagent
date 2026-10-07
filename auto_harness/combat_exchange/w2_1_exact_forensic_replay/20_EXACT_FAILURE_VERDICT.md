# Exact W2-1 Failure Verdict

## Verdict
**LOCK_CONVERSION_FAILURE / ENGAGEMENT_RANGE_FAILURE (MIXED, earliest = lock conversion)**

## Confidence
MEDIUM

## First Hostile Damage
- time = T_EP ≈ 26,850 s (first `is_locked` with attacker id, e.g. white_usv10 ← usv15,usv17)
- attacker = concrete Black ids present in `locked_attacker` (usv10–usv18) — **known to the victim**
- attacker legally observable / lockable = NOT_MEASURED (engine envelope not traced)
- attacker actually observed = the victim was itself locked by them (threat known), but own-lock absent

## First White Death
- time = T_EP ≈ 27,150 s (white_usv10)
- killer = a Black usv that had locked the victim (ids recorded); victim own-lock = NO

## Observation / Engagement
- W2-1: **20/20 deaths preceded by Black lock; only 7/20 White units ever form an own lock; own locks
  begin ~2,070 s AFTER the first death.**
- W2-2: 15/15 deaths preceded by Black lock; **13/15 units form own locks**, first own lock only ~750 s
  after first death.

## Black-lock-before-White-observe
- W2-1: the White is locked by Black while it holds no own lock (all 20 deaths) — the enemy
  engagement envelope clearly covers the White while the White does not convert to its own envelope.

## Earliest Actionable Divergence
**ENGAGEMENT/LOCK CONVERSION**: the White is inside the Black engagement envelope (locked) but fails to
convert contact/knowledge into its own active lock — 7/20 (W2-1) vs 13/15 (W2-2). The White loses the
local fire exchange.

## Why C5 Failed
C5 only actuated stale-window ownership + predictor movement; the failure is not reached via stale-track
reacquisition — the White is already being locked (in enemy range) and dies before any lock, so
predictive reapproach adds no leverage.

## Why C6B Failed
C6B's own-geometry cohesion gate never armed (0 triggers): the White is cohesive and locked, not an
isolated overextended spearhead — so the pre-lock admission feature set did not match the failure.

## One Next Mechanism (concept only — DO NOT IMPLEMENT)
**LOCAL OVERMATCH / SYNCHRONIZED FIRE / KILL-CLOSURE**: get White units into their own lock/fire envelope
concurrently and survive the local exchange, rather than being locked-and-killed while unable to lock.
