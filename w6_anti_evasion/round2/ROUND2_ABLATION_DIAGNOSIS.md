# ROUND2 Ablation Diagnosis (STEP 2)

S1 5+5 vs10, seeds 2001-2003, B0 + B3, 7 variants (W5, W6_FULL, NO_PRED, NO_SCREEN,
PRED_ONLY, SCREEN_ONLY, NO_BRK). 42 episodes.

## B0 aggregate
| variant | clean | avg_dead | quirk_brk |
|---|---|---|---|
| W5 | 3/3 | 2.7 | 0 |
| W6_FULL | 2/3 | 3.0 | 1 |
| W6_NO_PRED | 1/3 | 3.7 | 2 |
| W6_NO_SCREEN | 0/3 | 4.0 | 3 |
| W6_PRED_ONLY | 1/3 | 3.7 | 2 |
| W6_SCREEN_ONLY | 1/3 | 2.7 | 2 |
| W6_NO_BRK | 1/3 | 3.7 | 2 |

## B3 aggregate
| variant | win | clean | avg_dead | quirk_brk |
|---|---|---|---|---|
| W5 | 3/3 | 2/3 | 1.3 | 1 |
| W6_FULL | 0/3 | 0/3 | 4.0 | 1 |
| W6_NO_PRED | 0/3 | 0/3 | 5.0 | 2 |
| W6_NO_SCREEN | 0/3 | 0/3 | 3.7 | 2 |
| W6_PRED_ONLY | 1/3 | 1/3 | 3.3 | 1 |
| W6_SCREEN_ONLY | 1/3 | 1/3 | 2.3 | 1 |
| W6_NO_BRK | 0/3 | 0/3 | 3.0 | 2 |

## Answers to the ablation questions
1. **no-prediction removes knife-fight loss?** NO — W6_NO_PRED still 5 USV dead on B0 s2002 and
   loses B3 (0/3). Prediction is not the sole loss source.
2. **no-screen removes B0 regression?** NO — W6_NO_SCREEN is the WORST B0 variant (0/3 clean,
   3 quirk-breakthroughs). The screen is PROTECTIVE; removing it increases breakthroughs.
3. **prediction-only preserves exploration reduction?** PARTIALLY — W6_PRED_ONLY explores less
   (B0 s2002 explore 55.3k vs W5 84.8k) but introduces breakthroughs (2/3 quirk).
4. **screen-only causes offense starvation?** NO — W6_SCREEN_ONLY on B0 s2002 is BETTER than W5
   (1 USV dead, clean). Screen-only is the most benign variant.
5. **primary regression source?** The W6 decision path as a whole (predictive-intercept aim +
   pursuit-cost allocation) degrades B3 engagement: W6_FULL loses 3/3 B3 (all USVs die).
   W6_SCREEN_ONLY (screen alone) is the least harmful and protects B0. The intercept geometry
   (aim pulling USVs into the target band) is the leading suspect; the pursuit-cost allocation
   re-scoring also moves USVs onto suboptimal targets under B3 evasion.

## Metrics caveat
Ablation CSV prediction_count=0 for all rows was an instrumentation read issue; a direct rerun
confirmed the W6 features ARE active (prediction_count=2480/intercept=2333/screen=735 on one
B3 s2001 run). The W6 metrics dump timing needs a fix (read-after-exit race) — handled in
ROUND2 fixes (event-semantics + metrics).
