# B0 27-Class Stratification Method (b0-27class-v1)

## Concept levels (must not be conflated)
- Policy: B0_RANDOM (immutable policy_id black-b0-v1).
- Empirical behavior class: E0 (Random / Uncoordinated).
- Within-policy log strata: 27 possible length x width x speed buckets (this document).
The 27 buckets are NOT strategies and are NOT registered as opponents.

## Classification unit
One valid B0 episode -> three scalars (formation_length, formation_width, formation_speed)
-> exactly one of 27 classes.

## Definitions (generic, documented)
- Only alive Black combat USVs (BLUE Ship); Black UAV excluded.
- Snapshot length/width: fleet centroid -> PCA (2x2 eigen) -> robust span along the major
  and minor principal axes: P90 - P10 of the projected coordinates (not max-min, to resist
  single-ship outliers).
- Snapshot speed: per-unit displacement / dt between consecutive trace samples; episode
  value = median over all per-unit samples (UAV excluded).
- Episode aggregation: median over snapshots with >= 4 visible combat units. Snapshot
  counts and speed sample counts are recorded per episode.

## Long-tail audit
The traces are pre-contact and in-contact; a whole-episode median is compared with a
first-20-snapshot window median (b0_stratify.run tail_audit). Differences were small
(length/width medians stable); the frozen result uses the whole-episode median (simple,
uniform across all episodes). No per-episode manual windowing.

## Thresholds (frozen)
Empirical 33.33/66.67 percentiles over the 28 valid unique episodes (linear interpolation).
See B0_27CLASS_THRESHOLDS.json (dataset_hash a235a4ee9a15a950).
Rule (identical for all three axes): LOW x<=Q1; MID Q1<x<=Q2; HIGH x>Q2.

## Degeneracy finding (honest)
formation_speed is effectively constant: B0 commands all Black USVs at 10 m/s, so
speed q33 = q67 = 10.0 and every valid episode is speed LOW (MID=HIGH=0). The speed axis
therefore carries no B0 variance; the effective stratification is length x width = 9 strata
(27 rows are still emitted, 18 zero). Tie counts are reported. This is a real property of
the B0 policy, not a pipeline error.

## Percentile slicing check
Length marginals 10/9/9, width marginals 10/9/9 (boundary ties); speed 28/0/0.

## Files
B0_LOG_SOURCE_AUDIT.md, B0_27CLASS_METHOD.md, B0_27CLASS_THRESHOLDS.json,
B0_LOG_27CLASS_ASSIGNMENTS.csv, B0_27CLASS_COUNTS.csv, B0_27CLASS_REPORT.md.
