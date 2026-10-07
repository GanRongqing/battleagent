# 05 — C7 MECHANISM CARD

## Problem
White knows / is engaged by Black (all victims are hostile-locked), but too few White units convert
into **active own-lock** state (W2-1: 35% vs W2-2: 87%).

## Mechanism (ONE)
Bounded 2-unit (max 3) engagement packages that **synchronize pre-lock approach timing** (minimize
predicted TTFL spread) around a reachable known/assigned threat, so members reach own-lock geometry
near-simultaneously.

## Primary causal target
ASSIGNED / KNOWN THREAT → ACTIVE OWN LOCK.

## Not directly targeting
sensing, stale-track retention, global allocator coverage, retreat, hit→kill.

## Bounds
package size 2 (max 3); coverage-floor invariant preserved; MAX_FORM_TIME / MAX_SYNC_TIME then DISSOLVE
-> ACE fallback; LEAD slowed/shaped if ahead (never retreat-to-base, never indefinite stop).

## Does NOT
use truth / route / strategy ID; blanket speed-up; mass all units; touch lock/fire legality.
