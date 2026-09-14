# W6-dev3 Diagnostic Ablation Report (24 episodes)

Config: S1 + S2, opponent B3_ADAPTIVE, DEV/diagnostic seeds 4001–4003 (now marked
diagnostic — no longer an unseen holdout), 4 variants × N=3 per scale.
`controller_mode = LEGACY_W5`, sim unchanged. Data: `W6_DEV3_DIAGNOSTIC.csv`.

## Aggregate (mean over N=3)

| Scale | Variant | clean | friendly loss | kills | breakthrough | explored km² | res s | exec-override actions |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| S1 | A W5 | 1/3 | 2.67 | 10.0 | 2 | 82,783 | 30,252 | 0 |
| S1 | B dev2 | 0/3 | **5.00** | 8.7 | 1 | 59,217 | 26,642 | **121** |
| S1 | C dev3 | 1/3 | **3.00** | 9.3 | 1 | 62,250 | **21,711** | **0** |
| S1 | D pred-only | 1/3 | 3.33 | 9.3 | 0 | 60,817 | 22,961 | 0 |
| S2 | A W5 | 2/3 | **4.00** | 20.0 | 1 | 92,983 | 22,852 | 0 |
| S2 | B dev2 | 0/3 | **10.00** | 18.0 | 0 | 82,100 | 27,789 | **151** |
| S2 | C dev3 | 0/3 | **8.00** | 18.7 | 2 | 81,975 | 28,135 | **0** |
| S2 | D pred-only | 0/3 | **10.00** | 18.7 | 2 | 78,092 | 26,616 | 0 |

## Answers to the ablation questions

- **Q1 (does dev3 reduce dev2 friendly loss?)** Partial. S1 5.0 → 3.0 (−40%), S2 10.0 → 8.0
  (−20%). Improvement, but NOT a full survival recovery: dev3 S2 still averages 8/10 USV
  dead vs W5 4.0.
- **Q2 (exploration benefit retained?)** Yes. dev3 < W5 explored on both scales (S1 −25%,
  S2 −12%); similar to dev2.
- **Q3 (does prediction-only already give the benefit?)** No. D is not clearly better than W5
  and still collapses at S2; prediction features alone (no allocator action) do not deliver
  the anti-evasion benefit.
- **Q4 (positive marginal value of the dev3 allocator over the legacy controller?)** Weak /
  seed-dependent. At S1 dev3 modestly beats W5 on resolution & loss; at S2 dev3 is still
  worse than W5. Residual value uncertain at N=3.
- **Q5 (is dev2's main negative contribution the execution override?)** Only partially.
  dev3 removed ALL execution overrides (121–151/game in dev2 → 0 in dev3) and improved S1
  survival, but S2 still collapses → execution override is not the sole cause; allocator /
  sensing-layer interactions remain.

## Caveats

- Seeds 4001–4003 are hard B3 seeds where even W5 only reaches clean 1/3 (S1) and 2/3 (S2).
- Run-level nondeterminism is present (see `coevolution_final/RNG_NONDETERMINISM.md`);
  N=3 per setting is small. The 10-dead collapses in dev2/dev3/D on S2 vs 4.0 for W5 should
  be re-read with larger N before strong claims.
- Mechanism counters confirm the boundary fix: `w6_execution_override_actions` = 0 for dev3
  and prediction-only in every episode; dev2 = 15–151.

## Decision

Survival gate (dev3 friendly loss clearly back toward W5) NOT passed at S2. Per the brief
(§23/§31): do NOT proceed to the 30-episode 3-scale DEV; do NOT freeze. Next step =
**component isolation of the allocator score** (W5 → +prediction → +breakthrough risk →
+pursuit cost → +handoff → +reserve, one feature at a time), keeping legacy execution.
