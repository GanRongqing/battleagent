# FP-V2 Distance Calibration (S2, 7001-7010)

## Within-policy vs between-policy variability

| policy | n | within_feature_median_std (behavioral) |
|---|---|---|
| B0 | 10 | 4.04 (median of feature stds) |
| B1 | 10 | 6.649 (median of feature stds) |
| B2 | 10 | 8.701 (median of feature stds) |
| B3 | 10 | 24.192 (median of feature stds) |

## Pairwise behavior distances & effect sizes

- B0 vs B1: behavioral distance=1.2690, top effect spatial.mean_group_spacing_km d=8.9880, seed consistency=1.0 -> EMPIRICALLY_DISTINCT
- B0 vs B2: behavioral distance=1.1760, top effect spatial.mean_group_spacing_km d=9.8210, seed consistency=1.0 -> EMPIRICALLY_DISTINCT
- B0 vs B3: behavioral distance=1.3350, top effect adaptation.dispersion_event_count d=11.1810, seed consistency=1.0 -> EMPIRICALLY_DISTINCT
- B1 vs B2: behavioral distance=0.3710, top effect spatial.mean_group_spacing_km d=1.1470, seed consistency=0.7 -> INCONCLUSIVE
- B1 vs B3: behavioral distance=1.1000, top effect adaptation.dispersion_event_count d=11.1810, seed consistency=1.0 -> EMPIRICALLY_DISTINCT
- B2 vs B3: behavioral distance=1.1110, top effect adaptation.dispersion_event_count d=11.1810, seed consistency=1.0 -> EMPIRICALLY_DISTINCT

## Suggested novelty threshold (empirical calibration, not theory)

- Behavioral distance is a summary only. Verdicts combine distance + feature-level Cohen's d + 10-seed direction consistency.
- No fixed threshold is applied automatically; if behavior distance of a new candidate to every pool member is < the smallest observed B-pair distance AND no top feature has |d|>=1 with direction consistency>=0.8, treat as potential behavioral duplicate.
- These remain empirical calibration outputs, not a theoretical standard.