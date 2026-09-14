# W6-dev3 Allocator Component Isolation — Report

Config: S2 (10+10 vs 20) × B3_ADAPTIVE × DEV seeds 4001–4003, execution = LEGACY W5
controller, UAV behaviour pinned to W5 default (track-maint OFF) across all variants.
Cumulative gates via env `W6_ISO`. Variant A reused from the dev3 diagnostic (pure W5,
exact config); B–F freshly run. New episodes = 15 (budget ≤ 18).

## Main table (N=3 per variant)

| Variant | iso | clean | mean loss | brk | explored km² | res s | assign changes/game | handoff_count (contaminated)* |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| A W5 | none | 2/3 | 4.0 | 1 | 92,983 | 22,852 | – | – |
| B +Prediction | prediction | 1/3 | 6.7 | 2 | 87,958 | 25,874 | 0 | 35 |
| C +Risk | +risk | 0/3 | 9.0 | 1 | 79,067 | 26,401 | 0 | 21 |
| D +PursuitCost | +pursuit | 0/3 | 8.7 | 3 | 83,925 | 26,376 | 1 | 33 |
| E +Handoff | +handoff | 0/3 | 9.0 | 1 | 84,533 | 28,037 | 2 | 53 |
| F +Reserve | +reserve | 0/3 | 10.0 | 0 | 80,325 | 28,769 | 1 | 36 |

*`handoff_count` was contaminated (see BUG_FIX_LOG) by the ignored dev2 allocation that used
to run inside `w6.step()`; the assignment-relevant metric is `assignment_change_count`.

## Marginal effects (outcome, noisy)

| Added component | Δclean | Δloss (mean) | Δbreakthrough |
|---|---:|---:|---:|
| Prediction (B−A) | −1 | +2.7 | +1 |
| Risk (C−B) | −1 | +2.3 | −1 |
| PursuitCost (D−C) | 0 | −0.3 | +2 |
| Handoff (E−D) | 0 | +0.3 | −2 |
| Reserve (F−E) | 0 | +1.0 | −1 |

## Per-seed (result / friendly dead)

| seed | A W5 | B | C | D | E | F |
|---|---|---|---|---|---|---|
| 4001 | V/4 | D/10 | D/7 | D/10 | D/10 | D/10 |
| 4002 | V/6 | V/2 | D/10 | D/6 | D/10 | D/10 |
| 4003 | V/2 | D/8 | D/10 | D/10 | D/7 | D/10 |

## Findings

1. **The allocator overlay barely fired.** Assignment-level changes (platform target changed)
   were 0–2 per game across B–F. On these S2 seeds the W6 allocator is effectively a
   passthrough of the frozen W5 allocation, so the cumulative components mostly did NOT
   express themselves in assignment.
2. **Outcome deltas are dominated by run-level nondeterminism.** A (pure W5) and B
   (prediction-only, allocation passthrough ≈ the same policy) differ by up to 10 dead on a
   seed, and the per-seed direction is inconsistent (s4002 B is better than A; s4001 B is far
   worse). This matches the earlier determinism probe (`RNG_NONDETERMINISM.md`): the same
   config can draw clean-vs-collapse.
3. Therefore **no single negative component can be claimed**: the marginal effects in the
   table are not attributable at N=3 because (a) the components barely changed assignments and
   (b) outcome noise is comparable to or larger than any component effect.

## Decision

- Single negative component: **NO** (cannot be established at this activation level / N).
- Multiple negative components: **NO**.
- Interaction effect: **NOT PROVEN** — the observed pattern is dominated by trajectory noise
  with near-zero mechanism activation on the studied seeds.

Next step (recommended, NOT run this round): verify at the *assignment-behaviour* level with a
step-wise assignment logger (record per-step allocator decisions + first-divergence time) on a
wider set of seeds, or use controlled paired resampling for outcome claims. Do NOT freeze any
W6 variant from this isolation.
