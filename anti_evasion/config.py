# -*- coding: utf-8 -*-
"""anti_evasion/config.py — W6 feature gates + normalized parameters.

All parameters are:
  - physically/normalized meaningful (not bare scene thresholds)
  - independent of fleet size / opponent profile / seed
  - recorded here so tuning is auditable

Feature flags read from env W6_FEATURES (comma list) or W6_ANTI_EVASION:
  predictive_intercept
  pursuit_cost
  handoff
  uav_track_maintenance
  adaptive_screen
  breakthrough_horizon
"""
import os

# master switch
W6_ENABLED = os.getenv("W6_ANTI_EVASION", "0").strip().lower() in ("1", "true", "yes")

_FEATURES = {
    "predictive_intercept": True,
    "pursuit_cost": True,
    "handoff": True,
    "uav_track_maintenance": True,
    "adaptive_screen": True,
    "breakthrough_horizon": True,
}

_env_features = os.getenv("W6_FEATURES", "").strip().lower()
if _env_features:
    wanted = {f.strip() for f in _env_features.split(",") if f.strip()}
    for k in _FEATURES:
        _FEATURES[k] = k in wanted
    if not wanted:  # empty string -> all off
        for k in _FEATURES:
            _FEATURES[k] = False

PREDICTIVE_INTERCEPT = _FEATURES["predictive_intercept"]
PURSUIT_COST = _FEATURES["pursuit_cost"]
HANDOFF = _FEATURES["handoff"]
UAV_TRACK_MAINTENANCE = _FEATURES["uav_track_maintenance"]
ADAPTIVE_SCREEN = _FEATURES["adaptive_screen"]
BREAKTHROUGH_HORIZON = _FEATURES["breakthrough_horizon"]

# ── W6-dev3: allocator-centric mode (WHO/WHAT/TARGET vs HOW separation) ──
# W6_MODE ∈ {w5, dev2, dev3, prediction_only}.  Default dev2 preserves current behaviour.
#   w5               : W6 fully off (pure W5 harness).
#   dev2 (default)   : full current W6 — predictive waypoint override + screen move deploy
#                      (execution_override = true).
#   dev3             : allocator-centric. execution_override = FALSE; allocator overlay adds
#                      protected handoff + risk reinforcement + risk-adaptive reserve.
#   prediction_only  : execution_override = FALSE; only risk-adaptive reserve (no handoff /
#                      reinforcement). Prediction/risk never touch navigation.
W6_MODE = os.getenv("W6_MODE", "dev2").strip().lower()
if W6_MODE not in ("w5", "dev2", "dev3", "dev4", "dev4_1", "dev4_2", "prediction_only"):
    W6_MODE = "dev2"

# true in dev2: the agent may write predictive navigation waypoints / screen moves
EXECUTION_OVERRIDE = (W6_MODE == "dev2")
# dev4 / dev4.1 / dev4.2: decision-space redesign (commitment pools + elastic reallocation)
DEV4 = W6_MODE in ("dev4", "dev4_1", "dev4_2")
DEV4_1 = (W6_MODE == "dev4_1")     # relative-ETA ratio FREE->imminent (experiment, superseded)
DEV4_2 = (W6_MODE == "dev4_2")     # capacity-deficit + deadline-feasible + coverage-safe
# LIVE SHADOW AUDIT: real allocator stays W5 (frozen); shadow proposals are logged only.
SHADOW_ONLY = os.getenv("W6_SHADOW_ONLY", "0").strip().lower() in ("1", "true", "yes")
if DEV4:
    EXECUTION_OVERRIDE = False
    ALLOC_ADAPTIVE_RESERVE = True
    ALLOC_HANDOFF = True
    ALLOC_RISK_REINFORCE = True
# dev3 allocator overlay switches
ALLOC_HANDOFF = W6_MODE in ("dev2", "dev3", "dev4", "dev4_1", "dev4_2")
ALLOC_RISK_REINFORCE = (W6_MODE in ("dev3", "dev4", "dev4_1", "dev4_2"))
ALLOC_ADAPTIVE_RESERVE = W6_MODE in ("dev3", "prediction_only", "dev4", "dev4_1", "dev4_2")
# dev4 reallocation limits
DEV4_MAX_REALLOC_PER_STEP = 1
DEV4_MIN_ETA_BENEFIT = 0.25
# dev4.1 candidate gate (superseded by dev4.2; kept for reproducibility)
FREE_TO_IMMINENT_ETA_RATIO = 1.5
# dev4.2 coverage-safe imminent reinforcement
#   deadline feasibility reuses BreakthroughRisk semantics: ETA*(1+SCREEN_ETA_SAFETY)<=b_eta.
#   capacity ceiling reuses W5 intent.emergency_focus_level (default 3) as temporary safety
#   guard. required in-time interceptors: 1 (HIGH) / 2 (CRITICAL).  (candidate gates, not tuned)
REQUIRED_IN_TIME_HIGH = 1
REQUIRED_IN_TIME_CRITICAL = 2
CRITICAL_RISK = 0.9
EMERGENCY_CONCENTRATION = 3   # per-threat saturation ceiling (== W5 emergency_focus default)
# dev3 default reserve adaptation range (normalized fractions, not fixed counts)
RESERVE_BASE_RATIO = 0.20
RESERVE_HIGH_RATIO = 0.40
RESERVE_HIGH_RISK_COUNT = 3        # >= this many high-risk corridors triggers the high ratio
RESERVE_ENDGAME_MAX_RISK = 1       # only one imminent threat -> endgame: no forced reserve

