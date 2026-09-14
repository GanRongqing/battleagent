# -*- coding: utf-8 -*-
"""strategy_library/policy_router.py — immutable policy endpoints (cards/artifact/fingerprint/compare)."""
from fastapi import APIRouter, HTTPException

from .policy_models import PolicyCard, now
from .policy_repository import get_policy_repository
from .policy_compare import validate

router = APIRouter(tags=["policies"])


def _repo():
    return get_policy_repository()


@router.get("/policies/{policy_id}")
def get_policy(policy_id: str):
    c = _repo().get_card(policy_id)
    if c is None:
        raise HTTPException(404, "policy not found")
    return c


@router.get("/policies/{policy_id}/artifact")
def get_artifact(policy_id: str):
    m = _repo().get_artifact(policy_id)
    if m is None:
        raise HTTPException(404, "no artifact manifest")
    return m


@router.get("/policies/{policy_id}/fingerprints")
def get_fingerprints(policy_id: str):
    return _repo().fingerprints(policy_id)


@router.get("/policies/{policy_id}/fingerprint/latest")
def latest_fingerprint(policy_id: str):
    fps = _repo().fingerprints(policy_id)
    if not fps:
        raise HTTPException(404, "no fingerprint")
    v2 = [f for f in fps if f.get("fingerprint_version") == "fp-v2"]
    return (v2 or fps)[0]


def _get_pair_validation(r, a, b, fp_version=None):
    import json as _json
    for va, vb in ((a, b), (b, a)):
        for row in r.validations(va):
            if row.get("reference_policy_id") != vb:
                continue
            ev = row.get("evidence")
            if isinstance(ev, str):
                try:
                    ev = _json.loads(ev)
                except Exception:
                    ev = {}
            ev = ev or {}
            if fp_version and ev.get("fingerprint_version") != fp_version:
                continue
            return row, ev
    return None, None


@router.get("/policies/{policy_id}/compare/{other_policy_id}")
def compare(policy_id: str, other_policy_id: str):
    r = _repo()
    ca, cb = r.get_card(policy_id), r.get_card(other_policy_id)
    ma, mb = r.get_artifact(policy_id), r.get_artifact(other_policy_id)
    if not (ca and cb):
        raise HTTPException(404, "policy missing")
    if not (ma and mb):
        return {"policy_a": policy_id, "policy_b": other_policy_id,
                "verdict": "INSUFFICIENT_EVIDENCE",
                "note": "missing artifact manifest"}
    from .policy_compare import compare_artifacts, semantic_difference
    base = {"policy_a": policy_id, "policy_b": other_policy_id,
            "artifact": {"same": bool(compare_artifacts(ma, mb))},
            "declared_semantic": semantic_difference(ca, cb),
            "verdict": "INSUFFICIENT_EVIDENCE"}
    fpa = [f for f in r.fingerprints(policy_id) if f.get("fingerprint_version") == "fp-v2"]
    fpb = [f for f in r.fingerprints(other_policy_id) if f.get("fingerprint_version") == "fp-v2"]
    if not (fpa and fpb):
        # legacy fp-v1 path (unchanged behaviour)
        fa = (r.fingerprints(policy_id) or [None])[0]
        fb = (r.fingerprints(other_policy_id) or [None])[0]
        if not (fa and fb):
            return {**base, "note": "no fingerprint available"}
        from .policy_compare import validate
        v = validate(ca, ma, fa, cb, mb, fb)
        r.add_validation(v)
        return {**base,
                "artifact": {"same": v.artifact_same},
                "semantic": v.semantic_difference,
                "empirical": {"distance": v.empirical_distance,
                              "top_feature_differences": v.feature_differences},
                "stability": {"multi_seed": v.multi_seed_stable},
                "verdict": v.novelty_verdict,
                "fingerprint_version": fa.get("fingerprint_version", "fp-v1")}
    # fp-v2 path: behaviour and response separated; verdict from stored calibration
    val, ev = _get_pair_validation(r, policy_id, other_policy_id, fp_version="fp-v2")
    if val is None:
        return {**base, "fingerprint_version": "fp-v2",
                "note": "fp-v2 common-calibration pair record not yet computed"}
    return {**base,
            "behavioral": ev.get("behavioral", {}),
            "response": ev.get("response", {}),
            "multi_seed": ev.get("multi_seed", {}),
            "multi_scenario": {"validated": False,
                               "status": "NOT_YET",
                               "note": "only S2 common calibration run"},
            "fingerprint_version": "fp-v2",
            "verdict": val.get("novelty_verdict")}


@router.post("/policies/{policy_id}/seal", status_code=200)
def seal(policy_id: str):
    r = _repo()
    c = r.get_card(policy_id)
    if c is None:
        raise HTTPException(404, "policy not found")
    if c["status"] == "sealed":
        return {"policy_id": policy_id, "status": "sealed"}
    if c["status"] not in ("candidate", "dev", "validation"):
        raise HTTPException(409, f"cannot seal from status {c['status']}")
    # artifact drift check: recompute current file hash vs manifest (heuristic entrypoint path)
    import os
    drift = None
    m = r.get_artifact(policy_id)
    if m and m.get("entrypoint"):
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         m["entrypoint"]) if not os.path.isabs(m["entrypoint"]) else m["entrypoint"]
        if os.path.exists(p):
            import hashlib
            cur = hashlib.sha256(open(p, "rb").read()).hexdigest()
            if m.get("artifact_hash") and cur != m["artifact_hash"]:
                drift = "ARTIFACT_DRIFT"
    c["status"] = "sealed"
    c["updated_at"] = now()
    r.upsert_card(PolicyCard(**{k: c[k] for k in
                                ("policy_id", "version", "side", "strategy_family",
                                 "declared_intent", "trigger_and_switch", "known_strengths",
                                 "known_weaknesses", "declared_traits", "status",
                                 "evaluation_role", "parent_policy_id", "description",
                                 "created_at", "updated_at")}))
    return {"policy_id": policy_id, "status": "sealed", "drift": drift}
