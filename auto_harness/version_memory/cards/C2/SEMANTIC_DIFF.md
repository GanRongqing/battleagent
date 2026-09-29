# Semantic Diff — ACE -> C2 (white-combat-0003-v1)

## What changed
- **Before (ACE/W5)**: for an assigned target the USV did not hold a lock on, if the target was not
  visible (stale) the controller performed a 34 km standoff (converge to own radar), and if it was within
  LOCK_RANGE but not lockable it held the standoff band — i.e. it could stall while pre-lock.
- **After (C2)**: before the FIRST lock of the current target, the USV **always closes** toward the
  target's predicted position; the standoff band is only used AFTER the first lock (post-lock path
  unchanged).

## Why changed
Initial hypothesis for LA-F1 (assigned but never reached lock range): pre-lock standoff prevented
sufficient closing.

## Trigger condition
USV has an assigned target it has not yet locked, with a known predicted position.

## What was intentionally NOT changed
- allocator/ACE reserve release, TrackManager, detection, radar, lock range, weapon, Black, scenario
- post-lock behaviour

## Expected mechanism
Faster closure -> higher Assigned->First-Lock conversion.

## Observed outcome (why this card is INCONCLUSIVE)
Lock rate rose (S1 +31% rel, S6 +39% rel) BUT median TTFL became slower (S1 +19%, S6 +8%) and combat was
mixed (S1 worse, S6 better). => "never reached lock range" does not imply "close more aggressively".

## Interface changed?
NO. (`interface_changes: []`)
