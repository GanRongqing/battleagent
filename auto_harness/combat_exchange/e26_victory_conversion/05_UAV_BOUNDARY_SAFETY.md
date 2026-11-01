# 05 — UAV BOUNDARY SAFETY
Extended `universal_safety.BoundaryAwareSafety` to UAV `fly`: predicts next-step position; if it would
leave the area, rewrites the course toward the area centre. Inward RETURN/LANDING courses are untouched
(they don't predict outside), so high-priority states are not overridden. Applies after ActionSafety to all
`fly` actions (SEARCH/SCREEN/GLOBAL_SEARCH/REACQUIRE/loiter), not just one branch.
Verified (C30 six scenarios, engine `AREA_TRACE`): **UAV AREA_OUT 50 → 0**, USV AREA_OUT stays 0.
