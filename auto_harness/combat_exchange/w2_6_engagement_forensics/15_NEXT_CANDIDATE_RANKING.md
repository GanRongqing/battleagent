# 15 — NEXT CANDIDATE RANKING (evidence-ranked, no implementation)

### Priority 1 — Break the freeze→second-hit chain (survival / de-fragmentation)
- Evidence: prelock deaths 8/18 (ACE) vs 1 on W2-4; first hit freezes victim 300 s (engine rule).
- Intervenable transition: first-hostile-lock → survive to own-lock (avoid/absorb the first hit).
- Legal observables: `is_locked`/`locked_attacker` (know when being locked), own `is_frozen`, positions.
- Shadow method: offline, detect White units under hostile lock but not yet hit; test a bounded
  reorganization (move lock-capable neighbours to cover them / break the enemy's lock by range).
- Falsified if: prelock deaths do not fall, or concurrency/windows do not rise.
- Control risk: medium (movement changes can disturb W2-4).
- Complexity: medium.

### Priority 2 — Concentrate arrival to raise concurrent windows
- Evidence: max concurrency 4 vs 9; reach 14 vs 17; C10 raised windows but not concurrency.
- Transition: in-range arrival → simultaneous own-lock (overlap of ≥300 s windows).
- Legal observables: positions/tracks of already-converting units.
- Shadow: measure C(t) if N units staged to arrive within one macro-step window.
- Control risk: high (this is the C7 lever that regressed W2-4 without a budget).
- Complexity: medium-high.

### Priority 3 — Observation gap (W2-1 / W2-2, NOT W2-6)
- Evidence: only 3–4 of 30 Black ever positioned; W2-1 0 reach.
- Transition: passive bearing → positioned track (sensor/UAV coverage).
- Control risk: low for W2-6 (not its bottleneck).
- Complexity: high.

Note: none of these is a "coordination count" mechanism; they target survival and overlap, per the data.
