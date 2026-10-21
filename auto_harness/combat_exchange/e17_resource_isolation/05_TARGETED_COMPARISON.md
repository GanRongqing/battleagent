# 05 — W2-5 TARGETED COMPARISON (seed 43001, identity VERIFIED)
| version | K/L | CER | traj hash | positioned Black | usv4 radar steps | breach unit | result |
|---|---|---|---|---|---|---|---|
| C10 (baseline) | 27/14 | 1.929 | 384b46b27af4 | 26 | 0 | usv4 (N y=+115) | Defeat |
| **Track-Only v2** | **27/14** | **1.929** | **384b46b27af4** | **26** | **0** | **usv4** | **Defeat** |
| C16 v2 | 23/12 | 1.917 | 87a6d23f51b8 | 22 | **0** | usv8 (S y=−75) | Defeat |
- **Track-Only ≡ C10 (bit-identical trajectory).** The non-invasive passive-history fix (separate history,
  no track-freshness mutation) is behaviour-neutral. VERIFIED.
- (Earlier Track-Only v1 that mutated `last_seen_time` regressed to 16/17 → showed the fix must NOT touch
  base track freshness; corrected.)
- **C16 changes decisions** (trajectory differs) but does **not localize usv4** (0 radar steps) and the breach
  moves to usv8; W2-5 regresses (27/14 → 23/12). VERIFIED. Not a no-op, but net negative.
- Clean Victory: **0** (still 1 breach).
