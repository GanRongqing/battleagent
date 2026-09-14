# -*- coding: utf-8 -*-
"""anti_evasion/pursuit_cost.py — PursuitCost + Pursuit-Cost-Aware allocation adjustment.

W6 Module 2: augment the existing marginal-value allocation without rewriting it.

effective_value = existing_value
                + BREAKTHROUGH_K   * breakthrough_urgency   (0..1)
                + INTERCEPT_ADV_K  * intercept_advantage    (0..1)
                - PURSUIT_COST_K   * pursuit_cost           (0..1)
                - COVERAGE_COST_K  * coverage_cost          (0..1)

Each component is normalized so weights are fleet/scale/opponent independent.
"""
import math

from . import config as cfg


def pursuit_cost(interceptor_pos, target_pos, target_vel,
                 usv_speed=cfg.USV_SPEED, sensing=cfg.SENSING_RANGE):
    """Normalized cost of a long, uncertain pursuit (0..1).

    = distance_to_intercept_promised / sensing_range   (capped at 1)
    + chase_expected (how far the target can run before catch) / sensing_range (capped)
    """
    if interceptor_pos is None or target_pos is None:
        return 1.0
    d = math.hypot(target_pos[0] - interceptor_pos[0], target_pos[1] - interceptor_pos[1])
    dist_term = min(1.0, d / sensing)
    tv = math.hypot(target_vel[0], target_vel[1]) if target_vel else 0.0
    if tv >= usv_speed:
        chase_term = 1.0
    else:
        rel = usv_speed - tv
        chase = tv * (d / rel) if rel > 0 else d
        chase_term = min(1.0, chase / sensing)
    return 0.6 * dist_term + 0.4 * chase_term


def coverage_cost(interceptor_pos, current_cover_positions, sensing=cfg.SENSING_RANGE):
    """Normalized defensive coverage lost if this interceptor leaves its post (0..1).

    = fraction of covered-reference points that fall outside this interceptor's
      sensing radius once it moves (approximated by how far it is from the coverage
      centroid, normalized by sensing range).
    """
    if interceptor_pos is None or not current_cover_positions:
        return 0.0
    cx = sum(p[0] for p in current_cover_positions) / len(current_cover_positions)
    cy = sum(p[1] for p in current_cover_positions) / len(current_cover_positions)
    d = math.hypot(interceptor_pos[0] - cx, interceptor_pos[1] - cy)
    return min(1.0, d / sensing)


def breakthrough_urgency(track, now, corridor=None, break_x=cfg.BREAK_X):
    """0..1 urgency: grows as the target approaches the break line and is fast toward it."""
    pos = track.predicted_position(now) if hasattr(track, "predicted_position") else None
    if pos is None:
        return 0.0
    x = pos[0]
    vx = track.last_velocity[0] if getattr(track, "last_velocity", None) else 0.0
    if x <= break_x:
        return 1.0
    prox = max(0.0, 1.0 - (x - break_x) / 200_000.0)
    vel = max(0.0, min(1.0, -vx / 20.0))
    return 0.7 * prox + 0.3 * vel


def intercept_advantage(intercept_eta, target_eta):
    """0..1: how much better an interceptor is at cutting off the corridor."""
    if intercept_eta is None or target_eta is None:
        return 0.0
    if intercept_eta <= 0:
        return 1.0
    return max(0.0, min(1.0, (target_eta - intercept_eta) / max(target_eta, 1.0)))


def effective_value(existing_value, track, now, interceptor_pos, cover_positions,
                    intercept_eta=None, target_eta=None):
    """W6-adjusted marginal value for one (interceptor, target) candidate.

    All components 0..1; weights from config (normalized)."""
    bc = breakthrough_urgency(track, now)
    ia = intercept_advantage(intercept_eta, target_eta)
    pc = pursuit_cost(interceptor_pos, track.predicted_position(now),
                      track.last_velocity)
    cc = coverage_cost(interceptor_pos, cover_positions)
    return (existing_value
            + cfg.BREAKTHROUGH_K * bc
            + cfg.INTERCEPT_ADVANTAGE_K * ia
            - cfg.PURSUIT_COST_K * pc
            - cfg.COVERAGE_COST_K * cc)
