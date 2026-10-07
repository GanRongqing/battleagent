# 04 — C6B MECHANISM CARD

## Problem
White units enter poor engagement geometry (forward, low support, long no-own-lock) before obtaining a
useful own engagement, die before their own lock, and the surviving sensing force collapses.

## Mechanism
Bounded **pre-lock commitment admission** using observable own/support geometry only:
- ADMISSION_STATE per combat USV ∈ {SAFE_TO_COMMIT, SHAPE_AND_WAIT, ENGAGED}.
- ENGAGED (own active lock) -> exact ACE behaviour.
- SHAPE_AND_WAIT when pre-lock AND overextended beyond local friendly support AND no own lock; action =
  lateral shaping (hold/offset) to let support close; bounded by MAX_SHAPE_WAIT.
- Otherwise SAFE_TO_COMMIT -> exact ACE behaviour (no-op).

## Does NOT do
retreat-after-lock, search changes, allocator changes, focus fire, truth access, route/strategy-ID logic.

## Expected causal effect
less isolated exposure -> fewer deaths before own lock -> larger surviving force -> preserved sensing /
engagement capacity -> better exchange.

## Bounds
hysteresis (entry/exit) + MAX_SHAPE_WAIT prevent oscillation and permanent passivity.
