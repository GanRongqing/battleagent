# 19 — BOTTLENECK MIGRATION
ACE dominant transition (input to C7): KNOWN/ASSIGNED -> OWN LOCK.
- W2-6: C7 moves it materially (ever-own-lock 11->15, hostile-locked-never-own-lock 8->5 per arm).
- W2-1: C7 has **no** effect (0 -> 0 own-lock) — the hardest case is not reachable by 2-unit packages
  (likely envelope/geometry, not coordination).
- Kills moved WITH locks on W2-6 (10->11 per episode), so the bottleneck did **not** migrate to
  KILL_CLOSURE there.
Residual dominant failure remains **OWN-LOCK CONVERSION** (W2-1), plus a **W2-4 coordination
perturbation** introduced by C7.
