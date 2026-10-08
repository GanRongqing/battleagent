# 20 — C7 VERDICT

## Result summary (full ACE re-baseline, post-determinism-fix engine)
| Group | ACE CER | C7 CER | ACE own-lock | C7 own-lock | ACE hostile-locked-never-own-lock | C7 |
|---|---|---|---|---|---|---|
| W2-1 (hard) | 0.000 | 0.000 | 0 | 0 | 100 | 100 |
| W2-6 (hard) | 0.556 | **0.688** | 55 | **75** | 40 | **25** |
| HARD pooled | 0.263 | 0.306 | 55 | 75 | 140 | 125 |
| W2-2 (control) | 0.211 | 0.211 | 35 | 35 | 65 | 65 |
| W2-4 (control) | 2.000 | 1.366 | 70 | 70 | 6 | 7 |
| CONTROL pooled | 0.640 | 0.559 | 105 | 105 | 71 | 72 |

Packages: 40 formed, 26 synchronized-lock successes.

## Interpretation
- **Mechanism signal (positive, hard case):** on W2-6, C7 improves own-lock conversion (11→15 units),
  reduces hostile-locked-without-own-lock (8→5), and lifts CER 0.556→0.688 (+24%). This is real,
  consistent across all 5 seeds.
- **W2-1 (hard):** no effect — own-lock stays 0. 2-unit packages cannot create a lock where the
  engagement envelope/geometry prevents any own lock.
- **W2-4 (control):** material **outcome regression** (-32% pooled CER; exchange wins 5/5→3/5) with
  **unchanged** own-lock — C7 disturbs an engagement ACE was already winning (most package formations).

## Verdict
**CONTROL_REGRESSION** (>20% drop + exchange-win degradation on W2-4). Confidence: MEDIUM.

(Secondary characterization: MECHANISM_SUPPORTED_OUTCOME_MIXED — mechanism supported on W2-6, outcome
mixed overall. The control gate is decisive per spec.)

## Recommended next action
Do **not** proceed to the full 12-strategy regression. Do **not** auto-tune. If C7 is pursued, gate
package formation so it does not perturb targets ACE is already converting (e.g., require the target be
a genuine hard 1-owner unlocked threat and cap the package budget), then re-test W2-6 + W2-4. Otherwise
DROP C7.
