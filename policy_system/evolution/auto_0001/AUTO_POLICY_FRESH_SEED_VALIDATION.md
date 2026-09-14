# AUTO_POLICY_FRESH_SEED_VALIDATION — black-auto-0001-v1 vs B0 (nearest)

Seeds 7101-7110 (fresh DEV, disjoint from 7001-7010).
- candidate N = 10, reference N = 10
- behavior distance = 1.309
- response distance = 0.689
- multi-seed = stable
- fresh novelty verdict = EMPIRICALLY_DISTINCT

## Top behavioral differences (fresh seeds)

| feature | mean cand | mean ref | Cohen's d | seed consistency |
|---|---|---|---|---|
| structure.early_late_concentration_delta | 0.095 | 0.535 | 5.511 | 1.0 |
| structure.early_force_commitment_ratio | 0.105 | 0.465 | 4.509 | 1.0 |
| spatial.mean_visible_group_count | 4.45 | 4.97 | 2.471 | 1.0 |

## DEV (7001-7010) vs FRESH (7101-7110)

| feature | DEV d | FRESH d | direction preserved |
|---|---|---|---|
| structure.early_late_concentration_delta | 5.052 | 5.511 | True |
| structure.early_force_commitment_ratio | 3.83 | 4.509 | True |
| spatial.mean_visible_group_count | 1.747 | 2.471 | True |