# 04 — Root Cause Report (LOCK_ACQUISITION)

Method: 0 new episodes. Recovered per-(USV,target) assignment lock outcomes from W5 baseline agent logs
(`[ASSIGN]`) + reliable baseline game logs (lock commands `white_usvN 锁定 usvN`). ACE shares the same
USVController, so this geometry is representative for ACE too.

## Answers

**1. Of the 84% "approach/intercept" USV occupancy, what is the main failure?**
It is NOT that assignments never lock. Per-**assignment** lock rate = **71.6%** (999/1395). The 84%
was a STEP-LEVEL occupancy artefact: locks are brief, so at any instant most engaged USVs are between
locks. The genuine no-lock failures are 28.4% of assignments.

**2. Why does an assigned USV fail to lock?** Of the 396 no-lock assignments:
- **LA-F1 NEVER_CLOSED_TO_LOCK_RANGE = 280 (70.7%)** — dominant, present in all 6 strategies.
- LA-F6/3 ENTERED_RANGE_BUT_NO_LOCK = 110 (27.8%).
- LA-F5 USV_DIED_BEFORE_GEOM = 6 (1.5%).

**3. Is it "distance always >40km" or "entered range but controller did not lock"?**
Mostly **distance stayed > 40km (LA-F1, 70.7%)**. A smaller part (27.8%) entered < 40km but did not lock
(consistent with `legal.can_lock` being false, i.e. no legal lock action yet in that step).

**4. Is it intercept geometry or standoff policy?**
The dominant LA-F1 ("never closed") is an **approach/closure** failure, not a "held the band too early"
failure. W5 already moves toward the target when `dist >= LOCK_RANGE`; so the closure problem is when
the target is stale/lost (`not is_visible`) — W5 then performs a 34 km **standoff** (converge-to-own-radar)
instead of continuing to close, and the assignment ends without ever reaching 40 km.

**5. Is the 81% no-lock death a primary cause or a downstream consequence?**
Downstream: the USV spends the assignment approaching (no lock), stays exposed, and is killed. The
death is a consequence of the failed closure, not an independent primary cause.

**6. Why C2 = LOCK-FIRST APPROACH?**
Because the dominant actionable family is LA-F1 (never closed). Per the phase mapping (LA-F1/LA-F3 ->
LOCK-FIRST APPROACH): before the first lock, prioritise entering the lock envelope instead of holding the
standoff band. We do NOT touch allocator / sensing / detection / survival.

## Scope / limitations
- Per-target lock TARGET is not in the game log's `usv_states`; lock events were recovered from the
  game-log `actions` (`锁定`) — reliable for the baseline.
- LA-F1 "min_dist" uses the target's `active_enemies` position (only present when detected); a target
  that is rarely detected may over-state LA-F1. This is a KNOWN uncertainty.
