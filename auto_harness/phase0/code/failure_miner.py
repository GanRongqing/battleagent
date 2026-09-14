# -*- coding: utf-8 -*-
"""auto_harness/phase0/code/failure_miner.py — deterministic rule-based failure miner.

Consumes derived episode features + outcome; emits FailureAnalysis with taxonomy modes,
backward indicators, earliest-actionable estimate and confidence. Offline only; never runs W5.
"""
from failure_taxonomy import TAXONOMY


def analyze_episode(feat):
    """feat: dict from trace_derive.parse_episode_log. Returns analysis dict."""
    analysis = {"failure_events": [], "primary": "F15_UNKNOWN", "secondary": [],
                "earliest_actionable": None, "lead_time_s": None, "confidence": "LOW",
                "evidence": []}
    if feat["clean_win"]:
        return analysis
    modes = []
    evid = []
    # late detection / search
    fd = feat.get("first_detection")
    res = feat.get("resolution")
    if fd is not None and res is not None and fd > 0.6 * res:
        modes.append("F2_LATE_DETECTION"); evid.append("first_detection late")
    elif feat.get("detect_events", 0) < 10 and not feat["clean_win"]:
        modes.append("F1_SEARCH_FAILURE"); evid.append("low detect events")
    # lost / reacquire
    if feat.get("lost_track_runs", 0) >= 2 and feat.get("reacquire_success", 0) < \
            feat.get("reacquire_attempts", 0):
        modes.append("F3_LOST_TRACK")
        evid.append("lost-track runs present")
    if feat.get("reacquire_attempts", 0) > 0 and feat.get("reacquire_success", 0) == 0:
        modes.append("F4_REACQUIRE_FAILURE"); evid.append("reacquire attempts zero success")
    # capacity hole (visible but never engaged) proxy
    n = max(1, feat.get("step_samples", 1))
    if feat.get("capacity_hole_proxy_steps", 0) / n > 0.5:
        modes.append("F5_CAPACITY_HOLE"); evid.append("visible-not-engaged frequent")
    # attrition: many deaths
    deaths = feat.get("friendly_usv_loss", 0)
    if deaths >= 5 and feat.get("first_friendly_death_time") is not None and \
            feat.get("resolution") and feat.get("first_friendly_death_time") < 0.6 * feat["resolution"]:
        modes.append("F9_ATTRITION_CASCADE"); evid.append("early deaths>=5")
    # kill chain: many breaks etc not directly derivable -> rely on others
    if feat.get("breakthrough", 0) > 0 and not modes:
        modes.append("F6_LATE_INTERCEPT")
        evid.append("breakthrough with no earlier indicator captured")
    if not modes:
        modes.append("F15_UNKNOWN")
    analysis["failure_events"].append({"failure_type": "BREAKTHROUGH" if feat.get("breakthrough") else
                                       "DEFEAT"})
    analysis["secondary"] = modes[1:3]
    # earliest actionable heuristic: first_lock known or first_detection; else None
    ea = feat.get("first_lock") or feat.get("first_detection")
    if ea is not None and feat.get("resolution"):
        analysis["earliest_actionable"] = ea
        analysis["lead_time_s"] = round(feat["resolution"] - ea, 1)
    analysis["primary"] = modes[0]
    analysis["confidence"] = "HIGH" if (len(modes) == 1 and evid) else "MEDIUM" if evid else "LOW"
    analysis["evidence"] = evid
    return analysis
