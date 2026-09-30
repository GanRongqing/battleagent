# ACE 12-Strategy N=2 Quick Generalization Report

White = ACE (`agent_hybrid_allocator_expand.py`, sha256 `7527253c…`), LLM off, deterministic step mode ON.
Seeds 43001/43002, N=2 per strategy, 24/24 valid episodes. **Quick (N=2) = descriptive only; not a
statistically confirmed generalization.**

## Main table

| Strategy | N | Black Kills | White Losses | Pooled CER | Exchange Wins |
|----------|---|-------------|--------------|------------|---------------|
| B0 | 2 | 60 | 16 | 3.750 | 2/2 |
| B1 | 2 | 50 | 5 | 10.000 | 2/2 |
| B2 | 2 | 57 | 7 | 8.143 | 2/2 |
| B3 | 2 | 60 | 14 | 4.286 | 2/2 |
| W1-1 分散式 dispersed | 2 | 9 | 6 | 1.500 | 2/2 |
| W1-2 两波次 two-wave | 2 | 14 | 2 | 7.000 | 2/2 |
| W2-1 横向编队-中央汇聚箭头突防 | 2 | 4 | 40 | 0.100 | 0/2 |
| W2-2 菱形编队-接近后扇形展开突防 | 2 | 60 | 23 | 2.609 | 2/2 |
| W2-3 菱形编队-两翼包抄中央突进 | 2 | 26 | 30 | 0.867 | 0/2 |
| W2-4 菱形编队-南北两翼镜像夹击 | 2 | 24 | 12 | 2.000 | 2/2 |
| W2-5 菱形编队-中央汇聚箭头突防 | 2 | 23 | 40 | 0.575 | 0/2 |
| W2-6 菱形编队-MUSV外侧绕行SUSV中央收缩 | 2 | 8 | 38 | 0.211 | 0/2 |

## Group summary

| Group | Strategies | Episodes | Black Kills | White Losses | Pooled CER | Exchange Wins |
|-------|-----------|----------|-------------|--------------|------------|---------------|
| OLD_LOCAL | 4 | 8 | 227 | 42 | 5.405 | 8/8 |
| WAVE1 | 2 | 4 | 23 | 8 | 2.875 | 4/4 |
| WAVE2 | 6 | 12 | 145 | 183 | 0.792 | 4/12 |
| ALL | 12 | 24 | 395 | 233 | 1.695 | 16/24 |

## Answers
1. **OLD_LOCAL** (B0-B3): pooled CER **5.405**, 8/8 exchange wins — ACE dominates.
2. **WAVE1** (wang.rar): pooled CER **2.875**, 4/4 wins. dispersed ~1.5 (low kill volume, small
   composition), two-wave 7.0.
3. **WAVE2** (六个策略): pooled CER **0.792**, only 4/12 wins — clear drop.
4. **OLD → WAVE1 → WAVE2 = YES, clear degradation.** 5.405 → 2.875 → 0.792.
5. **Hardest** (ACE loses): W2-1 中央汇聚箭头突防 (0.10), W2-6 MUSV外侧绕行 (0.21),
   W2-5 中央汇聚箭头突防 (0.575), W2-3 两翼包抄中央突进 (0.867) — all 0/2.
6. **Strongest**: B1 (10.0), B2 (8.14), W1-2 two-wave (7.0), B3 (4.29), B0 (3.75), W2-2 fan-out (2.61).
7. **New-opponent degradation signal = YES** (WAVE2 especially; note W2-2 fan-out is an exception).
8. **Worth expanding N**: the boundary cases W2-3 (0.867) and W2-5 (0.575) (near tie), plus the
   consistent-loss W2-1 and W2-6, to confirm direction.

## Caveats
- N=2 ⇒ descriptive only. Different compositions across groups (B0-B3 run 20 USV+10 UAV vs 30 black;
  W1 uses its own small composition; W2 uses 20 vs 30) — cross-group CER is indicative, not controlled.
- No root-cause claim is made (not supported by the logs); this is a summary of outcomes.
