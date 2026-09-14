# W6-dev4 Offline Counterfactual — Decision Expressivity

On the 2035 saved allocator states, granting the W6 allocator a **releasable platform pool**
(availability scenarios) was tested offline (no simulator). Reference: dev3's actual
assignment change was 0/2035.

| scenario | mean free pool | mean soft | mean hard | change states | change rate |
|---|---:|---:|---:|---:|---:|
| A ORIGINAL (free only) | 2.31 | 4.96 | 0.77 | 62 | 3.1% |
| B ONE_FREE (+1 released soft) | 2.31 | 4.96 | 0.77 | 362 | **17.8%** |
| C SOFT_RELEASE (all eligible soft) | 2.31 | 4.96 | 0.77 | 761 | **37.4%** |
| D ELASTIC_POOL | 2.31 | 4.96 | 0.77 | 761 | 37.4% |

Interpretation
- The free pool is NOT actually empty (mean ~2.3 per state); the binding constraint is that
  W6's decision mechanisms were gated so they only fired when a corridor was "uncovered" and a
  better lead existed — which almost never happened (dev3 actual = 0).
- The moment the availability model lets ONE soft platform be pulled, features become
  expressive: changeable states jump 3.1% → 17.8%; releasing all soft reaches 37.4%.
- Reasons produced are explainable: BREAKTHROUGH_URGENT / BETTER_INTERCEPTOR (ETA ≥25% better
  than the current lead). No unknown reason.

Conclusion: decision expressivity IS (a) bottleneck; candidate-pool expansion turns W6
features into non-zero, explainable assignment changes ⇒ proceed to dev4 implementation
(commitment classifier + releasable pool + elastic reserve), per the round's rule.
