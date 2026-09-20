# White Phase 1 Final Report — Anti-Leak Containment (white-auto-0001-v1)

## Phase 0 evidence (inherited)
W5×B3, S2, 6001–6100, N=100: clean 65 / breakthrough 26 / defeat 9; 35/35 non-clean have
exactly one breakthrough. Detection/first-lock/first-kill NOT discriminative; raw lost-track/
reacquire/capacity differences are duration artifacts (miner v2). Signature = single leak +
containment failure + long tail.

## Candidate
`white-auto-0001-v1` (anti_leak_containment), parent W5, allocator overlay only,
execution_override=false. Artifact `5fe78b73ae07…`, bundle `2fcde232ba81…`.

## Mechanism validation (offline)
- unit/fair-play/hidden-truth/variable-cardinality: 12/12 PASS (`test_anti_leak.py`).
- W5 non-trigger equivalence: 500/500 identical.
- offline replay (6001–6100 proxy): failure coverage 1.0, CRITICAL 0.343, clean false HIGH 0.431 / CRITICAL 0.077.

## DEV paired tournament (S2×B3, seeds 8001–8030, paired N=30)
| metric | W5 | candidate |
|---|---|---|
| clean | 15/30 = 0.500 | 22/30 = 0.733 |
| breakthrough | 14/30 = 0.467 | 6/30 = 0.200 |
| defeat | 4/30 = 0.133 | 6/30 = 0.200 |
| friendly loss mean | 3.20 | 3.37 (median 3 vs 3) |
| resolution mean | 27736 | 26594 |

Paired transitions:
- breakthrough: W5-brk→cand-no **11**, W5-no→cand-brk **3**, both-brk 3, both-no 13 (McNemar p=0.057).
- defeat: W5-def→cand-clean 3, W5-clean→cand-def 5, both-def 1, both-no-def 21 (McNemar p=0.727).

Mechanism KPI (candidate runtime, `*_w8events.json`): containment triggers total 19 across
11/30 episodes; preemptions 5; unblocked HIGH-risk evals 258; unblocked CRITICAL 89.
(W5 has no equivalent instrumentation, so unblocked-duration W5-vs-candidate is NOT RECORDED.)

## DEV verdict
**SUPPORTED (provisional).**
- breakthrough: clear reduction (0.467→0.200), paired 11:3 (p=0.057).
- clean: clear increase (0.500→0.733).
- loss: non-inferior (median 3 vs 3).
- resolution: improved (27736→26594).
- defeat: point estimate up (0.133→0.200) but **not statistically significant** (McNemar p=0.727);
  the pre-registered hard guardrail flagged this as a caveat, so promotion requires fresh validation.

## Next gate
Fresh validation 8101–8130 (paired W5 vs candidate, N=30) — started, no parameter changes allowed.

## Data gaps
- W5 unblocked crossing-risk duration: NOT RECORDED (no instrumentation on W5).
- last-kill tail per arm: NOT RECORDED in EPISODES.csv (derivable only from logs; not extracted here).
