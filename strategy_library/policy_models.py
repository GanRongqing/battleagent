# -*- coding: utf-8 -*-
"""strategy_library/policy_models.py — PolicyCard / ArtifactManifest / EmpiricalFingerprint /
ValidationRecord schemas (declared vs empirical separation)."""
import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from typing import List, Optional

VALID_STATUS = {"candidate", "dev", "validation", "active", "historical", "sealed"}
VALID_ROLES = {"general_opponent", "stress_test", "failure_probe", "regression_anchor",
               "validation_only", "historical_anchor"}


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


@dataclass
class PolicyCard:
    policy_id: str
    version: str
    side: str
    strategy_family: str
    declared_intent: dict
    trigger_and_switch: list
    known_strengths: list
    known_weaknesses: list          # non-empty unless explicit "unknown"
    declared_traits: dict
    status: str = "candidate"
    evaluation_role: str = "general_opponent"
    parent_policy_id: Optional[str] = None
    description: Optional[str] = None
    created_at: str = field(default_factory=now)
    updated_at: str = field(default_factory=now)

    def validate(self):
        errs = []
        if not self.policy_id:
            errs.append("missing policy_id")
        if not self.strategy_family:
            errs.append("missing strategy_family")
        if self.status not in VALID_STATUS:
            errs.append(f"bad status {self.status}")
        if self.evaluation_role not in VALID_ROLES:
            errs.append(f"bad evaluation_role {self.evaluation_role}")
        if not self.known_weaknesses and not self.declared_traits.get("weakness_unknown", False):
            errs.append("known_weaknesses empty (must be non-empty or explicit unknown)")
        return errs

    def to_dict(self):
        return asdict(self)


@dataclass
class ArtifactManifest:
    policy_id: str
    entrypoint: Optional[str] = None
    artifact_files: list = field(default_factory=list)
    artifact_hash: Optional[str] = None
    config_path: Optional[str] = None
    config_hash: Optional[str] = None
    prompt_path: Optional[str] = None
    prompt_hash: Optional[str] = None
    template_path: Optional[str] = None
    template_hash: Optional[str] = None
    environment_hash: Optional[str] = None
    simulator_hash: Optional[str] = None
    opponent_module_hash: Optional[str] = None
    git_commit: Optional[str] = None
    bundle_hash: Optional[str] = None
    created_at: str = field(default_factory=now)

    def compute_bundle(self):
        parts = ["entrypoint=" + (self.entrypoint or "null"),
                 "artifact_hash=" + (self.artifact_hash or "null")]
        for k in ("config_hash", "prompt_hash", "template_hash",
                  "environment_hash", "simulator_hash", "opponent_module_hash"):
            parts.append(f"{k}={self.__dict__.get(k) or 'null'}")
        parts.sort()
        return hashlib.sha256("\n".join(parts).encode()).hexdigest()

    def to_dict(self):
        return asdict(self)


@dataclass
class EmpiricalFingerprint:
    policy_id: str
    fingerprint_version: str
    scenario_set: list = field(default_factory=list)
    seed_set: list = field(default_factory=list)
    episode_count: int = 0
    behavior_features: dict = field(default_factory=dict)
    response_signature: dict = field(default_factory=dict)
    feature_availability: dict = field(default_factory=dict)
    source_logs_hash: Optional[str] = None
    computed_at: str = field(default_factory=now)
    schema_version: str = "fp-v1"

    def to_dict(self):
        return asdict(self)


@dataclass
class ValidationRecord:
    validation_id: Optional[str] = None
    candidate_policy_id: str = ""
    reference_policy_id: str = ""
    artifact_same: Optional[bool] = None
    semantic_difference: dict = field(default_factory=dict)
    empirical_distance: Optional[float] = None
    feature_differences: list = field(default_factory=list)
    multi_seed_stable: Optional[bool] = None
    multi_scenario_stable: Optional[bool] = None
    novelty_verdict: str = "INCONCLUSIVE"
    evaluation_role: str = "general_opponent"
    evidence: dict = field(default_factory=dict)
    created_at: str = field(default_factory=now)

    def to_dict(self):
        return asdict(self)
