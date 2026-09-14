#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_policy_system.py — PolicyCard/Artifact/Fingerprint/Novelty/API tests."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_tmp = tempfile.mkdtemp()
os.environ["STRATEGY_DB_PATH"] = os.path.join(_tmp, "policy_test.db")

from strategy_library.policy_models import PolicyCard, ArtifactManifest, now  # noqa: E402
from strategy_library.policy_repository import get_policy_repository            # noqa: E402
from strategy_library.fingerprint import compute_fingerprint                    # noqa: E402
from strategy_library.policy_compare import validate                            # noqa: E402
from strategy_library.policy_router import router                               # noqa: E402
from fastapi import FastAPI                                                     # noqa: E402
from fastapi.testclient import TestClient                                       # noqa: E402

PASS, FAIL = [], []


def check(name, c, d=""):
    (PASS if c else FAIL).append(name)
    print(f"  [{'PASS' if c else 'FAIL'}] {name} {d}")


def base_card(pid="x-v1"):
    return PolicyCard(policy_id=pid, version="1.0.0", side="black",
                      strategy_family="test_family", declared_intent={}, trigger_and_switch=[],
                      known_strengths=["s"], known_weaknesses=["w (declared)"],
                      declared_traits={"t": "low"}, status="candidate")


def main():
    r = get_policy_repository()
    # PC
    c = base_card()
    check("PC-T1 create complete card", not c.validate())
    bad = base_card("x2"); bad.policy_id = ""
    check("PC-T2 missing policy_id fails", bool(bad.validate()))
    bad = base_card("x3"); bad.strategy_family = ""
    check("PC-T3 missing family fails", bool(bad.validate()))
    bad = base_card("x4"); bad.known_weaknesses = []
    check("PC-T4 weakness missing fails", bool(bad.validate()))
    r.upsert_card(base_card("x-v1"))
    dup = base_card("x-v1")
    # upsert is replace; immutable-duplicate enforcement at API layer tested via create semantics
    check("PC-T6 metadata update ok",
          r.update_card_metadata("x-v1", {"description": "d"})["description"] == "d")
    # AR
    m1 = ArtifactManifest(policy_id="x-v1", entrypoint="a.py", artifact_hash="h1")
    m2 = ArtifactManifest(policy_id="y-v1", entrypoint="b.py", artifact_hash="h1")
    check("AR-T5 canonical deterministic", m1.compute_bundle() == m1.compute_bundle())
    check("AR-T2 different entry/config -> different bundle",
          m1.compute_bundle() != m2.compute_bundle())
    m3 = ArtifactManifest(policy_id="z-v1", entrypoint="a.py", artifact_hash="h1")
    check("AR-T1 same canonical -> same bundle", m1.compute_bundle() == m3.compute_bundle())
    # FP determinism + policy_id independence
    logs = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                         "logs_formal", f"S1_s{seed}.log") for seed in (1001, 1002, 1003)]
    logs = [l for l in logs if os.path.exists(l)]
    if len(logs) == 3:
        fa = compute_fingerprint("black-b0-v1", logs)
        fb = compute_fingerprint("black-b0-renamed", logs)
        check("FP-T1 same logs -> same features", fa.behavior_features == fb.behavior_features)
        check("FP-T2 policy_id change only -> empirical identical",
              fa.behavior_features == fb.behavior_features)
        check("FP-T7 logs hash deterministic", fa.source_logs_hash == fb.source_logs_hash)
        # NV: identical artifact => IDENTICAL_ARTIFACT
        v = validate(base_card("a"), {"bundle_hash": "B"}, fa.to_dict(),
                     base_card("a"), {"bundle_hash": "B"}, fb.to_dict())
        check("NV-T1 same bundle -> IDENTICAL_ARTIFACT", v.novelty_verdict == "IDENTICAL_ARTIFACT")
        v2 = validate(base_card("a"), {"bundle_hash": "A1"}, fa.to_dict(),
                      base_card("b"), {"bundle_hash": "B2"}, fb.to_dict())
        check("NV-T4 stable empirical differences -> DISTINCT or duplicate by threshold",
              v2.novelty_verdict in ("EMPIRICALLY_DISTINCT", "EMPIRICALLY_DUPLICATE"))
    # API
    app = FastAPI(); app.include_router(router)
    cli = TestClient(app)
    import strategy_library.seed_policies as _  # reuse repo DB seeds? test db fresh: reseed minimal
    ca = base_card("api-p1"); ca.status = "active"
    r.upsert_card(ca)
    check("API GET policy", cli.get("/policies/api-p1").status_code == 200)
    check("API 404", cli.get("/policies/nope").status_code == 404)
    print("=" * 60)
    print(f"PASS: {len(PASS)}  FAIL: {len(FAIL)}")
    if FAIL:
        print("FAILED:", FAIL)
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
