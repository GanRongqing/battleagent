# 04 — C5 MECHANISM CARD

## Mechanism (ONE)
TRACK_AWARE_REACQUISITION: when a USV's assigned target goes stale before its first effective
engagement, retain bounded ownership and drive an INTERCEPT movement from a small deterministic
predictor bank; end on re-observation, uncertainty threshold, or timeout.

## State machine
FRESH_TRACK --(observation stale)--> REACQUIRE --(fresh obs)--> FRESH_TRACK
REACQUIRE --(uncertainty > U_MAX)--> EXPIRED
REACQUIRE --(stale_time > MAX_REACQUIRE_TIME)--> EXPIRED
EXPIRED --> fall back to ACE ownership/assignment semantics (no sticky ownership).

## Predictor bank (deterministic, <=3)
- P0 CONSTANT_VELOCITY: last fresh position + last reliable velocity.
- P1 RECENT_VELOCITY: velocity over last k legal observations.
- P2 TURN_AWARE: only if TrackManager already recorded sustained turn evidence (maneuver_score).
Selection: lowest online EMA prediction error on re-observations; no-history fallback = P0.

## Uncertainty growth
uncertainty_radius = base + growth_rate * stale_time (+ historical error term, bounded).
EXPIRED when uncertainty_radius > U_MAX.

## Timeout
MAX_REACQUIRE_TIME = conservative single value (from track lifetime, no search). Documented below.

## Legality (HARD)
Prediction drives ONLY move/search/intercept heading. LOCK/FIRE/HIT/KILL remain decided by legal
observation + existing ActionSafety. Predicted position is never presented as an observed target.

## Why no infinite tracking
Bounded by MAX_REACQUIRE_TIME AND uncertainty threshold -> EXPIRED -> parent semantics restore.
