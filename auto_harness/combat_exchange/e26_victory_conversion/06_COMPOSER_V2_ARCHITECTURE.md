# 06 — UNIT-LEVEL COMPOSER (C30)
`agent_hybrid_split_screen.py` (`SplitScreenController`): per-unit assignment — ~1/3 of no-target USVs
(stable name-index) hold a defensive screen at `SCREEN_X` to guard the breakthrough line, the rest keep
pressing east; engaged/locking units untouched; universal safety (USV+UAV) applied to every action.
No scenario ID/seed. Result: combat **NO_EFFECT** vs C27 (identical K/L on all six), because the split-screen
units did not intercept the actual breachers. Composer V2's unit-level mechanism is implemented and
auditable, but did not convert any Defeat to Victory.
