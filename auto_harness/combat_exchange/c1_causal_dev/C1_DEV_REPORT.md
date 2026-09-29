# C1 Paired DEV Report (seeds 12101/12102)

## Overall (12 episodes each arm)

| arm | total kills | total losses | pooled CER | exchange wins |
|---|---|---|---|---|
| W5 | 144 | 181 | **0.796** | 5/12 |
| C1 | 114 | 161 | **0.708** | 5/12 |

C1 is WORSE than W5 on pooled CER (0.708 < 0.796), with FEWER kills (114 < 144) but slightly
fewer losses (161 < 181). The kill drop is not offset by the loss reduction.

## Per-strategy (N=2 pooled)

| strategy | W5 K/L CER | C1 K/L CER | ΔCER |
|---|---|---|---|
| S1 横向中央汇聚 | 13/31 = 0.42 | 42/10 = 4.20 | +3.78 |
| S2 扇形展开 | 57/30 = 1.90 | 4/37 = 0.11 | −1.79 |
| S3 两翼包抄 | 23/33 = 0.70 | 30/30 = 1.00 | +0.30 |
| S4 南北镜像 | 13/21 = 0.62 | 14/23 = 0.61 | −0.01 |
| S5 菱形中央汇聚 | 20/36 = 0.56 | 0/36 = 0.00 | −0.56 |
| S6 MUSV绕行 | 18/30 = 0.60 | 24/25 = 0.96 | +0.36 |

Only 3/6 strategies improve (S1, S3, S6). S2 suffers a catastrophic regression.

## Gate verdict

| gate | criterion | result |
|---|---|---|
| G1 | C1 pooled CER > W5 | **FAIL** (0.708 < 0.796) |
| G2 | C1 kills >= 0.95×W5 | **FAIL** (114 < 136.8) |
| G3 | C1 losses < W5 | PASS (161 < 181) |
| G4 | >=4/6 strategies improved | **FAIL** (3/6) |
| G5 | no catastrophic regression | **FAIL** (S2: W5 1.90 → C1 0.11) |
| G6 | S2 reproduced | **FAIL** (reversed) |

## Verdict: **DEV_REVERSED**

The survival-aware retreat does NOT provide a stable combat-exchange advantage. On the fresh
paired seeds it slightly REDUCES pooled CER and catastrophically regresses S2 (the case that
looked best on seed 11001).

## Why S2 flipped

On seed 11001, W5 got 0 kills/18 losses on S2 (a timing-luck trajectory); C1's retreat happened to
produce 29 kills/14 losses. On fresh seeds 12101/12102, W5 achieves 29/16 and 28/14 on its own
(CER ~1.9), while C1's retreat disengages too eagerly and collapses to 4/19 and 0/18.

This confirms the causal-attribution finding: the seed-11001 S2 "gain" was timing noise, not a
reproducible mechanism effect.

## Consequence

C1 is DROPPED. Per the phase rule, do NOT stack further mechanisms onto C1 (no C1.1, no C2 on this
parent). The survival-retreat trigger as implemented is net-negative on combat exchange.
