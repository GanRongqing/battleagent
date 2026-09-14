# W6-dev4 Decision Examples

## Offline (counterfactual, representative reasons on 2035 states)
- BREAKTHROUGH_URGENT: a soft/free platform whose min-ETA target is an imminent/uncovered
  corridor (dest in deficit<0 / infeasible) → assignment would move there.
- BETTER_INTERCEPTOR: platform ETA to dest is >=25% shorter than dest's current lead
  (or, if free, than the lead of an imminent target).
- No UNKNOWN reasons produced (decision logic emits only these enums).

## Live (S2×B3×4001–4003)
dev4 fired soft release (0–1/game) and free realloc (0–2/game), e.g. s4002 produced
soft_release=1 + realloc=1 with a clean win. Hard-commit violations 0; execution override 0.

## Caveat
Live triggering is still sparse vs the offline potential (17.8–37.4%); the live trigger
path is conservative (imminent/uncovered + ≥25% lead gain + step cadence). This is the
decision-quality item to audit next (eligibility/release timing), not a reason to re-tune
weights.
