# 06 — ROOT CAUSE AND NEXT ACTION

## W2-5 real breacher: CONFIRMED = `usv4`
- Judge BREACH_TRACE (episode `e15_w25_c10`, trace ON, trajectory identical to E9): t=**39492 s**,
  position x=**49,995 m**, y=**+115,000 m** → **northern inner lane**.
- Route-1 usv4 (offline truth, diagnosis only): (360.4,195)→(272.8,145)@6 → (185.2,115)@10 → (10,115)@10.

## Earliest failure node: OBSERVATION (no positioned track). VERIFIED
- Over the whole episode usv4 had **0 active (radar-positioned) steps** and only **10 passive bearing alerts**
  (first 02:34:00). => `obs.active` never contained usv4 with a position.
- Consequently TrackManager never had a positioned track, ThreatAllocator never assigned it, and no
  own-lock/engagement was possible. This is upstream of allocation/controller/legality.
- At breach time the 6 surviving White USVs were clustered in the SOUTH (y −142…−73); the north lane
  (y=+115) was uncovered. Both the observation gap and the coverage gap are present, but the **binding**
  node is the absence of any positioned track for usv4.

## C12 check (bearing-guided reacquire) on W2-5: no help
- W2-5 C12 = **16/15, 2 breaches** (== ACE level; C10 = 27/14, 1 breach). Driving a USV along a passive
  bearing did **not** create a positioned track/lock in time. => bearing-steering alone is insufficient.

## Kill-count semantics (P4)
- `judge._judge` counts a breached unit as `black_killed` in the next dead-units pass (breach calls
  `unit.kill()` → `isactive=False`). So the reported **27 “kills” include the 1 breach** ⇒ **26 combat kills**
  (+1 breach). `out_of_bounds` removals are not separately logged (NOT_MEASURED).
- Clean Victory = Engine Victory AND breakthrough==0 → still **False**.

## Next highest-value repair (single)
Improve **early positioned detection of the northern-lane unit**: give a forward sensor asset (UAV) or a
screen USV a **north-lane search/orientation that produces a radar track before the final dash**, then let
the existing allocator/lock chain engage. Do NOT add another allocator/coordination candidate (C12/C14 both
failed to change the outcome). Before that, resolve the UAV loss path (E12: UNRESOLVED) because UAVs are the
forward sensor that would detect a passive-only unit at range.
