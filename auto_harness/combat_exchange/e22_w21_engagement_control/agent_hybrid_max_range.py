#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""agent_hybrid_max_range.py — C23: MAX_RANGE_ENGAGEMENT.

Parent: C19 (agent_hybrid_press_search.py). Candidate: white-combat-0023-v1.

Evidence (E22 P0/C22): White USVs are frozen by Black and destroyed ~5 min after being frozen; freeze is
the Black lock. C22 showed standing off at 36.5 km still loses all 20 — the contested variable is the lock
race, not blobbing. White's own lock range is 40 km but engaged units keep a 34 km band, i.e. inside Black's
envelope. Keep C19's contact-gaining press (volume) but hold engaged units at the **outer edge of White's
own lock range** (39 km) so White locks as early as possible without reducing fleet volume.

Mechanism (ONE): engaged/locking standoff band raised to 39/37/40 km; no-target press unchanged (C19).
No scenario/route ID, no truth, no black-state read; lock range itself unchanged.
"""
import sys

from agent_hybrid_press_search import PressSearchAgentMain, PressSearchController

POLICY_ID = "white-combat-0023-v1"
PARENT = "C19(white-combat-0019-v1)"
MECHANISM = "MAX_RANGE_ENGAGEMENT"
BAND_MID, BAND_INNER, BAND_OUTER = 39_000.0, 37_000.0, 40_000.0


class MaxRangeController(PressSearchController):
    def _standoff_move(self, name, pos, tpos, band_mid, band_inner, band_outer):
        return super()._standoff_move(name, pos, tpos, BAND_MID, BAND_INNER, BAND_OUTER)


class MaxRangeAgentMain(PressSearchAgentMain):
    def __init__(self, use_uavs=True, max_steps=40000):
        super().__init__(use_uavs=use_uavs, max_steps=max_steps)
        self.usv_ctrl = MaxRangeController()


if __name__ == "__main__":
    use_uavs = True
    for a in sys.argv[1:]:
        if a == "--no-uav":
            use_uavs = False
    MaxRangeAgentMain(use_uavs=use_uavs).run()
