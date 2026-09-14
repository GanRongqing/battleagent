# W6-dev3 First-Divergence Trace

## Primary suspect

**None.** Per the isolation report, on S2 × B3 × seeds 4001–4003 the W6 allocator overlay
produced only 0–2 assignment changes per game across all cumulative variants (B–F). When a
component does not change the assignment, there is no first assignment divergence to trace
between consecutive variants — the "divergence" observed in outcomes (e.g. A V/4 vs B D/10 on
s4001, or A V/6 vs B V/2 on s4002) occurs despite *identical assignment behaviour* and is
therefore run-level trajectory noise, not a mechanism decision difference.

## Evidence of absence of divergence

Assignment change counters (from the per-game W6 metrics dump, summed over each variant):

| variant | assignment_change_count total (3 games) | mean lifetime s |
|---|---:|---:|
| B_Prediction | 0 | – |
| C_PlusRisk | 0 | – |
| D_PlusPursuit | 1 | 20,862 |
| E_PlusHandoff | 2 | 9,046 |
| F_PlusReserve | 1 | 12,898 |

For comparison, the mechanism *bookkeeping* counters (handoff_count, reinforcement events,
reserve events) are non-zero, but those did not translate into actual platform–target
reassignments on these seeds — the only assignment-level changes are the handful above, and
even those are too sparse and late (lifetimes of tens of thousands of sim-seconds) to explain
the per-seed outcome differences.

## Consequence

No "first causal divergence" with a score-component cause can be reported because no such
divergence occurred at the allocator layer on the studied seeds. Any valid first-divergence
analysis requires a run in which the component actually changes the assignment.

## Recommended instrumentation (future)

Add a per-step allocator logger that records, when a component gate is toggled and the
assignment actually changes: `sim_time`, `platform_id`, `prev_target`, `new_target`,
per-candidate score components (base marginal / prediction / risk / pursuit / coverage /
reserve), and the downstream controller action + death/kill deltas in the ±20-step window.
