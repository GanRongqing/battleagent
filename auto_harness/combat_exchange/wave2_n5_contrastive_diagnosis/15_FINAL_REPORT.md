# 15 — FINAL REPORT: WAVE2 N=5 + Contrastive Bottleneck Diagnosis

White = ACE (`agent_hybrid_allocator_expand.py`, sha256 `7527253c…`, UNCHANGED). Deterministic step mode ON.
Seeds 43001–43005. 30/30 WAVE2 episodes valid (12 old + 18 new). No policy change, no C5.

## 1. Does the N=2 conclusion hold after N=5?
**YES.** Classification is unchanged: W2-2 and W2-4 are ROBUST_WIN; W2-1, W2-3, W2-5, W2-6 are
ROBUST_LOSS. No strategy moved class.

## 2. Latest per-strategy outcomes (N=5)
| Strategy | N | Kills | Losses | Pooled CER | Wins |
|---|---|---|---|---|---|
| W2-1 横向编队-中央汇聚箭头突防 | 5 | 10 | 100 | 0.100 | 0/5 |
| W2-2 菱形编队-接近后扇形展开突防 | 5 | 150 | 75 | 2.000 | 5/5 |
| W2-3 菱形编队-两翼包抄中央突进 | 5 | 62 | 82 | 0.756 | 0/5 |
| W2-4 菱形编队-南北两翼镜像夹击 | 5 | 60 | 33 | 1.818 | 5/5 |
| W2-5 菱形编队-中央汇聚箭头突防 | 5 | 66 | 96 | 0.688 | 0/5 |
| W2-6 菱形编队-MUSV外侧绕行SUSV中央收缩 | 5 | 17 | 98 | 0.173 | 0/5 |

## 3. Classes
- ROBUST_WIN: **W2-2 (2.000), W2-4 (1.818)**
- ROBUST_LOSS: **W2-1 (0.100), W2-6 (0.173), W2-5 (0.688), W2-3 (0.756)**
- BORDERLINE: none

## 4. Overall WAVE2 pooled CER
**365 kills / 484 losses = 0.754** (Exchange Wins 10/30).

## 5. Largest success-vs-failure funnel gap
Front-of-funnel: **peak visible tracks 16.4 (WIN) vs 7.35 (LOSS)** and **first engagement ~1.8x later**
in LOSS, then **engage/lock fraction 2.6–2.8x lower**. Downstream magnitude largest at **survival**
(USV alive 9.2 vs 1.2). Per-target persistence/reacquisition and hit/kill closure = NOT_MEASURED
(frozen-agent logs); no instrumentation added.

## 6. Is allocator under-commitment again primary?
**NO.** Both groups engage and lock; no free-USV/zero-owner signature; commitment scales with
detected enemies.

## 7. Track persistence primary?
**PARTIALLY.** Clear peak_vis + engage_frac divergence (earliest), but not separable from
"lost sensing because USVs died" with the current logs.

## 8. Kill closure primary?
**NOT_SUPPORTED as primary.** lock_frac ≈ engage_frac in both groups; kill deficit tracks the smaller
engagement base.

## 9. Survival geometry primary?
**PARTIALLY.** Largest raw gap; but the engagement/track deficit precedes the wipe.

## 10. If only ONE candidate next round
Mechanism to solve: **track persistence / reacquisition** (recover and hold tracks for enemies that do
not present centrally — enemy central-convergence and MUSV-flank geometries), i.e. the front-of-funnel
deficit that appears first. (Survival collapse is the downstream consequence.)
**DO NOT implement it in this round.**

## Methods / limitations
- N=5 = small; descriptive, not statistical significance.
- Groups have different compositions (W1 small; W2 20 vs 30); within-WAVE2 comparison is controlled.
- No root-cause claim beyond transition-level proxy evidence; several funnel layers NOT_MEASURED.
