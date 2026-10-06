# 14 — Primary Bottleneck

## Verdict
**MIXED** (TRACK_PERSISTENCE front-of-funnel deficit + SURVIVAL_GEOMETRY downstream collapse)

## Strongest Evidence
1. **Front-funnel (track/engagement formation) deficit, earliest divergence.** ROBUST_LOSS keeps only
   **peak_vis 7.35** vs WIN **16.4** visible tracks (~2.2x), forms its first engagement **~1.8x later**
   (12.3k s vs 6.9k s), and holds active engagements/locks only **~2.6–2.8x less** of the episode
   (`engage_frac` 0.075 vs 0.198; `lock_frac` 0.071 vs 0.198). Locks start at similar sim-time in both
   (≈6.6–6.9k s), so lock *initiation* is not the blocker — sustained track→engagement is.
2. **Downstream survival collapse, largest magnitude.** ROBUST_LOSS ends with **1.2 USVs alive** vs
   **9.2** in WIN (7.7x) and **7.3 kills** vs **19.5** (2.7x). The failure group is effectively wiped.
3. **Allocator is NOT reopened.** Both groups reach lock/engagement; the loss group is not failing at
   `visible-but-unassigned`. Pooled commitment proxies (max_engaged 2.8 vs 5.1) scale with the number
   of detected enemies, not with a free-USV/zero-owner gap.

## Evidence Against Alternatives
- **TRACK_PERSISTENCE (alone):** PARTIALLY SUPPORTED. `peak_vis` and `engage_frac` clearly diverge, but
  we cannot separate "White fails to detect" from "White lost sensors because its USV/UAV died"
  (both move together). Per-target persistence/reacquisition is NOT_MEASURED (absent from logs).
- **KILL_CLOSURE (alone):** NOT SUPPORTED as primary. `lock_frac ≈ engage_frac` in both groups ⇒ the
  lock→engagement conversion is not differentially broken; the kill deficit scales with the smaller
  engagement base, not with a lock→hit closure failure. (Hit/kill per-target closure NOT_MEASURED.)
- **SURVIVAL_GEOMETRY (alone):** PARTIALLY SUPPORTED. The largest raw gap is survival, but the
  engagement/track deficit appears **before** the wipe, so survival is at least partly downstream.
- **ALLOCATOR_REOPENED:** NO. No visible-but-unassigned / free-USV+zero-owner signature in the
  aggregate; both groups engage and lock.

## Confidence
**MEDIUM** — direction is consistent and monotone across all 30 episodes; but exact per-target
persistence, HP, and hit/kill closure are NOT_MEASURED in the frozen-agent logs, so the front-funnel
vs survival causal ordering cannot be separated beyond the timing evidence above.

## Candidate Direction (concept only — DO NOT IMPLEMENT)
- If front-funnel dominates: **track-aware reacquisition / predictor-selection** (recover tracks for
  enemies that do not present centrally, e.g. enemy central-convergence and MUSV-flank geometries).
- If survival dominates: **pre-lock admission / synchronized approach** (avoid feeding the local enemy
  concentration).
Given MIXED, the single most-justified next candidate is a **track-persistence / reacquisition**
mechanism (front-of-funnel, earliest divergence), evaluated on W2-1/-3/-5/-6.
