# Same-Policy Repeatability Audit (W5)

## Config
White W5 (frozen), S2 10+10 vs 20, B3_ADAPTIVE, seeds 4001 & 4002 × 3 repeats each = 6
episodes. Identical config every run (same agent/skill/prompt/B3/scenario/seed/LLM=off/
controller/physics). Data: `repeatability_runs.csv`.

## Results (same seed, identical config)

| seed | rep | result | victory_time | dead | breakthrough |
|---|---|---|---:|---:|---:|
| 4001 | 1 | Victory (clean) | 27,090 | 3 | 0 |
| 4001 | 2 | Victory (clean) | 15,835 | 4 | 0 |
| 4001 | 3 | Victory (clean) | 21,550 | 4 | 0 |
| 4002 | 1 | Victory (clean) | 23,883 | 3 | 0 |
| 4002 | 2 | Victory (clean) | 36,397 | 7 | 1 |
| 4002 | 3 | **Defeat** | 37,913 | 5 | 1 |

## Classification
- Same-seed outcome variance is LARGE: seed 4002 flips Victory(clean) ↔ Defeat across repeats;
  victory_time spread is ~11–15k sim-seconds within one seed.
- First (coarse-log) divergence between repeats: at trace indices ≈29–31 (traces of length
  49–86 logged steps), i.e. mid-game, not at the first decisions.
- The allocator is deterministic on the same legal state (see replay report: 100 states ×10
  → 0 mismatch; hidden-truth PASS). Therefore this is **R1/R3 — sim trajectory/timing chaos,
  NOT R2 policy nondeterminism**.

## Nondeterminism source audit (read-only)
- Python/numpy RNG is reseeded per game in `scenario_builder.build_scenario`
  (`random.seed(rw_seed+1009)`, `np.random.seed(rw_seed+7)`).
- The engine still runs 100× real-time with an apply/release-window macro cadence
  (`MACRO_STEP`, pomdp_api) — decision/apply wall timing varies between runs and can shift
  engine-internal draw counts before combat states diverge.
- Suspected residual variance: engine-internal RNG draw sequence depending on execution
  timing within a macro step (continuous advancement), not covered by the scenario seed.
  Evidence is the deterministic-allocator yet divergent-live-trajectory result above.
- No allocator-side ordering/dict nondeterminism found (same-state replay deterministic).

## Answers
- same-seed outcome variance = LARGE (outcome flip + 11–15k s resolution spread at N=3)
- same-seed assignment divergence (live, coarse trace) = mid-game (~index 29–31)
- allocator deterministic given same state = YES
- live runtime repeatable = NO

## Consequence
Single small-N live outcomes are NOT a stable signal for allocator-component debugging; use
same-state replay for allocator questions and larger paired samples for outcome questions.
