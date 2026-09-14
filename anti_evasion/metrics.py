# -*- coding: utf-8 -*-
"""anti_evasion/metrics.py — W6 mechanism metrics (evaluator-side counters).

Records whether W6 mechanisms actually fire, so the DEV/ablation reports can prove
"feature triggered" (no silent no-op features). These are pure counters; they never
affect decisions.
"""
import threading


class W6Metrics:
    def __init__(self):
        self._l = threading.Lock()
        self.reset()

    def reset(self):
        with self._l:
            self.counts = {
                "prediction_count": 0,
                "intercept_count": 0,
                "unique_intercept_plan_changes": 0,
                "handoff_count": 0,
                "successful_handoff_count": 0,
                "handoff_eta_improvement_sum": 0.0,
                "handoff_evaluations": 0,
                "track_maintenance_assignments": 0,
                "screen_assignments": 0,
                "screen_evaluations": 0,
                "unique_screen_reconfigurations": 0,
                "high_risk_threat_events": 0,
                "late_intercept_events": 0,
                "breakthrough_risk_alerts": 0,
                "risk_evaluations": 0,
                "unique_high_risk_transitions": 0,
                "critical_risk_entries": 0,
                "unsafe_close_entries": 0,
                "unsafe_close_duration_steps": 0,
                "min_target_distance_during_pursuit": None,
                "reposition_outward_count": 0,
                "mean_pursuit_duration_sum": 0.0,
                "mean_pursuit_duration_n": 0,
                "max_pursuit_duration": 0.0,
                "mean_track_uncertainty_sum": 0.0,
                "mean_track_uncertainty_n": 0,
                "high_criticality_track_loss_count": 0,
                "uncovered_threat_duration_steps": 0,
                "dev3_handoffs": 0,
                "dev3_reinforcement_events": 0,
                "defensive_reserve_events": 0,
                "w6_execution_override_actions": 0,
                "assignment_change_count": 0,
                "assignment_lifetime_sum": 0.0,
                "assignment_lifetime_n": 0,
                "dev4_soft_release_events": 0,
                "dev4_realloc_events": 0,
                "dev4_reserve_release_events": 0,
                "dev4_reserve_create_events": 0,
                "dev4_free_pool_sum": 0.0,
                "dev4_free_pool_n": 0,
                "dev4_free_imminent_events": 0,
                "dev4_capacity_reinforce_events": 0,
                "dev4_hard_commit_violations": 0,
            }
            self._handoff_pending = {}   # target -> old_eta (to confirm success)

    def inc(self, key, by=1):
        with self._l:
            self.counts[key] = self.counts.get(key, 0) + by

    def add(self, key, value):
        with self._l:
            self.counts[key] = self.counts.get(key, 0) + value

    def snapshot(self):
        with self._l:
            return dict(self.counts)

    # handoff success bookkeeping
    def note_handoff(self, target, old_eta):
        with self._l:
            self.counts["handoff_count"] += 1
            self._handoff_pending[target] = old_eta

    def note_handoff_outcome(self, target, actual_new_eta):
        """successful handoff: new interceptor ETA stays below the old predicted ETA."""
        with self._l:
            old = self._handoff_pending.pop(target, None)
            if old is None or actual_new_eta is None:
                return
            if actual_new_eta < old:
                self.counts["successful_handoff_count"] += 1
                self.counts["handoff_eta_improvement_sum"] += (old - actual_new_eta)


_GLOBAL = W6Metrics()


def get_global_metrics():
    return _GLOBAL
