# -*- coding: utf-8 -*-
"""auto_harness/phase0/code/trace_derive.py — offline feature derivation from a W5 episode log.

READ-ONLY: parses the game log only. Never runs the agent. All derived fields are stored with
offline_only semantics where they rely on post-hoc reasoning.
"""
import re
import statistics


def parse_episode_log(path):
    events = {"assign": [], "release": [], "detect": [], "kills": []}
    steps = []     # (sim_t, usv_alive, usv_total, lock, int, vis, lost, engaged, kill)
    usv_dead_times = []
    prev_alive = None
    sim_end = 0.0
    meta = {}
    last_top = []
    for line in open(path, encoding="utf-8", errors="replace"):
        if "[META]" in line:
            for k in ("result", "victory_time", "first_detection", "first_lock", "first_kill",
                      "enemy_kills", "friendly_usv_losses", "black_breakthrough",
                      "reacquire_attempts", "reacquire_success"):
                m = re.search(rf"\b{k}=(\S+)", line)
                if m:
                    try:
                        meta[k] = float(m.group(1)) if k not in ("result",) else m.group(1)
                    except Exception:
                        meta[k] = m.group(1)
            sim_end = meta.get("victory_time", sim_end)
            continue
        m = re.search(r"\[t=([\d,]+)s\] step=(\d+) \|.*?USV: (\d+)/(\d+) \(avail=(\d+) int=(\d+)"
                      r" lock=(\d+).*?TRACKS: vis=(\d+) lost=(\d+) engaged=(\d+).*?KILL=(\d+)", line)
        if m:
            t = int(m.group(1).replace(",", "")); alive = int(m.group(3)); total = int(m.group(4))
            vis, lost, eng = int(m.group(8)), int(m.group(9)), int(m.group(10))
            kill = int(m.group(11))
            steps.append((t, alive, total, int(m.group(6)), int(m.group(7)), vis, lost, eng, kill))
            if prev_alive is not None and alive < prev_alive:
                usv_dead_times.append(t)
            prev_alive = alive
            sim_end = t
            continue
        if "[DETECT]" in line:
            events["detect"].append(1)
        elif "[ASSIGN]" in line:
            events["assign"].append(1)
        elif "[RELEASE]" in line:
            events["release"].append(1)
    # derived features
    if meta.get("result") == "Result.Defeat":
        outcome = "DEFEAT"
    elif meta.get("black_breakthrough", 0) > 0:
        outcome = "BREAKTHROUGH_WIN"
    else:
        outcome = "CLEAN_WIN"
    lost_runs = 0
    in_run = False
    for s in steps:
        if s[6] > 0 and not in_run:
            lost_runs += 1
            in_run = True
        elif s[6] == 0:
            in_run = False
    # zero-engaged-with-visible proxy duration (capacity hole proxy)
    zero_hole = 0
    for s in steps:
        if s[5] > 0 and s[7] == 0:   # visible ships but nobody locking -> no engagement
            zero_hole += 1
    first_dead = usv_dead_times[0] if usv_dead_times else None
    feats = {
        "outcome": outcome, "sim_end": sim_end,
        "clean_win": int(outcome == "CLEAN_WIN"),
        "breakthrough": int(meta.get("black_breakthrough", 0) or 0),
        "friendly_usv_loss": int(meta.get("friendly_usv_losses", 0) or 0),
        "enemy_kills": int(meta.get("enemy_kills", 0) or 0),
        "first_detection": meta.get("first_detection"),
        "first_lock": meta.get("first_lock"),
        "first_kill": meta.get("first_kill"),
        "resolution": meta.get("victory_time"),
        "reacquire_attempts": int(meta.get("reacquire_attempts", 0) or 0),
        "reacquire_success": int(meta.get("reacquire_success", 0) or 0),
        "first_friendly_death_time": first_dead,
        "usv_dead_times": usv_dead_times,
        "lost_track_runs": lost_runs,
        "capacity_hole_proxy_steps": zero_hole,
        "step_samples": len(steps),
        "detect_events": len(events["detect"]),
        "assign_events": len(events["assign"]),
    }
    return feats
