# Anti-Leak FRESH Validation (S2×B3, seeds 8101–8130, paired N=30)

No parameter changes between DEV and fresh. Artifact `5fe78b73ae07…` unchanged.

| metric | W5 | candidate |
|---|---|---|
| clean | 22/30 = 0.733 (CI 0.556–0.858) | 19/30 = 0.633 (CI 0.455–0.781) |
| breakthrough | 7/30 = 0.233 (CI 0.118–0.409) | 11/30 = 0.367 (CI 0.219–0.545) |
| defeat | 2/30 = 0.067 (CI 0.018–0.213) | 1/30 = 0.033 (CI 0.006–0.167) |
| loss mean/median/p25/p75 | 3.90 / 3.5 / 3 / 5 | 3.23 / 3.0 / 2 / 4 |
| resolution mean/median/p25/p75 | 26558 / 25766 / 17863 / 34628 | 26281 / 22579 / 18160 / 36161 |
| enemy survivors mean | 0.367 | 0.433 |
| last-kill tail mean/median | 8260 / 5967 | 8198 / 5136 |

Paired transitions:
- breakthrough: W5-brk→cand-no **7**, W5-no→cand-brk **11**, both-no 12, both-brk 0 (McNemar p=0.481).
- defeat: W5-def→cand-no 2, W5-no→cand-def 1, both-no 27 (p=1.0).
- clean: W5-clean→cand-not 11, W5-not→cand-clean 8, both-clean 11.

Mechanism (candidate): 6/30 episodes triggered; 10 triggers; 1 preemption; unblocked HIGH 61; unblocked CRITICAL 58.
(DEV had 11/30 episodes, 19 triggers, 258/89 unblocked — much higher.)

## Direction vs DEV
| metric | DEV (W5→cand) | FRESH (W5→cand) | reproduced |
|---|---|---|---|
| breakthrough | 0.467→0.200 (↓) | 0.233→0.367 (↑) | **NO (reversed)** |
| clean | 0.500→0.733 (↑) | 0.733→0.633 (↓) | NO (reversed) |
| defeat | 0.133→0.200 (↑) | 0.067→0.033 (↓) | NO (reversed) |
| loss | 3.20→3.37 | 3.90→3.23 (cand better) | NO |
| resolution | 27736→26594 | 26558→26281 | neutral |

## FRESH VERDICT = **FAIL**
The DEV breakthrough improvement did **not** reproduce; the direction reversed (candidate worse on
breakthrough and clean on fresh seeds). Per the stop gate: no promotion, W5 remains the frozen
current White baseline, and Phase2 stacking is not entered. This mirrors the W7 Gap-A lesson
(small-N positive reversed on new seeds).

Source: `auto_harness/phase1/fresh_w5/EPISODES.csv`, `fresh_cand/EPISODES.csv`.
