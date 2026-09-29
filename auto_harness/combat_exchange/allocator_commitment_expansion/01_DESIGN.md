# 01 — Design: ALLOCATOR_COMMITMENT_EXPANSION (white-combat-0002-v1)

## 1. Why does W5 leave free USV + zero-owner target?
Root cause (f1_root_cause_audit): F1-A "free capacity not assigned" = 86% of uncommitted-target
steps. W5's ThreatAllocator already has a PASS1 "coverage floor" (assign 1 USV to each zero-owner
ship) and PASS2 marginal concentration, but it is throttled by a STATIC RESERVE (reserve_ratio=0.20)
that removes ~20% of free USVs from the assignable pool every step.

## 2. How does focus_level=2 limit commitment?
`focus_level` is "attackers per target" in the marginal-value model. It does NOT cap the NUMBER of
targets; the real cap on breadth is the RESERVE + the finite assignable pool (PASS1 uses all
assignable USVs to give each zero-owner ship 1 attacker).

## 3. How does reserve_ratio=0.20 limit commitment?
In `allocate_usvs`: `reserve = round(len(available) * reserve_ratio)`, then `available = available[:-reserve]`.
So ~20% of free USVs are never assigned, even when zero-owner visible targets exist.

## 4. Which decision point does C1 modify?
Only the reserve computation, via a pre-pass in `ExpandingAllocator.allocate_usvs`: if an
under-commitment condition holds, the reserve is released (reserve_usvs -> 0) before delegating to
the parent allocator. The parent's PASS1/PASS2 order and value model are unchanged.

## 5. Why breadth-first (0->1) over (2->3)?
Because the audit shows the dominant failure is zero-owner targets transiting unengaged (F1-A 86%),
not insufficient overmatch. W5 already does 0->1 before 2->3; C1 only removes the reserve throttle so
the existing 0->1 pass can actually run to completion.

## 6. When does dynamic reserve release trigger?
`_under_commitment(tracks, usvs, usv_map, now)` returns True when:
- there exists a FREE combat USV (alive, has position, `usv_map[name] is None`), AND
- there exists a visible (`t.is_visible(now)`), ship, non-killed target with zero owners
  (`len(t.assigned_usvs) == 0`).

## 7. When does it NOT release?
When no free USV exists, or every visible actionable target already has >= 1 owner. In that case the
original reserve semantics are fully preserved (reserve_ratio unchanged).

## 8. Does C1 modify Controller? NO.
## 9. Does C1 modify Detection? NO.
## 10. Does C1 read hidden truth? NO (only t.is_visible/is_ship/assigned_usvs + usv_map + own states).

## Fair-play / generalization
No strategy name, route, y-lane, enemy count, or black-ID hardcoding. Variable-cardinality (unit-test H
covers 3/5/10/15/20 friendly USVs). Uses only legal observation + TrackManager belief.
