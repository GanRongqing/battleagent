# 04 — C28 ROUTER REGRESSION AUDIT (W2-2 Victory→Defeat)
C28 W2-2 `/result` reason = **我方所有单位被击毁** (all White destroyed) — NOT a breach. VERIFIED.
Mechanism (INFERRED, consistent with code): Composer V1 sets `has_threat = active>0`, then USV mode
CONTACT_MAINTENANCE reverts no-target USVs to the C10 screen, so when W2-2 has live tracks the fleet stops
pressing/engaging and is frozen/wiped (20 losses). This is the global-vs-unit-level defect E26 must fix.
