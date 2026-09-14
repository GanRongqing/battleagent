# W7 Performance Report (interim, honest)
## Candidates (S2 x B3, DEV 4001-4005)
- W5 baseline: clean 4/5 (0.80), brk 0.20, loss 2.6 (mean over 4001-4005)
- W7-recon-a (N=3): clean 0.667, brk 0.333, loss 3.67 -> DROP (no positive signal)
- W7-kc-a (N=5): clean 3/5 (0.60), brk 0.40, loss 3.2 -> DROP (clean -20pp vs W5, brk up)
## Interpretation
Two mechanism-grounded candidates (UAV screen/reacquire bias; kill-chain completion follow-up)
did not beat W5 on S2 B3. W5 remains the strongest deterministic baseline on this opponent at
this scale. Small-N noise is large (same-seed R1/R3), but direction is not encouraging.
## Status
W7 NOT COMPLETE. No robust candidate yet. Remaining budget/tracks: recon-b (coverage-gap),
proactive pre-commit, runtime fast-path, and final combine/3-scale/holdout — to be executed
under the performance-first loop; per §70 results are reported honestly, no fake improvement.
## Leaderboard
see W7_CANDIDATE_LEADERBOARD.csv (sorted by clean).
