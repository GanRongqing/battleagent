# W6-dev4 Decision Quality Audit

## 1. Audit scope
Real reallocations from 5 live W6-dev4 episodes (S2 × B3, diagnostic seeds 4001–4003, two
extra draws) with per-event + per-step trail logging (`dev4_events.jsonl`, `dev4_trail.jsonl`).
Plus an offline near-miss gate study over the 2035 saved allocator states.

## 2. Real reallocation events
7 events, ALL of type `REALLOC_FREE` (a FREE USV added to an imminent/uncovered target).
No SOFT_COMMITTED release and no handoff fired in any of the 5 draws.
Reasons: BREAKTHROUGH_URGENT ×5, BETTER_INTERCEPTOR ×2. Hard-commit violations 0,
execution override 0.

## 3. Short-horizon consequences (trail-based)
- deaths within 300/600 s after realloc: 0
- persists on the new target ≥300 s: 5/7
- released from the new target within 300 s: 2/7 (both at sim ≈ 21–21.7k s, late game)
- lock formed by 1200 s: 0 (free adds rarely reach a lock before resolution)
- candidate slower than existing lead (>2×) : 0 (all adds had lead ETA comparable/worse-free)

## 4. Verdicts (decision-local, not win-based)
| event | seed | type | reason | persist≥300 | dead | verdict |
|---|---|---|---|---|---|---|
| e0 | 4001 | REALLOC_FREE | BREAKTHROUGH_URGENT | yes | no | GOOD |
| e1 | 4003 | REALLOC_FREE | BETTER_INTERCEPTOR | yes | no | GOOD |
| e2 | 4003 | REALLOC_FREE | BETTER_INTERCEPTOR | yes | no | GOOD |
| e3 | 4002 | REALLOC_FREE | BREAKTHROUGH_URGENT | yes | no | GOOD |
| e4 | 4002 | REALLOC_FREE | BREAKTHROUGH_URGENT | yes | no | GOOD |
| e5 | 4002 | REALLOC_FREE | BREAKTHROUGH_URGENT | no (<300 s) | no | BAD (late transient) |
| e6 | 4002 | REALLOC_FREE | BREAKTHROUGH_URGENT | no (<300 s) | no | BAD (late transient) |

Summary: GOOD 5, BAD 2, NEUTRAL 0, AMBIGUOUS 0.

## 5. Near-miss opportunities (offline proxy)
Of the 2035 saved states: 895 have an imminent (high-risk/deficit) corridor; 777 have a FREE
platform whose best-ETA target is one of those imminent corridors (~38%, matching the earlier
soft/elastic counterfactual). i.e. a large *potential* reallocation pool to imminent corridors
exists. Live dev4 only realised a handful because it (a) only acted on FREE platforms (soft
release never triggered in these draws), (b) required dest uncovered or ≥25% ETA gain over the
current lead, and (c) a step cadence gate. It was NOT limited by score magnitude.

## 6. Gate breakdown (live / offline)
The dominant practical gate is **eligibility of platforms that are not actively locking** in
the right place at the right time; committed SOFT platforms were rarely release candidates in
these draws, so the free-add path dominated. A reliable machine-readable per-state gate
attribution could not be produced without more instrumentation (see notes); the qualitative
breakdown over the debug scan: most imminent targets already carry a comparable lead, so a
FREE add is an extra attacker, not a replacement — high-certainty GOOD in 5/7, churn-like BAD
2/7 only very late.

## 7. Commitment classification quality
SOFT release essentially never fired live in 5 draws → SOFT too permissive: NO evidence.
HARD protection correct (0 violations, 0 interruptions).
No evidence of over-broad SOFT.

## 8. Reserve quality
Reserve create/release counters fired (2–7/game); no evidence reserve release caused harm
(no coverage collapse, no deaths-after-release measured).

## 9. Handoff quality
Handoff (owner swap) never triggered in the draws. From the offline data, alternatives rarely
beat current leads by ≥25% (the W5 allocator already assigns the nearest); so the low handoff
count is mostly genuine lack of benefit, not a gate artefact.

## 10. Final diagnosis
Decision expressivity now produces a small number of explainable, mostly-good FREE additions to
imminent corridors (5 GOOD / 2 BAD, both very late and harmless), 0 hard violations. SOFT and
handoff paths are rarely eligible because committed platforms are usually the best owners
already; the opportunity that remains is adding FREE platforms to imminent corridors (present in
~38% of states) and its live realisation is throttled mainly by how often a genuinely
uncovered imminent corridor coexists with a spare FREE platform. This is NOT a score-magnitude
problem and NOT evidence that gates are "too conservative" on clearly-good moves.

## 11. Recommended single next change
Relax the REALLOC trigger from "dest uncovered/deficit<0" to also allow committing a FREE
platform to any imminent (risk≥HIGH) corridor that currently has < emergency concentration
(≤2) when the FREE platform is not materially slower than the current best lead (allow ≤1.5×
lead ETA). This is a bounded decision-integration change (WHO/TARGET only) — it increases live
expressivity of the already-GOOD free-add path without touching SOFT/handoff or HOW. Do not
alter weights/hysteresis/reserve.
