# Anti-Leak DEV Results (paired, S2 x B3)

- paired N = 30

| metric | W5 | candidate |
|---|---|---|
| clean rate | 0.5 (CI (0.332, 0.668)) | 0.733 (CI (0.556, 0.858)) |
| breakthrough rate | 0.467 (CI (0.302, 0.639)) | 0.2 (CI (0.095, 0.373)) |
| defeat rate | 0.133 (CI (0.053, 0.297)) | 0.2 (CI (0.095, 0.373)) |
| friendly loss mean | 3.2 | 3.37 |
| resolution mean | 27736.1 | 26593.6 |

- breakthrough delta (cand - W5) = -0.267

## Paired transitions (breakthrough)

- W5 fail -> candidate clean: 11
- W5 clean -> candidate fail: 3
- both clean: 13
- both fail: 3

## Mechanism KPIs

```
{
  "episodes_with_events": 30,
  "containment_triggers_mean": 0.63,
  "containment_triggers_total": 19,
  "preemptions_total": 5,
  "episodes_with_trigger": 11,
  "unblocked_high_evals_total": 258,
  "unblocked_critical_evals_total": 89
}
```

## Causal verdict = **BAD_TRADEOFF**
