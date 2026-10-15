# 02 — FAILURE EVIDENCE (from forensics)
W2-6 C10 raises own-lock units 11→15 and sustained 300 s windows 16→20 (ratio 0.556→0.688) but
**max concurrency stays 4** and 5/16 units still die before ever locking.
Engine: a unit dies when `locked_times` (=Σ completed incoming enemy locks that hit) reaches 2; a lock
must be held ≥300 s to hit (~80%); the first hit **freezes** the victim 300 s (cannot move/lock).
=> the exchange is limited by (a) concurrent sustained windows and (b) pre-lock attrition.
Root-cause verdict (w2_6_engagement_forensics/14): primary LOW_CONCURRENT_LOCK_CAPACITY, secondary
PRELOCK_ATTRITION.
