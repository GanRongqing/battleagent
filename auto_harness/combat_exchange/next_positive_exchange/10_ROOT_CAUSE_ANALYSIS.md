# 10 — DETAILED ROOT-CAUSE ANALYSIS (E2 logs, seed 43001; ACE unless noted)

Method: offline parse of the simulator game logs only (legal runtime records; no truth).
Signals used: `usv_states{is_alive,is_locking,is_locked,locked_attacker,locked_times}`, per-step
`actions` (lock requests), `active_enemies` (radar-positioned), `passive_enemies` (bearing only),
`events` (deaths), `final_stats`; plus per-episode kills from `[META]`.

## 0. The kill rule (verified)
`locker.py`: a unit is destroyed when its own `locked_times` reaches 2 (two completed enemy locks).
Cross-check: the count of White USVs whose final `locked_times` = 2 equals White losses **exactly** for
every scenario:
| scenario | White units reaching locked_times=2 | White losses |
|---|---|---|
| W2-1 | 20 | 20 |
| W2-2 | 19 | 19 |
| W2-6 | 18 | 18 |
| W2-4 | 6 | 6 |
So White loss = number of White USVs that are locked twice by Black. The exchange is therefore governed by
how many White USVs Black can lock twice vs how many Black USVs White can lock twice.

## 1. Engagement funnel per scenario (seed 43001)
| scenario | units reaching ≤40km | own-lock units | in-range but never locked | White deaths | died BEFORE own-lock | max concurrent own-locks | total lock-seconds | White K / L |
|---|---|---|---|---|---|---|---|---|
| W2-1 | **0** | **0** | 0 | 20 | **20** | 0 | 0 | 0 / 20 |
| W2-2 | 7 | 7 | 0 | 19 | **13** | 6 | 104 | 4 / 19 |
| W2-6 (ACE) | 14 | 11 | 3 | 18 | **8** | 4 | 231 | 10 / 18 |
| W2-6 (C10) | 16 | 15 | 1 | 16 | **5** | 4 | 285 | 11 / 16 |
| W2-4 | 17 | 14 | 3 | 6 | **1** | **9** | 314 | 12 / 6 |

Two columns track the outcome almost monotonically: **died-before-own-lock** (W2-4 1 → W2-6 8 → W2-2 13
→ W2-1 20) and **max concurrent own-locks** (9 → 4 → 6 → 0). Conversion from in-range to own-lock is
already high (0.79–1.00), so the binding transition is NOT "in-range → lock"; it is **"reach range / stay
alive long enough to lock"**.

## 2. Where the defeated units die (cross-tab)
Of the White USVs that die before ever locking, how many had ever reached ≤40 km?
| scenario | died before own-lock | of which reached ≤40 km | never reached |
|---|---|---|---|
| W2-2 | 13 | 0 | 13 (closest approach 67–172 km; 3 had no radar contact at all) |
| W2-6 ACE | 8 | 2 | 6 (closest 42–126 km) |
| W2-6 C10 | 5 | 1 | 4 (closest 41.5–61.6 km) |
| W2-4 | 1 | 0 | 1 |
=> The defeated units are killed while still **outside their own lock envelope** (or with no positional
contact at all). White is hit before/without being able to close and lock.

## 3. Killer visibility (positioned vs passive-only)
| scenario | distinct Black ever radar-positioned | distinct Black passive-only | White deaths with a POSITIONED killer | with ONLY passive killers |
|---|---|---|---|---|
| W2-1 | **4** | 23 | 10 | **10** |
| W2-2 | **3** | 30 | 10 | **9** |
| W2-6 | 11 | 19 | 17 | 1 |
| W2-4 | 10 | 10 | 6 | 0 |
=> Two distinct root-cause classes:
- **W2-1 / W2-2 = OBSERVATION-LIMITED**: only 3–4 of 30 Black are ever positioned; White fights blind
  (W2-1 0/20 in range, W2-2 7/20), and ~half of deaths come from Black that were never positioned.
- **W2-6 = RANGE/TIMING-LIMITED**: White *does* position Black (11/30) and 17/18 deaths involve a
  positioned killer — White sees the enemy but cannot close to its 40 km lock range before Black lands
  two hits (6/8 die-before-own units never got within 40 km).
- **W2-4 = healthy**: 10 positioned, 17 reach, 14 lock, 9 concurrent → White wins the exchange 12/6.

## 4. The discriminator (win vs lose)
White wins W2-4 with 14 own-lock units; White loses W2-6 with 11 (ACE). The difference is not the count so
much as **overlap and timing**: W2-4 reaches **9 concurrent** locks with only **1** unit dying before it
locks; W2-6 never exceeds **4 concurrent** locks and **8** units die before locking. The number of locks
held simultaneously (≈ hit throughput, since a completed lock takes ≥300 s) is the direct driver of kills.

## 5. What C10 actually changed (W2-6)
C10 (budgeted 2-unit synchronized packages) raised in-range units 14→16 and own-lock units 11→15,
reduced died-before-own-lock 8→5 and deaths 18→16 → K/L 10/18 → 11/16 (ratio 0.556→0.688, +24%).
But **max concurrent own-locks stayed 4** and total lock-seconds only 231→285 (vs W2-4's 314/9). So the
coordination mechanism improves how many units *eventually* lock, but not the **simultaneous** lock
throughput needed to out-kill Black, and it does not stop the early un-locked deaths.

## 6. Root cause (stated precisely)
The negative exchange is produced by a single dominant chain:

```
Black locks White from beyond White's lock range (or from a passive-only bearing)
   -> White USV accumulates locked_times = 2 and dies
   -> over half the force dies BEFORE it ever establishes its own lock
   -> the few surviving lockers never overlap enough (max conc 4) to out-kill Black
```

- W2-1: extreme — 0 positional in-range contact (observation failure). 20/20 die un-locked.
- W2-2: severe — 3 positioned Black only; 13/19 die un-locked (observation failure).
- W2-6: moderate — White sees the enemy but dies during closure; 8/18 die un-locked (range/timing
  failure).
- W2-4: control — nearly all White lock before dying (1 un-locked death); 9 concurrent locks → win.

## 7. Consequence for the next mechanism
Coordination (C7/C10) only partially addresses "eventually lock more units". To move W2-6 above 1.0 the
lever is **survival + faster/simultaneous closure** (get more White USVs into their own lock envelope
*before* Black's two hits land), and for W2-1/W2-2 the lever is the **upstream observation gap**
(bearing -> positioned track / sensor coverage). Neither is a coordination-count problem.

## Caveat
Single seed (43001) forensic; E2 shows per-scenario rows are near-identical across seeds, so the shape is
representative. Engine lock/weapon ranges are NOT_MEASURED (Cython), so "range asymmetry" is inferred
from distances, not from engine constants.
