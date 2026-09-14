# -*- coding: utf-8 -*-
"""anti_evasion/w6_harness.py — W6DecisionCore.

Combines the W6 modules into a per-step decision layer over the frozen V5 belief tracker.
Feature-gated: each component can be disabled (see config.W6_FEATURES).

Outputs per step:
  corridors             track_name -> PredictedCorridor
  intercept_plans       track_name -> best InterceptPlan (cheapest feasible interceptor)
  breakthrough_risks    track_name -> BreakthroughRisk
  criticalities         track_name -> criticality
  screen                AdaptiveScreenPlanner.ScreenPlan
  allocation            W6-adjusted {target: [interceptor...]}
  handoffs              list[HandoffDecision]
  metrics               W6Metrics counters (fire-check)
"""
import math

from . import config as cfg
from .motion_predictor import ShortHorizonPredictor
from .intercept_planner import InterceptPlanner
from .breakthrough_risk import BreakthroughRiskEstimator
from .pursuit_cost import effective_value
from .handoff import HandoffEvaluator
from .track_criticality import criticality, is_high_criticality
from .adaptive_screen import AdaptiveScreenPlanner
from .metrics import get_global_metrics


class W6DecisionCore:
    def __init__(self):
        self.predictor = ShortHorizonPredictor()
        self.planner = InterceptPlanner()
        self.brk = BreakthroughRiskEstimator()
        self.handoff = HandoffEvaluator()
        self.screen = AdaptiveScreenPlanner()
        self.metrics = get_global_metrics()
        self._screen_sig = None
        self._intercept_sigs = {}
        self._risk_state = {}
        self._last_handoff_evals = 0

    # ── 1) predictive interception ──
    def compute_corridors(self, tracks, now):
        corridors = {}
        if not cfg.feature_on("predictive_intercept"):
            return corridors
        for name, t in tracks.items():
            c = self.predictor.predict(t, now)
            if c is not None:
                corridors[name] = c
                self.metrics.inc("prediction_count")
        return corridors

    def compute_intercept_plans(self, corridors, usv_positions, now):
        plans = {}
        if not cfg.feature_on("predictive_intercept"):
            return plans
        for name, corr in corridors.items():
            best = None
            for usv_name, pos in usv_positions.items():
                pl = self.planner.plan(usv_name, pos, corr)
                if pl is None:
                    continue
                if best is None or pl.intercept_eta < best.intercept_eta:
                    best = pl
            if best is not None:
                plans[name] = best
                self.metrics.inc("intercept_count")
                # unique plan change: only when the waypoint/geometry materially changes
                sig = (round(best.intercept_point[0], 3), round(best.intercept_point[1], 3),
                       best.geometry_state)
                if self._intercept_sigs.get(name) != sig:
                    self._intercept_sigs[name] = sig
                    self.metrics.inc("unique_intercept_plan_changes")
        return plans

    # ── 5) breakthrough horizon risk ──
    def compute_risks(self, tracks, now, corridors, intercept_plans):
        risks = {}
        if not cfg.feature_on("breakthrough_horizon"):
            return risks
        for name, t in tracks.items():
            r = self.brk.estimate(t, now, corridors, intercept_plans)
            risks[name] = r
            self.metrics.inc("risk_evaluations")
            # risk TRANSITIONS (LOW/HIGH/CRITICAL) not per-tick counts
            prev = self._risk_state.get(name, "LOW")
            cur = ("CRITICAL" if r.risk_score >= 0.9
                   else "HIGH" if r.risk_score >= cfg.BRK_RISK_HIGH else "LOW")
            if prev != cur:
                if (prev == "LOW" and cur in ("HIGH", "CRITICAL")) or \
                        (prev == "HIGH" and cur == "CRITICAL"):
                    self.metrics.inc("unique_high_risk_transitions")
                if cur == "CRITICAL":
                    self.metrics.inc("critical_risk_entries")
                self._risk_state[name] = cur
            if r.risk_score >= cfg.BRK_RISK_HIGH:
                self.metrics.inc("breakthrough_risk_alerts")
            if r.interceptor_deficit is not None and r.interceptor_deficit < 0:
                self.metrics.inc("late_intercept_events")
        return risks

    # ── 3) track criticality (UAV maintenance) ──
    def compute_criticalities(self, tracks, now, sensor_support):
        crits = {}
        if not cfg.feature_on("uav_track_maintenance"):
            return crits
        for name, t in tracks.items():
            c = criticality(t, now, sensor_support_count=sensor_support.get(name, 0))
            crits[name] = c
        return crits

    # ── 4) adaptive defensive screen ──
    def compute_screen(self, alive_usvs, usv_positions, tracks, now, corridors,
                       intercept_plans, committed_names):
        if not cfg.feature_on("adaptive_screen"):
            return None
        # A corridor needs defensive screen coverage when the current best interceptor
        # arrangement CANNOT stop it in time:
        #   - no feasible intercept plan, OR
        #   - best interceptor is TOO LATE: interceptor_deficit < 0
        #     (interceptor ETA*(1+safety) exceeds the target's time-to-breakthrough).
        # NOTE: BreakthroughRisk.risk_score is an engagement-urgency score that clamps to 0
        # when the interceptor is hopelessly late, so the screen must NOT be gated on
        # risk_score alone — it keys on the deficit (the true "can't stop it" signal).
        uncovered = []
        screen_eta_ok = True
        for name, t in tracks.items():
            plan = intercept_plans.get(name)
            risk = self.compute_risks({name: t}, now, corridors, intercept_plans).get(name)
            if risk is None:
                continue
            b_eta = getattr(risk, "breakthrough_eta", None)
            if b_eta is None or b_eta == float("inf") or b_eta <= 0.0:
                continue  # no imminent breakthrough deadline (moving away / already past)
            too_late = risk.interceptor_deficit is not None and risk.interceptor_deficit < 0
            no_feasible = plan is None or not plan.intercept_feasible
            if too_late or no_feasible:
                uncovered.append(corridors.get(name))
                screen_eta_ok = False
        cover = list(usv_positions.values())
        plan = self.screen.plan(alive_usvs, cover, [u for u in uncovered if u],
                                committed_names, screen_eta_ok=screen_eta_ok)
        # unique reconfigurations only when the demand signature changes
        self.metrics.inc("screen_evaluations")
        if self._screen_sig != plan.signature:
            self._screen_sig = plan.signature
            self.metrics.inc("unique_screen_reconfigurations")
        return plan

    # ── 2) pursuit-cost-aware allocation + handoff ──
    def w6_allocation(self, base_alloc, tracks, usv_positions, usv_states, now,
                      corridors, intercept_plans, current_commitments=None):
        """Adjust the frozen allocator's output with W6 value terms, and apply handoff.

        Handoff correctness: compare the CURRENT COMMITTED interceptor (from the existing
        engagement state, e.g. usv_ctrl.targets) vs the BEST alternative (the highest-value
        W6 interceptor for this target / best ETA) — never a self-compare.
        """
        if not (cfg.feature_on("pursuit_cost") or cfg.feature_on("handoff")):
            return base_alloc, []
        handoffs = []
        alloc = {}
        for target, usvs in base_alloc.items():
            t = tracks.get(target)
            if t is None:
                alloc[target] = usvs
                continue
            # choose the interceptor with best W6 effective value
            best = None
            for uname in usvs:
                pos = usv_positions.get(uname)
                plan = intercept_plans.get(target)
                ieta = plan.intercept_eta if plan and plan.interceptor == uname else None
                teta = plan.target_eta if plan else None
                val = effective_value(0.0, t, now, pos, list(usv_positions.values()),
                                      ieta, teta)
                if best is None or val > best[1]:
                    best = (uname, val)
            chosen = best[0] if best else (usvs[0] if usvs else None)
            if chosen:
                alloc[target] = [chosen]
            # handoff: current committed interceptor vs best alternative (correct object)
            if cfg.feature_on("handoff") and chosen is not None and len(usv_positions) >= 2:
                current = (current_commitments or {}).get(target, chosen)
                plan = intercept_plans.get(target)
                cur_eta = None
                for u in usv_positions:
                    p = self.planner.plan(u, usv_positions[u], corridors.get(target))
                    if p is not None and u == current:
                        cur_eta = p.intercept_eta
                best_alt = None
                best_alt_eta = None
                for u in usv_positions:
                    if u == current:
                        continue
                    p = self.planner.plan(u, usv_positions[u], corridors.get(target))
                    if p is None:
                        continue
                    if best_alt_eta is None or p.intercept_eta < best_alt_eta:
                        best_alt, best_alt_eta = u, p.intercept_eta
                if current != chosen:
                    # keep the higher-value interceptor as alternative reference
                    alt = chosen if chosen != current else best_alt
                    alt_eta = None
                    if alt:
                        for u in usv_positions:
                            p = self.planner.plan(u, usv_positions[u], corridors.get(target))
                            if p is not None and u == alt:
                                alt_eta = p.intercept_eta
                    dec = self.handoff.evaluate(target, current, alt, cur_eta, alt_eta,
                                                usv_states.get(current), now)
                else:
                    dec = self.handoff.evaluate(target, current, best_alt, cur_eta,
                                                best_alt_eta, usv_states.get(current), now)
                if dec.handoff:
                    handoffs.append(dec)
                    self.metrics.note_handoff(target, dec.old_eta)
                    alloc[target] = [dec.to_interceptor]
        self.metrics.add("handoff_evaluations", max(0, self.handoff.evaluations - self._last_handoff_evals))
        self._last_handoff_evals = self.handoff.evaluations
        return alloc, handoffs

    # ── W6-dev3: allocator-centric overlay (WHO/WHAT/TARGET only) ──
    def allocator_centric(self, base_alloc, tracks, usv_positions, usv_states, now,
                          corridors, plans, risks, current_commitments=None):
        """dev3 allocator overlay. Never changes navigation.

        base_alloc is the FROZEN W5 allocation (coverage floor + marginal concentration +
        reserve). This overlay only:
          1. preserves base multiplicity (no collapse) — execution runs legacy,
          2. risk-adaptive defensive reserve CAP: how many free USVs the overlay may pull,
          3. protected handoff (owner change / add better lead) using a FREE alternative,
          4. risk reinforcement: commit a free USV to an uncovered imminent-breakthrough
             threat (deficit < 0).
        All resulting assignments are executed by the LEGACY W5 USVController.
        """
        alloc = {t: list(us) for t, us in base_alloc.items()}
        committed_pool = {u for us in alloc.values() for u in us}
        free = [u for u in usv_positions if u not in committed_pool]
        n_alive = len(usv_positions)
        # ── strict cumulative component gates (isolation) or dev3 defaults ──
        if cfg.ISO_MODE:
            g_risk = cfg.ISO_RISK
            g_pursuit = cfg.ISO_PURSUIT
            g_handoff = cfg.ISO_HANDOFF
            g_reserve = cfg.ISO_RESERVE
        else:
            g_risk = cfg.ALLOC_RISK_REINFORCE
            g_pursuit = cfg.PURSUIT_COST
            g_handoff = cfg.ALLOC_HANDOFF
            g_reserve = cfg.ALLOC_ADAPTIVE_RESERVE
        # imminent high-risk corridors (finite breakthrough horizon)
        imminent = 0
        uncovered = []
        for name, r in (risks or {}).items():
            b_eta = getattr(r, "breakthrough_eta", None)
            if b_eta is None or b_eta == float("inf") or b_eta <= 0:
                continue
            too_late = r.interceptor_deficit is not None and r.interceptor_deficit < 0
            if (r.risk_score >= cfg.BRK_RISK_HIGH) or too_late:
                imminent += 1
                if too_late or plans.get(name) is None or not plans[name].intercept_feasible:
                    uncovered.append(name)
        n_ship_targets = sum(1 for t in alloc if tracks.get(t) is not None)
        # defensive reserve ratio: threat-driven, resource-relative, endgame-aware
        if not g_reserve:
            desired_reserve = 0
        elif imminent <= cfg.RESERVE_ENDGAME_MAX_RISK or n_ship_targets <= 1:
            desired_reserve = 0
        elif imminent >= cfg.RESERVE_HIGH_RISK_COUNT:
            desired_reserve = int(round(n_alive * cfg.RESERVE_HIGH_RATIO))
        else:
            desired_reserve = int(round(n_alive * cfg.RESERVE_BASE_RATIO))
        allowed_pull = max(0, len(free) - desired_reserve)
        if uncovered:
            self.metrics.inc("defensive_reserve_events")

        def _rank(u, target):
            """candidate USV u for target: (maximize value if pursuit-on, else minimize ETA)."""
            pos = usv_positions.get(u)
            corr = corridors.get(target)
            p = self.planner.plan(u, pos, corr) if pos is not None and corr is not None else None
            if p is None:
                return None
            if g_pursuit:
                t = tracks.get(target)
                if t is None:
                    return ("min", p.intercept_eta)
                val = effective_value(0.0, t, now, pos, list(usv_positions.values()),
                                      p.intercept_eta, p.target_eta)
                return ("max", val)
            return ("min", p.intercept_eta)

        def _pick(usv_list, target):
            best, best_key = None, None
            for u in usv_list:
                k = _rank(u, target)
                if k is None:
                    continue
                mode, v = k
                if best_key is None or (mode == "min" and v < best_key) or \
                        (mode == "max" and v > best_key):
                    best, best_key = u, v
            return best

        # ── 4) risk reinforcement: cover imminent/too-late corridors with a free USV ──
        if g_risk and allowed_pull > 0:
            cap = 3
            order = sorted(uncovered, key=lambda n: -getattr(risks.get(n), "risk_score", 0.0))
            for name in order:
                if allowed_pull <= 0:
                    break
                assigned = alloc.get(name) or []
                t = tracks.get(name)
                if t is None or len(assigned) >= cap:
                    continue
                best_u = _pick(free, name)
                if best_u is not None:
                    alloc.setdefault(name, []).append(best_u)
                    free.remove(best_u)
                    allowed_pull -= 1
                    self.metrics.inc("dev3_reinforcement_events")
                    self.metrics.inc("defensive_reserve_events")
        # ── 3) protected handoff: better FREE alternative takes/joins the engagement ──
        if g_handoff and free and allowed_pull > 0:
            for target in list(alloc.keys()):
                if allowed_pull <= 0 or not free:
                    break
                assigned = alloc.get(target) or []
                if not assigned:
                    continue
                current = (current_commitments or {}).get(target)
                if current is None or current not in assigned:
                    current = assigned[0]
                cur_e = None
                for u in [current]:
                    p = self.planner.plan(u, usv_positions.get(u), corridors.get(target))
                    if p is not None:
                        cur_e = p.intercept_eta
                best_u = _pick(free, target)
                if best_u is None or cur_e is None or cur_e <= 0:
                    continue
                best_e = None
                p = self.planner.plan(best_u, usv_positions[best_u], corridors.get(target))
                if p is not None:
                    best_e = p.intercept_eta
                if best_e is None:
                    continue
                dec = self.handoff.evaluate(target, current, best_u, cur_e, best_e,
                                            usv_states.get(current), now)
                if dec.handoff:
                    alloc.setdefault(target, []).append(best_u)
                    free.remove(best_u)
                    allowed_pull -= 1
                    self.metrics.note_handoff(target, dec.old_eta)
                    self.metrics.inc("dev3_handoffs")
        self.metrics.add("handoff_evaluations", max(0, self.handoff.evaluations - self._last_handoff_evals))
        self._last_handoff_evals = self.handoff.evaluations
        return alloc

    def features(self, tracks, usvs, now, usv_positions, usv_states, sensor_support=None):
        """W6 state features WITHOUT any allocation. Used by dev3 / isolation so the
        (ignored) dev2 collapse-allocation inside step() never runs or pollutes metrics.
        """
        corridors = self.compute_corridors(tracks, now)
        plans = self.compute_intercept_plans(corridors, usv_positions, now)
        risks = self.compute_risks(tracks, now, corridors, plans)
        crits = self.compute_criticalities(tracks, now, sensor_support or {})
        screen = self.compute_screen(len(usv_positions), usv_positions, tracks, now,
                                     corridors, plans, set(plans.keys()))
        return {"corridors": corridors, "intercept_plans": plans, "risks": risks,
                "criticalities": crits, "screen": screen}

    def step(self, tracks, usvs, now, base_alloc, usv_positions, usv_states,
             sensor_support=None, current_commitments=None):
        corridors = self.compute_corridors(tracks, now)
        plans = self.compute_intercept_plans(corridors, usv_positions, now)
        risks = self.compute_risks(tracks, now, corridors, plans)
        crits = self.compute_criticalities(tracks, now, sensor_support or {})
        screen = self.compute_screen(len(usv_positions), usv_positions, tracks, now,
                                     corridors, plans, set(base_alloc.keys()))
        alloc, handoffs = self.w6_allocation(base_alloc, tracks, usv_positions,
                                             usv_states, now, corridors, plans,
                                             current_commitments)
        return {
            "corridors": corridors, "intercept_plans": plans, "risks": risks,
            "criticalities": crits, "screen": screen, "allocation": alloc,
            "handoffs": handoffs,
        }
