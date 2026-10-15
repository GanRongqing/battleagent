# 01 — OFF EQUIVALENCE
`OBS_TI_REVIVE=0` reproduces the frozen baselines exactly on W2-6 seed 43001:
| policy | OFF (E4) | E2/E3 baseline |
|---|---|---|
| ACE | 10/18 (0.556) | 10/18 (0.556) |
| C10 | 11/16 (0.688) | 11/16 (0.688) |
| C11 | 11/16 (0.688) | 11/16 (0.688) |
=> OFF is behaviour-identical (env-gated fix inactive). New tests added: truly-dead not revived; live
   positioned contact revived (test_observation_integrity 7/7).
