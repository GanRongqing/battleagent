# EXISTING ISOLATION RESULT AUDIT

Target config for the isolation chain: **S2 (10+10 vs 20) × B3_ADAPTIVE × seeds
4001–4003**, execution = LEGACY W5 controller, UAV behavior UNIFORM across A–F (W5 default;
W6 UAV-track-maintenance OFF during isolation so it never leaks into a component step).

| variant | seed | existing result? | reuse? | reason |
|---|---|---|---|---|
| A W5_BASE | 4001 | `W6_DEV3_DIAGNOSTIC.csv` A_W5 S2 s4001 = Victory, dead 4 | REUSE | pure W5, exact config match |
| A W5_BASE | 4002 | A_W5 S2 s4002 = Victory, dead 6 | REUSE | same |
| A W5_BASE | 4003 | A_W5 S2 s4003 = Victory, dead 2, brk 1 | REUSE | same |
| B +Prediction | 4001-4003 | none | RUN | prediction-only iso variant not previously run (prior "prediction_only" had reserve+UAV maint ON) |
| C +Risk | 4001-4003 | none | RUN | risk-enabled reinforcement with UAV maint OFF not run |
| D +PursuitCost | 4001-4003 | none | RUN | pursuit-cost-aware candidate selection not isolated |
| E +Handoff | 4001-4003 | none | RUN | handoff-only incremental not run |
| F +Reserve | 4001-4003 | `C_dev3` rows exist but UAV maint was ON | RUN | must re-run with uniform UAV behaviour (maint OFF) for a clean E→F delta |

New episodes required: B..F × 3 = **15** (budget ≤ 18). Variant A reused (0 new).
No G (+track maintenance) for now — UAV behaviour is pinned to the W5 default in A–F.
