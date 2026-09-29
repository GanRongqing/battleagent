# Retreat Semantic Audit (C1, seed11001)

Reconstructed C1 survival-retreat trigger conditions from the seed11001 game logs:
`exposed (is_locked or locked_attacker)` AND `no enemy within 40km` AND `nearest friendly > 50km`.

## Reliable finding: retreat-trigger count by strategy

| strategy | exposed steps | exposed + kill-opp | retreat-eligible (exposed + no-kill + far-support) |
|---|---|---|---|
| S1 横向中央汇聚 | 22 | 22 | **0** |
| S2 扇形展开 | 239 | 211 | 5 |
| S3 两翼包抄 | 972 | 211 | 21 |
| S4 南北镜像 | — | — | 0 |
| S5 菱形中央汇聚 | 246 | 15 | **0** |
| S6 MUSV绕行 | — | — | 0 |

## Key conclusion

1. **The survival retreat does NOT trigger on S5 or S1.** On S5 the white USVs are exposed 246
   times but always have a friendly within 50 km (so the "far support" condition never holds);
   on S1 they are only exposed 22 times and always with a kill opportunity.
2. Therefore **the S5 / S1 regressions are NOT caused by false retreats.**
3. The S5/S1 "regressions" are tiny and consistent with single-episode noise:
   - S1: 23/4 (CER 5.75) → 24/6 (4.0) — still a strong win, ±1 kill ±2 losses.
   - S5: 2/20 (0.10) → 1/18 (0.056) — both ~0, ±1 kill ±2 losses.
4. Retreat-eligible events are concentrated on S2 (5) and S3 (21) — the two strategies that
   IMPROVED, not regressed.

## Limitation
The velocity-based "closing vs passing" sub-classification was too noisy to be reliable, so
`C1_RETREAT_EVENT_AUDIT.csv` reports counts only (not confident TRUE vs FALSE labels).

## Verdict
**ROOT CAUSE CONFIRMED = NO.** The hypothesis "S5/S1 regression is caused by false passing-target
retreats" is refuted: retreat does not fire on S5/S1 at all, and the regressions are noise-level.

Per instruction (step 8): STOP — do not implement the C1.1 survival-trigger semantic fix based on
this hypothesis.

C1 already shows a strong aggregate improvement (pooled CER 0.71 → 1.19, seed11001), driven by
S2/S4. Recommended next step: carry C1 forward (DEV on 12101/12102) rather than patch C1.1.
