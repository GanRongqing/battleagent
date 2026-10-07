# 08 — DETERMINISM CHECK  (GATE: FAIL — deeper than judge_system)

## Attempts
1. Baseline C7: W2-1/43001 x2 -> outcome identical, per-step hash differs (first mismatch step 945/993;
   `white_usv6`<->`white_usv15` freeze/position swap).
2. Applied approved fix: `judge_system._judge()` raw-set iterations -> sorted-by-name
   (`self.units` L77/108/117, `self.black_ships` L99, `self.white_ships` L107).
3. Hardened service env: `PYTHONHASHSEED=0` for base_server + API.
4. Re-ran gate: **still FAIL.** total_steps now equal (993=993) but first mismatch at step 929/993:
   `white_usv14`<->`white_usv7` swap `is_frozen`/`locked_times`/x (119882<->120464, ~582 m = ~1 macro-step).

## Verdict: NOT deterministic (bit-level). Outcome identical.
All outcome + lock-conversion metrics are identical across same-seed runs; only per-step state
diverges via a late **2-unit freeze tie-flip** between mirror units.

## Root cause (deeper, NOT C7 and NOT judge_system)
`hsystem/simulation/arsenal/locker.py:106` decides a lock "hit" with `random.random() > 0.2`
(freeze + `locked_times`). The divergence is the RNG-based hit landing on one of two **mirror** units
(usv6/usv15, usv7/usv14; y ≈ ±34370) one macro-step apart. This is an **RNG-consumption / event-order
tie** in the compiled engine layer (symmetric units resolved in an order that is not stable across
runs), not the `_judge` set iteration (which was fixed and did not change the result).

## Evidence against the judge_system hypothesis
- Fixing `_judge` order + `PYTHONHASHSEED=0` did not remove the divergence.
- The diverging field is `is_frozen`/`locked_times` (produced by `locker._locked_work`), which
  `_judge` never writes.
- The swap is between geometrically mirrored units -> a tie in a nearest-target / event-queue
  comparison, resolved by an order that varies run-to-run.

## Scope note (baseline risk)
Writing the nominal seed into the engine's `RW_SEED_FILE` changed W2-1's outcome (CER 0.1 -> 0.0) and
would invalidate the frozen ACE N=5 baseline (which was produced under the engine's fixed seed regime,
confirmed by W2-1 rows being byte-identical across 43001..43005). That seed change was **reverted** for
baseline comparability.

## Status
HALTED per the gate ("Otherwise STOP"). C7 logic itself is deterministic (pure function of legal state;
package selection sorts by (distance, id)). The residual is in the frozen engine/locker layer.
MD
echo "report updated"