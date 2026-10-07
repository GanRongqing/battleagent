# 13 — CONTROL REGRESSION CHECK

Controls = W2-2, W2-4. C5 delta is a strict no-op when all assigned targets are FRESH (unit test 8),
so on control strategies (which detect well) C5 must be behaviourally identical to ACE except during
brief stale windows. Any control CER change is therefore bounded by the stale-window MOVE substitutions.
(Quantified from the C5 eval CSV once complete; see 09/10/12.)
