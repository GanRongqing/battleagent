# Case Study: Anti-Leak (white-auto-0001-v1)

- Candidate: `agent_hybrid_w8_containment.py` (policy white-auto-0001-v1), parent W5.
- Tests: unit / fair-play / W5-equivalence 12/12 PASS (test_anti_leak.py).
- DEV (seeds 8001-8030): breakthrough 0.467 -> 0.200 (paired 11:3, McNemar p=0.057);
  clean 0.500 -> 0.733; defeat 0.133 -> 0.200.
- FRESH (seeds 8101-8130): FAIL — breakthrough direction REVERSED (0.233 -> 0.367).
- Verdict: **not promoted** (remains candidate; status validation). Illustrates
  DEV-only gains do not survive a fresh-seed holdout.
- Artifacts: auto_harness/phase1/ANTI_LEAK_*.{json,md,csv}, FAILURE_MINER_V2.*
