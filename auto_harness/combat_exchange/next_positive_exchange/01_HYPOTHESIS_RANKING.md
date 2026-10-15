# 01 — CANDIDATE HYPOTHESIS RANKING (W2-6 focus, E2 evidence)

Observable fields available online (agent obs): `is_locked`, `locked_attacker`, `is_locking`,
positions, tracks (`has_position`,`is_visible`), assignment (`self.targets`). Simulator legal-lock
opportunity is NOT_MEASURED. No truth.

| rank | hypothesis | online fields | trigger space | decision changed | interferes with ACE? | truth? | cost | verdict |
|---|---|---|---|---|---|---|---|---|
| **1** | **H1 Demand-gated coordination**: allow the C7 package only when the target's owner is under hostile lock | `is_locked`/`locked_attacker` | W2-6 high (40 hostile-lock units/5ep), W2-4 low (8) | yes (package FORM) | low (suppresses W2-4 packages) | no | low | **IMPLEMENT (C9)** |
| 2 | H2 No support diversion; only lead TTFL slowdown | positions/tracks | all packages | yes (movement) | medium | no | low | hold |
| 3 | H3 Global package budget (cap #active packages) | internal | capacity | yes (FORM) | medium | no | low | hold |
| 4 | H4 Skip if target already "handled" (owner closing, high speed) | speed/pos | needs derived observable | yes | medium | no | med | NEED INSTRUMENTATION |
| 5 | H5 Bearing-guided localization (W2-1) | passive bearings | W2-1 | yes | n/a | no | high | out of scope (W2-1) |

## Why H1
E2: W2-4 White units are **almost never hostile-locked without own-lock** (Σ=8 across 5 eps) yet C7
formed ~15 packages/ep there and regressed a 5/5 win to 3/5; W2-6 has Σ=40 hostile-lock units and C7
formed ~2 packages/ep that helped (own-lock 11→15). The single observable that separates the two
regimes is `is_locked`/`locked_attacker` on the owner → a legal local "task demand" gate.

## Falsification
H1 is falsified if on W2-6 the gate suppresses the helpful packages (hostile-lock not present at those
FORMs), or if W2-4 still regresses (gate too permissive), or if the gate changes nothing (packages were
already on hostile-locked owners).
