# 16 — FINAL REPORT: Search vs Survival Causal Split

ACE unchanged (7527253c…). No policy/truth in runtime. Source = existing 30 WAVE2 N=5 episodes (0 new).

## Answers
1. **Did W2 ROBUST_LOSS see clearly fewer enemies before the first White combat-USV death?**
   **NO.** Median first contact: WIN 6,570 s vs LOSS 6,720 s (≈equal); median first death: WIN 6,270 s
   vs LOSS 6,270 s (identical). Pre-contact visible tracks are 0 for both. The "peak visible 16.4 vs
   7.35" gap is a whole-episode max from the combat phase.
2. **Does the difference survive alive-sensor normalization?** The WIN/LOSS sensor counts are equal
   pre-casualty; the track gap appears only after LOSS is wiped → largely explained by fewer
   surviving sensors.
3. **Observability oracle:** NOT_AVAILABLE (sensing eligibility not reliably reconstructable; none invented).
4. **First White casualty time:** WIN median 6,270 s; LOSS median 6,270 s (same).
5. **Does the visible-track gap widen before or after casualty?** **AFTER** casualty (in LOSS).
6. **Why do W2-1 and W2-5 both fail?** Same late-catastrophe signature: acquire late/none, get wiped
   (W2-1 even dies before contact). Shared pattern is engagement survival, not an early search blind spot.
7. **Why do W2-2 / W2-4 succeed?** They acquire at ≈6.3k s and **survive** the engagement (final alive
   ≈8–13). Success signature = engagement survival, not faster search.
8. **SEARCH upstream or downstream?** Downstream/shared: search is equally unproductive for both groups;
   it amplifies losses but does not cause the WIN/LOSS split.
9. **SURVIVAL upstream or downstream?** **UPSTREAM.** The split is at contact→survival.
10. **Next candidate:** **C6B = PRE_LOCK_ENGAGEMENT_ADMISSION** (observation-derived; avoid feeding
    unsupported USVs into engagement geometry). Not implemented.

## Verdict
**SURVIVAL_GEOMETRY**, confidence **MEDIUM** (leaning HIGH: contact/death timings are nearly identical,
outcome differs by ~8x in surviving USVs). SEARCH is a shared non-differential weakness.

## Notes
- 0 new episodes; offline parsing only. No diagnostic logger added (invariance gate trivially preserved).
- C5 not continued; no C6 implemented.
