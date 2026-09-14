# W7 Search Space Summary
Attack surfaces tested (all on frozen W5, S2xB3, legal obs only, execution override 0):
1 Sensing exploitation (recon-a) -> DROP
2 Kill-chain completion (kc-a) -> DROP
3 Coverage-gap dynamic sensing (recon-b1) -> DROP
4 Runtime fast-path (profile) -> DROP (latency not bottleneck)
5 Combat capacity-hole prevention (gap-a) -> DROP (N10 clean 0.60 vs W5 0.80)
Search closed after 5 independent directions produced no robust win-rate improvement and all
positive early signals reversed at larger N. W5 is at/near a local optimum of the hand-crafted
deterministic search space on this opponent/scale. Further unbounded heuristic search is
stopped by policy (not by lack of effort).