# ── W6-dev3 allocator component isolation (strict cumulative gates) ──
# Env W6_ISO = comma list among {prediction, risk, pursuit, handoff, reserve, track_maint}.
# Isolation runs keep execution_override FALSE and UAV-track-maintenance OFF (unless
# track_maint is listed) so each variant adds exactly ONE allocator component.
_ISO = os.getenv("W6_ISO", "").strip().lower()
ISO_COMPONENTS = {c.strip() for c in _ISO.split(",") if c.strip()} if _ISO else set()
ISO_MODE = bool(_ISO)
ISO_PREDICTION = "prediction" in ISO_COMPONENTS
ISO_RISK = "risk" in ISO_COMPONENTS
ISO_PURSUIT = "pursuit" in ISO_COMPONENTS
ISO_HANDOFF = "handoff" in ISO_COMPONENTS
ISO_RESERVE = "reserve" in ISO_COMPONENTS
ISO_TRACK_MAINT = "track_maint" in ISO_COMPONENTS
# Isolation overrides execution-override to FALSE and pins UAV behaviour to W5 default.
if ISO_MODE:
    EXECUTION_OVERRIDE = False
    UAV_TRACK_MAINTENANCE_FORCE_OFF = True
else:
    UAV_TRACK_MAINTENANCE_FORCE_OFF = False




def feature_on(name):
    return W6_ENABLED and _FEATURES.get(name, False)


# ── normalized / physically-meaningful parameters ──
# prediction horizon: base sim-seconds for a confident, low-maneuver track
PRED_BASE_HORIZON_S = 60.0
# maneuver evidence reduces horizon to at most this fraction
PRED_MIN_HORIZON_S = 15.0
# uncertainty radius at horizon = current uncertainty + growth*horizon + maneuver penalty
UNCERT_GROWTH = 20.0          # m/s of radial growth per second of extrapolation
MANEUVER_UNCERT = 40_000.0    # m added when maneuver_score==1 (linear in maneuver_score)

# intercept: normalized feasibility margin relative to sensing range
INTERCEPT_FEASIBLE_MARGIN = 0.15   # ETA gap fraction of pursuit ETA that is "feasible"
LOCK_RANGE = 40_000.0
USV_SPEED = 20.0
UAV_SPEED = 100.0

# pursuit cost: normalized by sensing range / mission horizon
SENSING_RANGE = 35_000.0           # USV radar (normalization denominator)
MISSION_HORIZON = 600_000.0        # scenario end_time (normalization denominator)
PURSUIT_COST_K = 1.0               # pursuit cost weight (normalized)
COVERAGE_COST_K = 1.0              # coverage-loss weight (normalized)
BREAKTHROUGH_K = 1.0               # breakthrough-urgency weight (normalized)
INTERCEPT_ADVANTAGE_K = 1.0        # intercept-advantage weight (normalized)

# handoff
HANDOFF_MIN_BENEFIT = 0.25         # new ETA must beat old ETA by >=25% (hysteresis)
HANDOFF_COOLDOWN_S = 60.0          # min sim-seconds before a target can be re-handed off
LOCK_PROTECT_K = 1.5               # multiplier on switching cost when old interceptor holds an active lock
ACTIVE_LOCK_AGE_S = 240.0          # engagement that already ran >= this long is near kill chain

# track criticality (normalized 0..1)
CRIT_BREAK_WEIGHT = 1.0
CRIT_UNCERT_WEIGHT = 1.0
CRIT_MANEUVER_WEIGHT = 0.7
CRIT_REDUNDANCY_WEIGHT = 0.8
HIGH_CRIT = 0.6

# adaptive screen
SCREEN_MIN_FRACTION = 0.2          # minimum defensive capacity = fraction of alive USVs
SCREEN_MAX_FRACTION = 0.5          # cap screen at this fraction (never starve offense)
SCREEN_ETA_SAFETY = 0.2            # screen required if best interceptor ETA > breakthrough ETA*(1+safety)

# breakthrough horizon
BREAK_X = 50_000.0
BRK_RISK_HIGH = 0.75
