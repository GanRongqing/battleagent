# Causal Attribution Report

## Question
How much of C1's seed11001 CER gain (0.71 -> 1.19) is attributable to the survival mechanism?

## Method
1. Non-trigger equivalence (offline): proven — 222/222 states identical when survival off.
2. Retreat trigger count (offline reconstruction from game logs): S2=5, S3=21, S1/S4/S5/S6=0.

## Finding
The survival mechanism only fires on S2 (fan-out) and S3 (two-flank). On S1/S4/S5/S6 it does
NOT fire (white USVs are either never exposed or always have support within 50km).

Consequently:
- S2 (+29 kills, -4 losses): mechanism-triggered => SUPPORTED.
- S3 (+1 kill, 0 loss): mechanism-triggered but weak => PARTIAL_SUPPORT.
- S1/S4/S5/S6 (kill/loss deltas of ±1-4): NOT mechanism-triggered => NOT_ATTRIBUTABLE
  (simulator/timing trajectory divergence, since C1 is non-trigger equivalent to W5).

## Important implication
The S4 "improvement" (1.22 -> 2.00) and S1 "regression" (5.75 -> 4.00) are NOT attributable to the
survival mechanism — they are single-episode timing noise. They should NOT be expected to reproduce
reliably on fresh seeds.

The ONLY robustly-attributable effect is on S2 (and weakly S3). Fresh paired DEV must confirm
whether the S2 benefit reproduces.

## Verdict
**PARTIAL_SUPPORT** (non-trigger equivalent; mechanism effect observed on S2/S3; other deltas are
timing noise, not mechanism). No implementation contamination.
