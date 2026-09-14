# -*- coding: utf-8 -*-
"""auto_harness/phase0/code/failure_taxonomy.py — deterministic failure taxonomy (F1..F15)."""
TAXONOMY = {
 "F1_SEARCH_FAILURE": "target never effectively found within the key window",
 "F2_LATE_DETECTION": "found too late to act",
 "F3_LOST_TRACK": "track built then lost at a critical stage",
 "F4_REACQUIRE_FAILURE": "reacquire too slow / absent after loss",
 "F5_CAPACITY_HOLE": "dangerous target/cluster known with no effective interceptor",
 "F6_LATE_INTERCEPT": "interceptor exists but ETA/geometry too late",
 "F7_COMMITMENT_MISMATCH": "resources exist but committed elsewhere",
 "F8_KILL_CHAIN_FAILURE": "first-hit/frozen not finished in time, contributed to loss",
 "F9_ATTRITION_CASCADE": "key platform lost first, then capacity collapses",
 "F10_MULTI_AXIS_OVERLOAD": "simultaneous high-risk axes exceed capacity",
 "F11_UAV_COVERAGE_FAILURE": "UAV sensing/screen/battery formed critical blind period",
 "F12_BATTERY_HANDOFF_FAILURE": "key UAV return/low-battery broke sensing continuity",
 "F13_CONTROL_TIMING_FAILURE": "decision/apply/stale timing contributed",
 "F14_EXECUTION_FAILURE": "reasonable assignment not completed by controller",
 "F15_UNKNOWN": "cannot reliably classify",
}
