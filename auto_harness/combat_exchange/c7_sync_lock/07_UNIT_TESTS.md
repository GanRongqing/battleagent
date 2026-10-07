# 07 — UNIT TESTS
File: test_sync_lock.py  — **15/15 PASS** (>=14 required)
1 all-engaged no-op; 2 single-owner-no-lock -> 2-unit package; 3 support unavailable -> no package;
4 stealing an owner forbidden; 5 deterministic (lowest-id) selection; 6 lead-too-far -> shaped/slowed;
7 support caught up -> no shape; 8 own-lock established -> DISSOLVE; 9 target disappears -> DISSOLVE;
10 track expires -> DISSOLVE; 11 timeout -> DISSOLVE; 12 no permanent passivity (base actions kept);
12b lead never ordered to retreat; 13 no truth access; 14 no strategy/route ID logic.
Lock legality & fire legality untouched (no calls into legal/lock/fire; movement only).
