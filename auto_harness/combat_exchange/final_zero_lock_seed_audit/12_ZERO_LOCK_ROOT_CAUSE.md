# 12 — ZERO-LOCK ROOT CAUSE (W2-1)

## Answer to the Stage F questions
1. **Why own-lock = 0 in W2-1?** No White USV ever obtains a sustained positional contact inside lock
   range. Across the whole episode the 20 White USVs' minimum distance to any radar-positioned enemy is
   **123.4 km**. The only active (positioned) contacts (`usv14..usv17`) appear for **two log steps only**
   (`01:53:00`, `01:53:30`) and vanish. The controller therefore issues **0 lock requests**.
2. **Observation or legality?** Primarily **observation**: of the 23 enemies that lock White
   (`locked_attacker`), **19 are ONLY passively detected** (bearing, no position) → no fresh positional
   track → cannot be locked. The 4 enemies ever positioned were ~123 km away, well beyond the agent's
   40 km lock pre-filter (engine eligibility NOT_MEASURED).
3. **Did the controller request when legal?** No legal opportunity ever arose (0 units within 40 km), so
   the controller correctly issued **0 lock actions** — not a controller bug.
4. **Which layer rejected?** None: there were **0 requests → 0 rejections** (`10_ACTION_REJECTION_TRACE.csv` empty).
   The bottleneck is upstream of the controller (`_opportunistic_lock` needs a positioned track < LOCK_RANGE).
5. **Earliest divergence vs W2-4:** the **FRESH-CONTACT / in-range** transition. W2-1 min distance 123.4 km
   (0/20 in range); W2-4 min distance **4.6 km** (17/20 in range) → 281 requests → 14 active locks.
6. **Nominal seeds independent?** NO (see 01/11): all episodes used the fixed engine seed
   (`seed_det.txt`=11001); the 5 nominal seeds are not independent realizations.
7. **Use of the old C7 N=5 after the seed fix:** keep as PRE_SEED_FIX historical evidence only; the
   A/B/ZERO-lock findings that are **seed-independent** (W2-1 has no positional contacts in range under
   engine seed 11001) remain, but the W2-6/W2-4 numbers must be re-measured in the new epoch.

## Code locations
- Agent lock pre-filter: `agent_hybrid_v5.py::USVController._opportunistic_lock` and `step`
  (requires a track with position and distance < `LOCK_RANGE`). No request is emitted without it.
- Engine seed reader: `hsystem/sim_script/scenario/adaptation.py:162` (`RW_SEED_FILE`).
- Stochastic lock hit: `hsystem/simulation/arsenal/locker.py:106`.

## Verdict
ZERO_LOCK_ROOT_CAUSE = **NO_FRESH_CONTACT** (dominant: 19/23 attackers passive-only; the 4 positioned
contacts are 123 km out of range and 1-step transient). Secondary stage where it also fails:
NO_LEGAL_LOCK_OPPORTUNITY. Confidence: **MEDIUM**.
