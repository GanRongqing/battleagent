# 07 — C6B Determinism
C6B is a pure post-process on the parent controller's actions (deterministic thresholds/hysteresis;
no new RNG). Same-seed behaviour is expected deterministic; full engine-level repeatability was limited
by the environment (API restarts during eval). No truth, no route/strategy-ID.
