# Protected SOFT Persistence Shadow Audit
1 Motivation: static trigger transient; test online persistence (P300/600/1200).
2 State machine: continuous timers per (platform,cur,alt) w/ full reset semantics.
3 Horizons: P300/P600/P1200 (sensitivity only).
4 Replay 4001-4003: P300 exec55 (med life 222s); P600 exec10 (med 480s); P1200 exec2 (270s).
5 Would-execute: persistence sharply reduces volume (as expected).
6 Post-trigger stability: P300 post600 17/55; P600 3/10; P1200 0/2 (4001-4003).
7 Post-trigger reversal: high at P300 (rev300 28/55); lower at P600.
8 Target-switch: recorded in events (see CSVs); moderate.
9 Attribution: all risk-shift LOW/MED->HIGH+ (base def); persistence does not select a distinct
   mechanism class.
10 Assignment-age: not gated (recorded only).
11 Cases: events CSV (109 events); heuristic verdicts mostly TOO_TRANSIENT.
12 Validation 4004-4006: P300 exec38 (post600 1), P600 exec4 (post600 0), P1200 0.
13 Cross-seed: post600 useful signal in only 1-2 of 6 seeds across all horizons.
14 Determinism/fair play/neutrality PASS.
15 Final diagnosis: CASE C.
16 Next: stop hand-crafted SOFT line; recommend RL allocator / sensing / intent direction.
