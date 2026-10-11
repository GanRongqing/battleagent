# 13 — FINAL REPORT: ZERO-LOCK + SEED INDEPENDENCE AUDIT

## Scope
Read-only audit (static + offline log parsing) + one RNG-plumbing fix + minimal same-seed replay.
ACE / C7 / Black / controllers / legality / sensors / weapons / routes unchanged. No C8.

## Seed
- Seed source: `adaptation._seed_rng()` reads `RW_SEED_FILE`.
- **Broken**: evaluation runners write `/tmp/opencode/seed_w0.txt`; the engine read
  `RW_SEED_FILE=/tmp/opencode/seed_det.txt` → nominal seeds never reached the engine.
- **Fix (separate, plumbing only)**: `svc.sh` `RW_SEED_FILE` -> `/tmp/opencode/seed_w0.txt`. No change to
  RNG distribution/probabilities/targeting/physics.
- Post-fix: same-seed 43001 x2 bit-identical; controlled engine-RNG test shows seeds 43001/43002/43003
  give distinct draw sequences. New epoch E2 required; E1 CSVs untouched.

## Zero-lock (W2-1), epoch E1, engine seed 11001
Funnel (20 White USVs): fresh contact **20**, in-range (≤40 km, agent proxy) **0**, lock request **0**,
accepted **0**, active own-lock **0**. Min White→positioned-enemy distance **123.4 km**; the only 4
positioned enemies appear for 2 log steps at 01:53 and vanish; 19 of the 23 enemies that lock White are
**passive-only** (bearing, no position).
Control W2-4 (ACE): fresh 19, in-range **17**, request **281**, accepted 281, active **14**, min 4.6 km.
Earliest divergence: **FRESH-CONTACT / in-range** transition.

## Evaluation independence (E1)
`11_EVALUATION_INDEPENDENCE_AUDIT.csv`: all 40 episodes share `ActualEngineSeed=11001` and identical
initial-state hashes; W2-1/W2-2/W2-6 have a single distinct trajectory across the 5 nominal seeds
(W2-4: 2 clusters — process-instance noise, not seed). The C7 "N=5" is effectively N≈1. **Nominal seeds
were not independent realizations.**

## Verdict
ZERO_LOCK_ROOT_CAUSE = **NO_FRESH_CONTACT** (dominant), secondary NO_LEGAL_LOCK_OPPORTUNITY.
Confidence: MEDIUM.
Use of old C7 N=5: PRE_SEED_FIX historical evidence only; seed-independent parts (W2-1 has no positional
contacts in range) remain valid; W2-6/W2-4 magnitudes must be re-measured in E2.
Next engineering action: run the C7/ACE panel in epoch E2 (seed actually wired); the W2-1 zero-lock is a
**sensing/geometry** problem (White never obtains a positioned in-range track), not a lock-controller bug.
