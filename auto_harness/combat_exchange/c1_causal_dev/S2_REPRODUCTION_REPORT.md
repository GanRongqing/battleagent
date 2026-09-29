# S2 Reproduction Report (扇形展开)

S2 (fan-out) was the largest seed-11001 C1 "win" (W5 0/18 → C1 29/14). This is the key
reproduction check.

| seed | W5 K/L CER | C1 K/L CER | classification |
|---|---|---|---|
| 11001 (historical smoke) | 0/18 = 0.00 | 29/14 = 2.07 | (baseline artifact) |
| 12101 (fresh) | 29/16 = 1.81 | 4/19 = 0.21 | REVERSED |
| 12102 (fresh) | 28/14 = 2.00 | 0/18 = 0.00 | REVERSED |

## Classification: **REVERSED**

On both fresh seeds, C1 is dramatically WORSE than W5 on S2. The seed-11001 result (W5 0 kills)
was a single-run timing artifact: W5 naturally achieves CER ~1.9 on S2 on fresh seeds.

## Interpretation

C1's survival retreat is harmful on the fan-out geometry: when the black fans out and does not
concentrate on individual White USVs, the "exposed" signal is weak, but the retreat still
disengages White USVs from kill opportunities, collapsing kill output (4/19, 0/18) without
meaningfully saving ships (losses 19 and 18 vs W5's 16 and 14).

The S2 benefit claimed from seed 11001 is NOT reproducible and is therefore attributed to
timing noise (consistent with the earlier causal audit).
