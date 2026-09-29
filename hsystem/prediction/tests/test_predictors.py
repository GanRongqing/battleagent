# -*- coding: utf-8 -*-
"""test_predictors.py — Part B synthetic unit tests (no simulator)."""
import math
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from prediction.history import TrackHistory
from prediction.manager import PredictorManager
from prediction.models.constant_velocity import ConstantVelocityPredictor
from prediction.models.constant_turn import ConstantTurnPredictor
from prediction.models.recent_velocity import RecentVelocityPredictor


def mk(history_samples):
    h = TrackHistory("t1")
    for t, x, y in history_samples:
        h.add(t, x, y)
    return h


def straight():
    return mk([(i, 100 * i, 0) for i in range(6)])


def turn():
    out = []
    for i in range(7):
        ang = math.radians(20 * i)
        out.append((i, 100 * math.cos(ang), 100 * math.sin(ang)))
    return mk(out)


def test_T1_straight_cv_good():
    h = straight()
    p = ConstantVelocityPredictor().predict(h, 5)
    assert abs(p.position_x - 1000) < 60 and abs(p.position_y) < 60, (p.position_x, p.position_y)


def test_T2_turn_constant_turn_beats_cv():
    h = turn()
    cv = ConstantVelocityPredictor().predict(h, 5)
    ct = ConstantTurnPredictor().predict(h, 5)
    # true next point (i=7) on radius 100 circle
    tx, ty = 100 * math.cos(math.radians(140)), 100 * math.sin(math.radians(140))
    assert ct.distance_to(tx, ty) <= cv.distance_to(tx, ty) + 1e-6, (ct.distance_to(tx, ty), cv.distance_to(tx, ty))


def test_T3_speed_up():
    h = mk([(i, 50 * i * i, 0) for i in range(5)])
    p = ConstantVelocityPredictor().predict(h, 1)
    assert p.position_x > h.latest()[1]


def test_T4_slow_down():
    h = mk([(i, 200 * i - 10 * i * i, 0) for i in range(5)])
    p = ConstantVelocityPredictor().predict(h, 1)
    assert p.position_x > h.latest()[1]


def test_T5_scurve():
    h = mk([(i, 100 * math.sin(i / 2.0), 0) for i in range(10)])
    assert ConstantVelocityPredictor().predict(h, 2).model_id == "constant_velocity"


def test_T6_abrupt_heading_change():
    pts = [(i, 100 * i, 0) for i in range(4)] + [(4, 300, 0), (5, 300, 100)]
    h = mk(pts)
    assert RecentVelocityPredictor().predict(h, 1).model_id == "recent_velocity"


def test_T7_observation_gap():
    h = mk([(0, 0, 0), (1, 10, 0), (30, 300, 0)])  # gap -> stale single-step velocity is large
    p = ConstantVelocityPredictor().predict(h, 5)
    assert p.uncertainty_radius > 0


def test_T8_reacquisition_selector_prefers_accurate():
    mgr = PredictorManager()
    h = straight()
    # run: predict all, then re-observe true position, update scores
    from prediction.prediction import Prediction
    for step in range(2, 12):
        preds = mgr.predict_all(h, 1)
        true_x = 100 * (step + 1)
        mgr.observe(true_x, 0.0, [(p, step + 1) for p in preds], step + 1)
        h.add(step, true_x, 0.0)
    best, allp, reason = mgr.select(h, 1)
    assert reason == "min_recent_error" and best.model_id == "constant_velocity", (reason, best.model_id)


def test_selector_fallback_without_evidence():
    mgr = PredictorManager()
    best, allp, reason = mgr.select(straight(), 1)
    assert reason == "fallback_insufficient_evidence" and best.model_id == "constant_velocity"


def test_no_hidden_truth_only_history():
    # predictor can only take a TrackHistory; ensure interface signature
    import inspect
    sig = inspect.signature(ConstantVelocityPredictor.predict)
    assert list(sig.parameters) == ["self", "history", "horizon_s"]


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t(); print("PASS", t.__name__)
        except Exception as e:
            failed += 1; print("FAIL", t.__name__, ":", e)
    print("=" * 40)
    print("PASS" if failed == 0 else "FAIL", f"{len(tests)-failed}/{len(tests)}")
    sys.exit(1 if failed else 0)
