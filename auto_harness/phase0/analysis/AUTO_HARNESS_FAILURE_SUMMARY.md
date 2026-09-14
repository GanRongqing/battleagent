# W5 Failure Discovery (Phase 0)

## 1. Corpus
S2 (10+10 vs 20) x B3_ADAPTIVE. Corpus seeds 6001-6100 (AUTO_HARNESS_CORPUS_DEV, new, documented).
W5 frozen (hash e823e7bed219...), B3 frozen, physics frozen. N=100 complete, all episodes preserved.

## 2. Outcome distribution
clean 65/100 (0.65, Wilson 95% CI [0.553, 0.736]); breakthrough-wins 26; defeats 9;
non-clean (failure) episodes 35; abnormal 0.

## 3-5. Failure taxonomy / modes / clusters (N=35)
Miner classifies all 35 failures as F3_LOST_TRACK (lost-track runs present + partial reacquire).
This is a COARSE classification: lost-track presence is near-universal in failures and also
present in successes; the miner as built cannot yet split severity/secondary modes. Honest
reading: track-continuity/reacquire pressure is the single dominant shared failure signal,
but finer subclustering (reacquire latency, reacquire-failure vs capacity-hole downstream,
multi-axis load) is REQUIRED next before Phase-1 targeting.

## 6-7. Earliest actionable (all failures, preliminary)
lead_time_s computed per event as (resolution - first_lock) proxy (see
AUTO_HARNESS_FAILURE_EVENTS.jsonl); stable medians need a richer miner pass.

## 8. Success vs failure (N=100 means)
| feature | clean | fail |
|---|---|---|
| first_detection | 1855.6 | 1855.7 (NOT discriminative) |
| lost_track_runs | 9.1 | 11.8 |
| capacity_hole_proxy_steps | 26.1 | 32.7 |
| reacquire_attempts | 175.8 | 208.1 |

## 9. W7 hypotheses (preliminary)
Detection timing is NOT discriminative (recon/late-detection hypotheses weakly supported).
Lost-track + reacquire + visible-not-engaged pressure ARE higher in failures (supports a
track-continuity / capacity theme); kill-chain-specific and coverage-gap hypotheses need the
finer miner pass to quantify.

## 10. Phase-1 targets (provisional)
1) Track continuity / lost-track reduction + reacquire latency (F3/F4 cluster, 35/35 shared).
2) Capacity-hole prevention as downstream (F5 signal present in failures).
3) Multi-axis/attrition to be confirmed by subclustering.
Caveat: miner coarseness means these are provisional; finer failure subclustering is the
immediate next step before a Phase-1 patch is justified.

## 11-12. Recommendation
Complete Phase-0.1 miner refinement (subcluster F3 by reacquire-latency/capacity-hole/multi-axis),
then Phase 1 may target track-continuity/reacquire with an evidence-based intervention.
