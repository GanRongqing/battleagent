# 01 — TRACK-ONLY CONTROL
`TrackOnlyAgentMain` = C10 + `PassiveHistoryManager`, with the **unchanged** C10 UAVManager and USVController.
Purpose: isolate the passive data fix from any action change. Because bearing-only tracks never drive
allocation/lock/UAV scheduling, Track-Only must be behaviour-identical to C10 (trajectory hash check in 06).
