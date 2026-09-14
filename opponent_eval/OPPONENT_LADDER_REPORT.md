# Opponent Ladder Smoke Report

White 5+5 vs Black 10 combat USV (pure combat, no Black UAV), N=3 per profile.

## Profiles

- **B0_RANDOM**: existing random-waypoint baseline (unchanged).
- **B1_MULTI_AXIS**: Black USVs split into dynamic spatial groups (normalized capacity, count-agnostic) approaching the breakthrough line from several lateral lanes with perturbation. _From_ a single clustered corridor _to_ multi-lateral pressure.
- **B2_COORDINATED_PRESSURE**: adds group-level coordination on top of B1: ships within a group share a synchronized x-schedule; groups are staggered in arrival; fixed lanes mean surviving ships keep their mission if a group is lost.
- **B3_ADAPTIVE**: adds a legal runtime controller: Black re-plans headings / lane offsets from its OWN radar intel (`get_black_targets()`), e.g. shifts a group laterally away from a detected White presence. It never reads White hidden state.

## Fair play (see test_opponent_profiles.py)

- hidden-White-truth counterfactual: identical legal observation ⇒ identical Black action
- White-internal-state mask: Black policy has zero references to White belief/tracks/allocation/intent/doctrine; only get_black_targets()
- variable-cardinality: 3/10/20/30/50 all generate + plan without crash

## Smoke results

| profile | seed | result | clean | usv_dead | enemy_kills | groups | peak_sim | explored_km2 | sim_time |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| B0_RANDOM | 1001 | Result.Victory | 1 | 0 | 10 | 2.8 | 10 | 47325.0 | 10399.0 |
| B0_RANDOM | 1002 | Result.Victory | 1 | 1 | 10 | 3.0 | 10 | 56675.0 | 11121.0 |
| B0_RANDOM | 1003 | Result.Victory | 1 | 2 | 10 | 2.7 | 10 | 53550.0 | 12024.0 |
| B1_MULTI_AXIS | 1001 | Result.Victory | 1 | 2 | 10 | 2.6 | 10 | 49750.0 | 11153.0 |
| B1_MULTI_AXIS | 1002 | Result.Victory | 1 | 1 | 10 | 2.9 | 10 | 53125.0 | 11672.0 |
| B1_MULTI_AXIS | 1003 | Result.Victory | 1 | 2 | 10 | 2.9 | 10 | 48275.0 | 10768.0 |
| B2_COORDINATED_PRESSURE | 1001 | Result.Victory | 1 | 0 | 10 | 2.9 | 10 | 51800.0 | 10361.0 |
| B2_COORDINATED_PRESSURE | 1002 | Result.Victory | 1 | 1 | 10 | 3.0 | 10 | 50225.0 | 10749.0 |
| B2_COORDINATED_PRESSURE | 1003 | Result.Victory | 1 | 2 | 10 | 2.7 | 10 | 69325.0 | 15916.0 |
| B3_ADAPTIVE | 1001 | Result.Victory | 1 | 2 | 10 | 2.8 | 10 | 46975.0 | 11234.0 |
| B3_ADAPTIVE | 1002 | Result.Victory | 1 | 0 | 10 | 2.9 | 10 | 59750.0 | 10975.0 |
| B3_ADAPTIVE | 1003 | Result.Victory | 1 | 2 | 10 | 2.9 | 10 | 50800.0 | 12303.0 |

## Profile summary (mean over seeds)

| profile | clean_rate | usv_dead | enemy_kills | groups | peak_sim | lane_entropy | first_contact | first_kill | explored_km2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| B0_RANDOM | 3/3 | 1.00 | 10.00 | 2.83 | 10.00 | 0.14 | 2111.33 | 8213.67 | 52516.67 |
| B1_MULTI_AXIS | 3/3 | 1.67 | 10.00 | 2.80 | 10.00 | 0.09 | 2126.67 | 8308.67 | 50383.33 |
| B2_COORDINATED_PRESSURE | 3/3 | 1.00 | 10.00 | 2.87 | 10.00 | 0.09 | 2110.33 | 8218.33 | 57116.67 |
| B3_ADAPTIVE | 3/3 | 1.33 | 10.00 | 2.87 | 10.00 | 0.07 | 2123.33 | 8221.67 | 52508.33 |

## Policy-level geometry (waypoint generation, seed=1001, Black=10)

Black-approach geometry differs by profile (from generated initial waypoints):

| profile | final-y span (m) | mid-waypoint y span (m) | structure |
|---|---:|---:|---|
| B0_RANDOM | ~111,500 | ~109,900 | independent random corridors, narrow-ish scatter |
| B1_MULTI_AXIS | ~411,500 | ~360,000 | spatial groups fan out across the full lateral corridor |
| B2_COORDINATED | ~420,000 | ~380,000 | structured lanes; ships in a group share a lane (synchronized) |

## Honest reading of the smoke

- At 5+5 vs 10 (pure combat) **White still wins all 12 cleanly (10/10 kills)**: the ladder is implemented, but this small scale is not where it flips White's outcome.
- The ladder's *tactical pressure* is visible at the policy level (geometry spread) and modestly in in-game metrics (B1 shows the highest mean USV loss 1.67; sim_time / explored vary by profile). N=3 is not statistically meaningful.
- No simulator / policy bug: all episodes completed, all fair-play audits PASS.

> Purpose: confirm the ladder produces *different tactical pressure* and no policy/simulator bug — not statistical significance (N=3).

---

## ⚠ Correction (post-smoke audit)

A bug was found after the smoke: `import opponent_profiles` inside `build_scenario` failed
in the sim-server process (project root not on its sys.path), so the opponent profile was
NEVER passed to the sim — **all smoke games silently ran B0_RANDOM**. Consequences:

- The smoke's per-profile in-game results (B1/B2/B3 "clean 3/3") were actually B0 with
  different seeds, NOT the named profiles.
- The **policy-level** differences in this report (waypoint geometry y-spread: B0 ~111 km,
  B1 ~412 km, B2 ~420 km) were computed by calling the pure path functions directly and
  REMAIN VALID.
- Fair-play unit tests (test_opponent_profiles.py) validate B1/B2/B3 path generation +
  B3 plan at the function level and PASS — but they did not exercise the sim integration.

Fix applied: `scenario_builder.py` now adds the project root to sys.path before importing
`opponent_profiles`, and `scenario_composition.py` (the actual script sent to the sim server)
now reads the profile from the config file. After the fix, a live B3 game confirms the
adaptive controller fires (calls=1292, replan_count=282, lane_shift_count=113,
dispersion_event_count=92) — see the formal B0-vs-B3 evaluation (opponent_formal_eval/).
