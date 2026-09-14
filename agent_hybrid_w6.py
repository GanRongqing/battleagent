#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""agent_hybrid_w6.py — W6 Anti-Evasion / Predictive-Interception Harness.

Subclasses agent_hybrid_v5.AgentMain. W6_ANTI_EVASION=0 (default) -> exactly the frozen
V5 path. W6_ANTI_EVASION=1 -> the base V5 controllers/allocator run UNCHANGED, with W6
inputs injected at the decision seams:

  - allocator output            -> W6 pursuit-cost-aware allocation (+ handoff)
  - target intercept aim        -> W6 predicted-corridor point (shadowing the track
                                   prediction the controller consumes)
  - defensive screen            -> W6 keeps a resource-relative screen reserve
  - UAV track maintenance       -> W6 seeds the base reacquire/screen with
                                   high-criticality tracks
  - breakthrough horizon risk   -> feeds threat urgency into the W6 allocation

Skill / prompt / simulator physics / opponent policy untouched. No opponent-profile,
fleet-size, seed, or hidden-truth dependence.
"""
import os
import re
import sys
import math

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import agent_hybrid_v5 as a5                   # noqa: E402
from anti_evasion import config as wcfg        # noqa: E402
from anti_evasion.w6_harness import W6DecisionCore   # noqa: E402
from anti_evasion.metrics import get_global_metrics  # noqa: E402


def _uav_home(name):
    m = re.search(r"(\d+)$", name)
    return f"white_usv{m.group(1)}" if m else "white_usv1"


class W6Agent(a5.AgentMain):
    def __init__(self, use_uavs=True, max_steps=40000):
        super().__init__(use_uavs=use_uavs, max_steps=max_steps)
        self.w6 = W6DecisionCore()

    # ── W6 decision step; delegates to W5 exactly when disabled ──
    def step_once(self):
        if not wcfg.W6_ENABLED:
            return super().step_once()

        st = self.client.status()
        if not isinstance(st, dict):
            return False
        now = a5.parse_sim_time(st.get("局内时间", "00:00:00"))
        obs = a5.Obs(st, now)
        legal_raw = self.client.legal_actions()
        legal = a5.LegalSet(legal_raw) if isinstance(legal_raw, dict) else a5.LegalSet({})

        events = self.tracker.update(obs)
        self.tracker.reconcile_assigned(obs, self.usv_ctrl.targets)
        kill_evs, killed = self.tracker.kill_detect(obs, self.prev_black_killed)
        events += kill_evs
        a5._KILLED.update(killed)
        self.prev_black_killed = obs.black_killed

        self.mission = self._compute_mission(obs)
        self._update_mission_metrics()
        self._update_coverage_from_usvs(obs)

        self.intent = self.commander.get_intent()
        # baseline frozen marginal allocation
        base_alloc = self.allocator.allocate_usvs(
            dict(self.tracker.tracks), obs.usvs, self.usv_ctrl.targets, now,
            intent=self.intent, return_margin=False)

        usv_positions = {u["name"]: tuple(u["position"][:2])
                         for u in obs.usvs if u.get("is_alive") and u.get("position")}
        usv_states = {u["name"]: {"is_locking": u.get("is_locking"),
                                  "locking_unit": u.get("locking_unit"),
                                  "locked_since": None}
                      for u in obs.usvs}

        # W6 decision core (dev2: full step incl. its allocation; dev3/iso/predonly:
        # features only — the allocation is produced by allocator_centric below)
        current_commitments = {t: u for u, t in self.usv_ctrl.targets.items()}
        if wcfg.EXECUTION_OVERRIDE:
            d = self.w6.step(self.tracker.tracks, obs.usvs, now, base_alloc,
                             usv_positions, usv_states,
                             current_commitments=current_commitments)
        else:
            d = self.w6.features(self.tracker.tracks, obs.usvs, now,
                                 usv_positions, usv_states)
        corridors = d["corridors"]; plans = d["intercept_plans"]; risks = d["risks"]

        # ── W6-dev3: allocator-centric mode ──
        # WHO/WHAT/TARGET comes from the W6 allocator overlay over the frozen W5 allocator;
        # HOW (navigation/standoff/lock/engage) is ALWAYS the legacy USVController. When the
        # execution-override flag is off (dev3 / prediction_only) we never write a predictive
        # waypoint (_w6_intercept) and never rewrite a controller move.
        if wcfg.EXECUTION_OVERRIDE:
            alloc = d["allocation"] or base_alloc
        elif wcfg.SHADOW_ONLY:
            alloc = base_alloc          # REAL policy frozen to W5; shadow logged only
        elif wcfg.DEV4:
            alloc = self._dev4_allocate(base_alloc, obs, now, corridors, plans, risks)
        else:
            alloc = self.w6.allocator_centric(
                base_alloc, self.tracker.tracks, usv_positions, usv_states, now,
                corridors, plans, risks, current_commitments=current_commitments) \
                or base_alloc
        if wcfg.SHADOW_ONLY:
            try:
                self._shadow_log(obs, now, base_alloc, corridors, plans, risks)
            except Exception:
                pass

        # knife-fight / standoff geometry metrics (legacy standoff semantics ~ LOCK_RANGE*0.85)
        if wcfg.feature_on("predictive_intercept"):
            unsafe_band = a5.LOCK_RANGE * 0.85
            m = get_global_metrics()
            for target, usvs in alloc.items():
                t = self.tracker.tracks.get(target)
                if t is None:
                    continue
                tpos = t.predicted_position(now)
                for uname in usvs:
                    u = next((x for x in obs.usvs if x.get("name") == uname), None)
                    if not u or not u.get("position") or not tpos:
                        continue
                    dist = math.hypot(tpos[0] - u["position"][0], tpos[1] - u["position"][1])
                    cur_min = m.counts.get("min_target_distance_during_pursuit")
                    if cur_min is None or dist < cur_min:
                        m.counts["min_target_distance_during_pursuit"] = dist
                    if dist < unsafe_band:
                        m.inc("unsafe_close_entries")
                        m.inc("unsafe_close_duration_steps")
                plan = plans.get(target)
                if plan is not None and plan.geometry_state == "REPOSITION_OUTWARD":
                    m.inc("reposition_outward_count")

        # decision-neutral allocator state logger (env W6_ALLOC_LOG=1)
        if os.getenv("W6_ALLOC_LOG", "0") == "1":
            try:
                self._log_alloc_state(obs, now, base_alloc, alloc, corridors)
            except Exception:
                pass

        # predictive intercept waypoint override — EXECUTION-OVERRIDE mode ONLY (dev2)
        if wcfg.feature_on("predictive_intercept") and wcfg.EXECUTION_OVERRIDE:
            for t in self.tracker.tracks.values():
                t._w6_intercept = None
            for target, usvs in alloc.items():
                corr = corridors.get(target)
                plan = plans.get(target)
                t = self.tracker.tracks.get(target)
                if t is None:
                    continue
                aim = plan.intercept_point if plan is not None else \
                    (corr.predicted_position if corr is not None else None)
                if aim is not None:
                    t._w6_intercept = tuple(aim)
                    get_global_metrics().inc("w6_execution_override_actions")

        # base controllers run unchanged with the (W6 or base) allocation
        usv_acts = self.usv_ctrl.step(obs, self.tracker.tracks, legal, alloc, events,
                                      intent=self.intent, mission=self.mission)
        try:
            mtr = get_global_metrics()
            new_map = {}
            for tgt, usvs in alloc.items():
                for u in usvs:
                    new_map[u] = tgt
            alive = {u["name"] for u in obs.usvs if u.get("is_alive")}
            if not hasattr(self, "_assign_start"):
                self._assign_start = {}
            for u, tgt in new_map.items():
                if u not in alive:
                    continue
                prev = getattr(self, "_prev_assign", {}).get(u)
                if prev is not None and prev != tgt:
                    mtr.inc("assignment_change_count")
                    st = self._assign_start.get(u)
                    if st is not None:
                        mtr.counts["assignment_lifetime_sum"] += (now - st)
                        mtr.counts["assignment_lifetime_n"] += 1
                    self._assign_start[u] = now
                elif u not in self._assign_start:
                    self._assign_start[u] = now
            for u in list(self._assign_start):
                if u not in alive:
                    self._assign_start.pop(u, None)
            self._prev_assign = new_map
        except Exception:
            pass

        # adaptive screen PHYSICAL move deploy — EXECUTION-OVERRIDE mode ONLY (dev2)
        # (dev3 / prediction_only: AdaptiveScreenPlanner is a resource-demand estimator only;
        #  it never emits a platform move here — reserve stays allocator-level.)
        if wcfg.feature_on("adaptive_screen") and wcfg.EXECUTION_OVERRIDE:
            sp = d.get("screen")
            if sp is not None and sp.screen_positions and sp.min_capacity > 0:
                m = get_global_metrics()
                committed = {u for us in alloc.values() for u in us}
                slots = list(sp.screen_positions)
                used = 0
                for u in obs.usvs:
                    if used >= sp.min_capacity or not slots:
                        break
                    name = u.get("name")
                    if not u.get("is_alive") or u.get("is_locking"):
                        continue
                    if name in committed or self.usv_ctrl.targets.get(name) is not None:
                        continue
                    pos = u.get("position")
                    if not pos:
                        continue
                    bp = (pos[0], pos[1])
                    target_sp = min(slots, key=lambda s: (s[0] - bp[0]) ** 2 + (s[1] - bp[1]) ** 2)
                    for i, act in enumerate(usv_acts):
                        if isinstance(act, tuple) and len(act) == 2 and act[1] == "move" \
                                and act[0].startswith(name + " 移动"):
                            usv_acts[i] = self.usv_ctrl._move(name, bp, target_sp)
                            used += 1
                            m.inc("screen_assignments")
                            m.inc("w6_execution_override_actions")
                            break

        # UAV track maintenance: seed the base reacquire with high-criticality tracks
        # (isolation: disabled unless the track_maint component is explicitly enabled)
        if wcfg.feature_on("uav_track_maintenance") and d.get("criticalities") \
                and not (wcfg.ISO_MODE and not wcfg.ISO_TRACK_MAINT):
            ordered = sorted(self.tracker.tracks.items(),
                             key=lambda kv: -d["criticalities"].get(kv[0], 0.0))
            for name, t in ordered:
                if d["criticalities"].get(name, 0.0) >= 0.6 and \
                        not t.is_visible(now) and t.has_position:
                    uavs_alive = [u["name"] for u in obs.uavs if u.get("is_alive")]
                    if uavs_alive:
                        self.uav_mgr.reacquire_lock[name] = uavs_alive[0]
                        get_global_metrics().inc("track_maintenance_assignments")
                    break
        uav_acts = self.uav_mgr.step(obs, self.tracker, legal, events,
                                     intent=self.intent,
                                     threat_fn=lambda t, n: self.allocator.threat_score(t, n),
                                     coverage=self.coverage, mission=self.mission)
        self._emit_events(events)
        self._dev4_log_trail(obs, now)

        self._record_stats(obs, events)
        self.resource = a5.FriendlyResourceState.build(obs, self.usv_ctrl, self.uav_mgr,
                                                       self.tracker, self.coverage, now)
        self._prev_visible = obs.enemy_visible
        self._prev_usv_alive = obs.usv_alive

        safe = self.safety.filter(usv_acts + uav_acts, obs, legal)
        if not safe:
            safe = [{"action_text": "空操作，等待一个宏观步 [noop]", "action_type": "noop"}]
        resp = self.client.apply(safe)
        self._maybe_log(obs, alloc, safe, resp)
        return not obs.ended

    def _log_alloc_state(self, obs, now, base_alloc, alloc, corridors):
        """READ-ONLY allocator-decision snapshot (never affects decisions). Writes one JSON
        line per allocator decision point so an offline replay can recompute W5/W6/iso
        allocators on identical legal input. Only legal belief is stored (no hidden truth)."""
        import json as _json
        path = os.getenv("ALLOC_STATES_PATH", "/tmp/opencode/allocator_states.jsonl")
        it = vars(self.intent) if hasattr(self.intent, "__dict__") else {}
        intent = {k: v for k, v in it.items()
                  if k in ("focus_level", "emergency_focus_level", "engagement_aggressiveness",
                           "reserve_usvs", "reserve_ratio", "threat_bias", "priority_tracks",
                           "overmatch_policy", "uncertainty_tolerance") and not callable(v)}
        usvs = [{"name": u.get("name"), "position": u.get("position"),
                 "alive": bool(u.get("is_alive")), "is_locking": bool(u.get("is_locking")),
                 "is_frozen": bool(u.get("is_frozen")),
                 "locking_unit": u.get("locking_unit"),
                 "battery": u.get("battery")}
                for u in obs.usvs]
        tracks = {}
        for name, t in self.tracker.tracks.items():
            tracks[name] = {"name": t.name, "position": list(t.last_position) if t.last_position else None,
                            "velocity": list(t.last_velocity) if t.last_velocity else None,
                            "last_seen": t.last_seen_time, "confidence": t.confidence,
                            "has_position": bool(t.has_position),
                            "heading": t.heading, "turn_events": t.turn_events,
                            "maneuver_score": t.maneuver_score, "point_confidence": t.point_confidence,
                            "uncertainty_radius": t.uncertainty_radius,
                            "pred_errors": list(t.pred_errors)[-10:],
                            "is_ship": bool(t.is_ship),
                            "assigned_usvs": sorted(t.assigned_usvs),
                            "engaged": bool(t.engaged)}
        usv_map = {u: (t if t is not None else None) for u, t in self.usv_ctrl.targets.items()}
        rec = {"episode": os.getenv("RUN_TAG", "?"), "scenario": os.getenv("SCENARIO_SCRIPT", "?"),
               "seed": os.getenv("RUN_SEED", "?"), "sim_time": round(float(now), 1),
               "decision_index": self.step, "mission": self.mission,
               "friendly_usvs": usvs,
               "usv_alive": obs.usv_alive, "uav_alive": obs.uav_alive,
               "enemy_visible": obs.enemy_visible,
               "usv_map": {k: v for k, v in usv_map.items()},
               "tracks": tracks, "intent": intent,
               "base_alloc": {t: sorted(u) for t, u in base_alloc.items()},
               "alloc": {t: sorted(u) for t, u in alloc.items()}}
        with open(path, "a", encoding="utf-8") as f:
            f.write(_json.dumps(rec) + "\n")

    def _dev4_allocate(self, base_alloc, obs, now, corridors, plans, risks):
        """W6-dev4 decision-space redesign: commitment pools + elastic reallocation.

        WHO/TASK/TARGET only. HARD (locking/frozen) platforms are never touched. SOFT moves
        are owner changes via self.usv_ctrl.targets (legacy controller steers HOW next step).
        Returns alloc (target->[usv]) for free-pool additions.
        """
        from anti_evasion.commitment import classify_all
        from anti_evasion.elastic_reserve import ElasticReserveManager
        from anti_evasion.releasable_pool import build_releasable_pool
        alloc = {t: list(u) for t, u in base_alloc.items()}
        target_map = {u: (t or None) for u, t in self.usv_ctrl.targets.items()}
        cls = classify_all(obs.usvs, target_map)
        alive = {u["name"] for u in obs.usvs if u.get("is_alive")}
        # imminent / uncovered sets from legal risk belief
        imminent, uncovered = set(), set()
        for name, r in (risks or {}).items():
            b = getattr(r, "breakthrough_eta", None)
            if b is None or b == float("inf") or b <= 0:
                continue
            too_late = r.interceptor_deficit is not None and r.interceptor_deficit < 0
            if (r.risk_score >= wcfg.BRK_RISK_HIGH) or too_late:
                imminent.add(name)
                p = plans.get(name)
                if too_late or p is None or not p.intercept_feasible:
                    uncovered.add(name)
        free_platforms = [p for p, c in cls.items() if c == "FREE" and p in alive]
        free_others = [p for p in free_platforms]
        # elastic reserve: hold some free back only when uncovered high-risk demand exists
        rm = getattr(self, "_dev4_reserve", None)
        if rm is None:
            rm = self._dev4_reserve = ElasticReserveManager()
        n_imminent = len(imminent)
        keep_res, released, added = rm.update(
            free_others, len(alive), n_imminent,
            n_uncovered_feasible=1 if uncovered else 0)
        if released:
            get_global_metrics().inc("dev4_reserve_release_events")
        if added and n_imminent:
            get_global_metrics().inc("dev4_reserve_create_events")
        # releasable candidate pool: free-not-reserved + eligible SOFT
        free_pool = [p for p in free_others if p not in keep_res]
        if free_pool:
            m4 = get_global_metrics()
            m4.counts["dev4_free_pool_sum"] += len(free_pool)
            m4.counts["dev4_free_pool_n"] += 1
        pool, pool_reasons = build_releasable_pool(cls, target_map, alloc, risks, now)
        # note: SOFT members already carry target; add them as candidate list (free only usable
        # for alloc additions; soft for owner-change). We reassign at most one per step.
        for u in sorted(pool, key=lambda x: (x not in free_pool)):
            if u not in alive or u in keep_res:
                continue
            if len(pool_reasons.get(u, [])) or u in free_pool:
                pass
        # ── dev4.2: coverage-safe imminent reinforcement (capacity deficit + deadline) ──
        dev42_best = None
        if wcfg.DEV4_2:
            # per-corridor need from reused breakthrough-risk semantics
            def _risk_obj(C):
                return (risks or {}).get(C)
            def _in_time(C):
                """count committed interceptors (incl. locking) that can meet the deadline."""
                b = getattr(_risk_obj(C), "breakthrough_eta", None)
                if b is None or b == float("inf") or b <= 0:
                    return 0
                cnt = 0
                for nm in (base_alloc.get(C) or []):
                    if cls.get(nm) == "HARD_COMMITTED":
                        cnt += 1
                        continue
                    pp = next((x for x in obs.usvs if x.get("name") == nm and x.get("position")), None)
                    if not pp:
                        continue
                    pn = self.w6.planner.plan(nm, tuple(pp["position"][:2]), corridors.get(C))
                    if pn is not None and pn.intercept_eta * (1 + wcfg.SCREEN_ETA_SAFETY) <= b:
                        cnt += 1
                return cnt
            need_corridors = {}
            for C in imminent:
                b = getattr(_risk_obj(C), "breakthrough_eta", None)
                if b is None or b == float("inf") or b <= 0:
                    continue
                risk = getattr(_risk_obj(C), "risk_score", 0.0)
                if risk < wcfg.BRK_RISK_HIGH:
                    continue
                req = (wcfg.REQUIRED_IN_TIME_CRITICAL if risk >= wcfg.CRITICAL_RISK
                       else wcfg.REQUIRED_IN_TIME_HIGH)
                cap = _in_time(C)
                if cap < req and len(base_alloc.get(C, [])) < wcfg.EMERGENCY_CONCENTRATION:
                    need_corridors[C] = (risk, req - cap)
            # candidate FREE platforms that can meet a need corridor's deadline
            cands = []
            for u in free_pool:
                if cls.get(u) != "FREE" or u not in alive or u in keep_res:
                    continue
                up = next((x for x in obs.usvs if x.get("name") == u and x.get("position")), None)
                if not up:
                    continue
                pos = tuple(up["position"][:2])
                for C, (risk, deficit) in need_corridors.items():
                    if C == target_map.get(u) or C not in corridors:
                        continue
                    pn = self.w6.planner.plan(u, pos, corridors.get(C))
                    if pn is None:
                        continue
                    b = getattr(_risk_obj(C), "breakthrough_eta", float("inf"))
                    if pn.intercept_eta * (1 + wcfg.SCREEN_ETA_SAFETY) > b:
                        continue                        # DEADLINE_INFEASIBLE
                    # coverage safety: would C2 (need corridor) lose its only in-time candidate?
                    unsafe = False
                    for C2, (r2, d2) in need_corridors.items():
                        if C2 == C:
                            continue
                        has_other = False
                        for nm in [x for x in free_pool if x != u] + \
                                [x for x in base_alloc.get(C2, []) if cls.get(x) != "HARD_COMMITTED"]:
                            pp2 = next((z for z in obs.usvs if z.get("name") == nm and z.get("position")), None)
                            if not pp2:
                                continue
                            pn2 = self.w6.planner.plan(nm, tuple(pp2["position"][:2]), corridors.get(C2))
                            if pn2 is not None and \
                                    pn2.intercept_eta * (1 + wcfg.SCREEN_ETA_SAFETY) <= \
                                    getattr(_risk_obj(C2), "breakthrough_eta", float("inf")):
                                has_other = True
                                break
                        if not has_other:
                            unsafe = True
                            break
                    if unsafe:
                        continue                        # COVERAGE_UNSAFE
                    if len(base_alloc.get(C, [])) >= wcfg.EMERGENCY_CONCENTRATION:
                        continue
                    cands.append((risk, deficit, pn.intercept_eta, u, C))
            if cands:
                cands.sort(key=lambda x: (-x[0], x[2]))   # highest risk, then fastest
                _risk, _def, _e, u, C = cands[0]
                dev42_best = (float("-inf"), u, C, target_map.get(u),
                              "FREE_TO_IMMINENT_CAPACITY_DEFICIT")
        if dev42_best is not None:
            _r, u, dest, cur, reason = dev42_best
            alloc.setdefault(dest, []).append(u)
            get_global_metrics().inc("dev4_realloc_events")
            get_global_metrics().inc("dev4_capacity_reinforce_events")
            self._dev4_log_event("REALLOC_FREE", u, cur, dest, reason, target_map, now,
                                 corridors, obs, cls, keep_res)
            return alloc
        # ── dev4.1: relaxed FREE -> imminent HIGH-risk corridor trigger ──
        dev41_best = None
        if wcfg.DEV4_1:
            def _ref_eta(C):
                best = None
                for nm in (base_alloc.get(C) or []):
                    pp = next((x for x in obs.usvs if x.get("name") == nm and x.get("position")), None)
                    if not pp:
                        continue
                    pn = self.w6.planner.plan(nm, tuple(pp["position"][:2]), corridors.get(C))
                    if pn is not None and (best is None or pn.intercept_eta < best):
                        best = pn.intercept_eta
                return best
            for u in free_pool:
                if cls.get(u) != "FREE" or u not in alive or u in keep_res:
                    continue
                up = next((x for x in obs.usvs if x.get("name") == u and x.get("position")), None)
                if not up:
                    continue
                pos = tuple(up["position"][:2])
                for C in imminent:
                    if C not in corridors or C == target_map.get(u):
                        continue
                    conc = len(base_alloc.get(C, []))
                    if conc >= wcfg.EMERGENCY_CONCENTRATION:
                        continue
                    ref = _ref_eta(C)
                    if ref is None or ref <= 0:
                        continue                    # invalid ref: deterministic no-trigger
                    pn = self.w6.planner.plan(u, pos, corridors.get(C))
                    if pn is None:
                        continue
                    ratio = pn.intercept_eta / ref
                    if ratio <= wcfg.FREE_TO_IMMINENT_ETA_RATIO:
                        if dev41_best is None or ratio < dev41_best[0]:
                            dev41_best = (ratio, u, C, target_map.get(u),
                                          "FREE_TO_IMMINENT_CORRIDOR")
        if dev41_best is not None:
            _r, u, dest, cur, reason = dev41_best
            alloc.setdefault(dest, []).append(u)
            get_global_metrics().inc("dev4_realloc_events")
            get_global_metrics().inc("dev4_free_imminent_events")
            self._dev4_log_event("REALLOC_FREE", u, cur, dest, reason, target_map, now,
                                 corridors, obs, cls, keep_res)
            return alloc
        best = None  # (benefit, u, dest, old)
        for u in pool:
            if u not in alive or u in keep_res:
                continue
            up = next((x for x in obs.usvs if x.get("name") == u and x.get("position")), None)
            if not up:
                continue
            pos = tuple(up["position"][:2])
            cur = target_map.get(u)
            for dest in sorted(set(imminent) | set(uncovered)):
                if dest == cur or dest not in corridors or u in cls and cls[u] == "HARD_COMMITTED":
                    continue
                p = self.w6.planner.plan(u, pos, corridors.get(dest))
                if p is None:
                    continue
                eta = p.intercept_eta
                # destination need: current lead there
                lead = None
                for name, uu in (self.usv_ctrl.targets or {}).items():
                    if uu == dest:
                        lead = name
                lead_e = None
                if lead:
                    lp = next((x for x in obs.usvs if x.get("name") == lead and x.get("position")), None)
                    if lp:
                        lp_ = self.w6.planner.plan(lead, tuple(lp["position"][:2]),
                                                   corridors.get(dest))
                        if lp_ is not None:
                            lead_e = lp_.intercept_eta
                if cur:
                    oldp = self.w6.planner.plan(u, pos, corridors.get(cur))
                    cur_e = oldp.intercept_eta if oldp else None
                else:
                    cur_e = None
                benefit = (lead_e or float("inf")) - eta if lead_e is not None else 0.0
                reason = None
                if dest in uncovered:
                    reason = "BREAKTHROUGH_URGENT"
                elif cur_e is not None and eta < cur_e * (1 - wcfg.DEV4_MIN_ETA_BENEFIT):
                    reason = "BETTER_INTERCEPTOR"
                elif cur_e is None and lead_e is not None and \
                        eta < lead_e * (1 - wcfg.DEV4_MIN_ETA_BENEFIT) and dest in imminent:
                    reason = "BETTER_INTERCEPTOR"
                if reason is None:
                    continue
                # hard protection: never move a LOCKING/FROZEN platform
                if cls.get(u) == "HARD_COMMITTED":
                    continue
                # soft move must not strand old target
                if cur and len(alloc.get(cur, [])) <= 1 and cls.get(u) == "SOFT_COMMITTED":
                    continue
                # avoid duplicate additions
                if alloc.get(dest) and u in alloc[dest]:
                    continue
                key = benefit if dest in uncovered else ((cur_e or lead_e or 0.0) - eta)
                if best is None or key > best[0]:
                    best = (key, u, dest, cur, reason)
        if best is not None and self.step % 5 == 0:
            _b, u, dest, cur, reason = best
            if cls.get(u) == "SOFT_COMMITTED":
                self.usv_ctrl.targets[u] = dest          # task-level owner change
                get_global_metrics().inc("dev4_soft_release_events")
                etype = "SOFT_RELEASE"
            else:
                alloc.setdefault(dest, []).append(u)
                get_global_metrics().inc("dev4_realloc_events")
                etype = "REALLOC_FREE"
            if reason == "FREE_TO_IMMINENT_CORRIDOR":
                get_global_metrics().inc("dev4_free_imminent_events")
            self._dev4_log_event(etype, u, cur, dest, reason, target_map, now,
                                 corridors, obs, cls, keep_res)
        return alloc

    def _dev4_log_event(self, etype, platform, old, new, reason, target_map, now,
                        corridors, obs, cls, keep_res):
        """Decision-neutral dev4 audit event log (env W6_DEV4_LOG=1). Never affects decisions."""
        if os.getenv("W6_DEV4_LOG", "0") != "1":
            return
        import json as _j
        up = next((x for x in obs.usvs if x.get("name") == platform and x.get("position")), None)
        dest_e = cur_e = lead_e = None
        pos = tuple(up["position"][:2]) if up and up.get("position") else None
        if pos is not None:
            pn = self.w6.planner.plan(platform, pos, corridors.get(new)) if new in corridors else None
            dest_e = pn.intercept_eta if pn else None
            if old and old in corridors:
                po = self.w6.planner.plan(platform, pos, corridors.get(old))
                cur_e = po.intercept_eta if po else None
            lead = None
            for name, uu in (self.usv_ctrl.targets or {}).items():
                if uu == new:
                    lead = name
            if lead:
                lp = next((x for x in obs.usvs if x.get("name") == lead and x.get("position")), None)
                if lp:
                    pl = self.w6.planner.plan(lead, tuple(lp["position"][:2]), corridors.get(new))
                    lead_e = pl.intercept_eta if pl else None
        rec = {"episode": os.getenv("RUN_TAG", "?"), "seed": os.getenv("RUN_SEED", "?"),
               "sim_time": round(float(now), 1), "decision_index": self.step,
               "type": etype, "platform": platform, "old_target": old,
               "new_target": new, "reason": reason,
               "commitment_class": cls.get(platform),
               "cur_eta": round(cur_e, 1) if cur_e else None,
               "dest_eta": round(dest_e, 1) if dest_e else None,
               "lead_eta": round(lead_e, 1) if lead_e else None,
               "held_reserve": bool(platform in keep_res),
               "locking": bool(up and up.get("is_locking")), "frozen": bool(up and up.get("is_frozen"))}
        try:
            with open(os.getenv("DEV4_EVENTS_PATH", "/tmp/opencode/dev4_events.jsonl"),
                      "a", encoding="utf-8") as f:
                f.write(_j.dumps(rec) + "\n")
        except Exception:
            pass

    def _dev4_log_trail(self, obs, now):
        """Compact per-decision platform trail for post-change windows (W6_DEV4_LOG=1)."""
        if os.getenv("W6_DEV4_LOG", "0") != "1":
            return
        import json as _j
        mapd = {}
        for u in obs.usvs:
            mapd[u.get("name")] = {"a": bool(u.get("is_alive")),
                                   "t": self.usv_ctrl.targets.get(u.get("name")),
                                   "l": bool(u.get("is_locking")),
                                   "f": bool(u.get("is_frozen"))}
        rec = {"episode": os.getenv("RUN_TAG", "?"), "sim_time": round(float(now), 1),
               "decision_index": self.step, "units": mapd}
        try:
            with open(os.getenv("DEV4_TRAIL_PATH", "/tmp/opencode/dev4_trail.jsonl"),
                      "a", encoding="utf-8") as f:
                f.write(_j.dumps(rec) + "\n")
        except Exception:
            pass

    def _shadow_log(self, obs, now, base_alloc, corridors, plans, risks):
        """Decision-neutral protected-SOFT shadow evaluator (logs WOULD_REASSIGN only).

        Minimal trigger: SOFT, not near-lock, not unique feasible interceptor, coverage-safe,
        current target risk < HIGH, best alternative risk >= HIGH. Never changes assignments."""
        import json as _j, math as _m
        import os as _os
        path = _os.environ.get("SHADOW_PATH", "/tmp/opencode/shadow.jsonl")
        um = {u: (t or None) for u, t in self.usv_ctrl.targets.items()}
        alive = [u for u in obs.usvs if u.get("is_alive")]
        alive_n = {u["name"] for u in alive}
        lock = {u["name"]: bool(u.get("is_locking") and u.get("locking_unit")) for u in alive}
        frozen = {u["name"]: bool(u.get("is_frozen")) for u in alive}
        usvp = {u["name"]: tuple(u["position"][:2]) for u in alive if u.get("position")}
        committed = {x for vv in base_alloc.values() for x in vv}
        def risk_of(C):
            r = risks.get(C)
            return (getattr(r, "risk_score", 0.0),
                    getattr(r, "breakthrough_eta", None)) if r else (0.0, None)
        def eta_ok(nm, C):
            if nm not in usvp or C not in corridors:
                return False
            p = self.w6.planner.plan(nm, usvp[nm], corridors.get(C))
            if p is None:
                return False
            rs, b = risk_of(C)
            if b is not None and b != float("inf") and b > 0:
                return p.intercept_eta * (1 + wcfg.SCREEN_ETA_SAFETY) <= b
            return True
        def eta_of(nm, C):
            p = self.w6.planner.plan(nm, usvp.get(nm), corridors.get(C)) if nm in usvp else None
            return p.intercept_eta if p else None
        proposals = []
        shadows = []
        for u in alive:
            name = u["name"]
            if lock.get(name) or frozen.get(name):
                continue
            cur = um.get(name)
            cls = "SOFT" if cur else "FREE"
            if cls != "SOFT" or cur is None or cur not in corridors or name not in usvp:
                continue
            rs_C, b_C = risk_of(cur)
            if rs_C >= wcfg.BRK_RISK_HIGH:
                continue
            cp = usvp[name]
            if corridors[cur].current_estimate is not None:
                distC = _m.hypot(cp[0] - corridors[cur].current_estimate[0],
                                 cp[1] - corridors[cur].current_estimate[1])
            else:
                distC = None
            near_lock = distC is not None and distC < a5.LOCK_RANGE
            others_ok = [x for x in alive_n if x != name and not lock.get(x) and not frozen.get(x)
                         and eta_ok(x, cur)]
            unique_ci = (not others_ok) and eta_ok(name, cur)
            # coverage safety: any other HIGH corridor would lose its only in-time candidate
            cov_unsafe = False
            for C2 in risks:
                rs2, b2 = risk_of(C2)
                if C2 == cur or rs2 < wcfg.BRK_RISK_HIGH:
                    continue
                rem = [x for x in alive_n if x != name and not lock.get(x) and not frozen.get(x)]
                if not any(eta_ok(x, C2) for x in rem):
                    cov_unsafe = True
                    break
            # best HIGH/CRITICAL alternative
            best_a, best_r, best_e = None, 0.0, None
            for A in risks:
                rsA, bA = risk_of(A)
                if A == cur or rsA < wcfg.BRK_RISK_HIGH:
                    continue
                eA = eta_of(name, A)
                if eA is None:
                    continue
                if best_a is None or (rsA, -eA) > (best_r, -best_e):
                    best_a, best_r, best_e = A, rsA, eA
            rec = {"p": name, "cur": cur, "cur_risk": round(rs_C, 3),
                   "alt": best_a or "", "alt_risk": round(best_r, 3),
                   "near_lock": near_lock, "unique": unique_ci,
                   "cov_unsafe": cov_unsafe}
            if best_a is None:
                rec["block"] = "NO_HIGH_ALTERNATIVE"
            elif near_lock:
                rec["block"] = "NEAR_LOCK_PROTECTED"
            elif unique_ci:
                rec["block"] = "UNIQUE_INTERCEPTOR_PROTECTED"
            elif cov_unsafe:
                rec["block"] = "COVERAGE_UNSAFE"
            else:
                rec["block"] = "PROPOSAL"
                proposals.append(rec)
            shadows.append(rec)
        line = {"episode": _os.environ.get("RUN_TAG", "?"), "seed": _os.environ.get("RUN_SEED", "?"),
                "sim_time": round(float(now), 1), "decision_index": self.step,
                "proposals": proposals, "shadows": shadows,
                "n_alive": len(alive_n)}
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(_j.dumps(line) + "\n")
        except Exception:
            pass

    def run(self):
        try:
            super().run()
        finally:
            try:
                import json
                with open("/tmp/opencode/w6_metrics.json", "w", encoding="utf-8") as f:
                    json.dump(get_global_metrics().snapshot(), f, ensure_ascii=False)
            except Exception:
                pass


if __name__ == "__main__":
    use_uavs = "--no-uav" not in sys.argv
    W6Agent(use_uavs=use_uavs).run()
