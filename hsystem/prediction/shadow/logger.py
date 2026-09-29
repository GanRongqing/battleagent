# -*- coding: utf-8 -*-
"""Shadow logger — records predictions + re-observation errors WITHOUT affecting control."""
import csv
import os


class ShadowLogger:
    def __init__(self, outdir):
        self.outdir = outdir
        os.makedirs(outdir, exist_ok=True)
        self.pred_path = os.path.join(outdir, "PREDICTIONS.csv")
        self.err_path = os.path.join(outdir, "REOBS_ERRORS.csv")
        self.score_path = os.path.join(outdir, "MODEL_SCORES.csv")
        self._init(self.pred_path, ["sim_time", "track_id", "horizon_s", "model_id",
                                    "pred_x", "pred_y", "uncertainty_radius", "confidence",
                                    "selected_model", "track_age", "maneuver_score"])
        self._init(self.err_path, ["sim_time", "track_id", "model_id", "prediction_error", "model_rank"])
        self._init(self.score_path, ["sim_time", "track_id", "model_id", "ema_error", "n"])

    def _init(self, p, cols):
        if not os.path.exists(p):
            with open(p, "w", newline="") as f:
                csv.writer(f).writerow(cols)

    def log_prediction(self, row):
        with open(self.pred_path, "a", newline="") as f:
            csv.writer(f).writerow([row.get(c, "") for c in
                                    ["sim_time", "track_id", "horizon_s", "model_id", "pred_x", "pred_y",
                                     "uncertainty_radius", "confidence", "selected_model", "track_age",
                                     "maneuver_score"]])

    def log_error(self, row):
        with open(self.err_path, "a", newline="") as f:
            csv.writer(f).writerow([row.get(c, "") for c in
                                    ["sim_time", "track_id", "model_id", "prediction_error", "model_rank"]])

    def log_scores(self, sim_time, track_id, scorer):
        for m, e in scorer.ema.items():
            with open(self.score_path, "a", newline="") as f:
                csv.writer(f).writerow([sim_time, track_id, m, round(e, 2), scorer.count.get(m, 0)])
