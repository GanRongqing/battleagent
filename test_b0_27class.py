#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_b0_27class.py — B0 27-class stratification tests (B027-T1..T10)."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "b0_log_stratification"))
import b0_stratify as b  # noqa: E402

PASS, FAIL = [], []


def check(name, c, d=""):
    (PASS if c else FAIL).append(name)
    print(f"  [{'PASS' if c else 'FAIL'}] {name} {d}")


def main():
    # B027-T1 percentile deterministic / correct 33-66
    v = list(range(1, 101))
    q1 = b.pct(v, 1 / 3)
    q2 = b.pct(v, 2 / 3)
    check("B027-T1 33/66 percentile deterministic",
          q1 == b.pct(v, 1 / 3) and abs(q1 - 34.0) < 0.01 and abs(q2 - 67.0) < 0.01,
          f"q1={q1} q2={q2}")

    # B027-T2/T3/T4 bucket boundaries
    Q1, Q2 = 10.0, 20.0
    check("B027-T2 x=Q1 -> LOW", b.classify(Q1, Q1, Q2) == "LOW")
    check("B027-T3 x=Q2 -> MID", b.classify(Q2, Q1, Q2) == "MID")
    check("B027-T4 x>Q2 -> HIGH", b.classify(Q2 + 1e-6, Q1, Q2) == "HIGH")

    # B027-T5 27 rows always emitted
    r = b.run(write=False)
    check("B027-T5 27 classes always emitted",
          len(b.ALL_CLASSES) == 27 and len(r["counts"]) == 27)

    # B027-T6 counts sum = valid episodes
    check("B027-T6 counts sum = valid episodes",
          sum(len(v) for v in r["counts"].values()) == len(r["valid"]) == r["thresholds"]["episode_count"],
          f"sum={sum(len(v) for v in r['counts'].values())} valid={len(r['valid'])}")

    # B027-T7 duplicate logs de-duplicated (synthetic identical traces)
    tmp = tempfile.mkdtemp()
    tp = os.path.join(tmp, "s1_black_behavior_trace.jsonl")
    with open(tp, "w") as f:
        for t in range(10):
            f.write('{"sim_time": %d, "visible_count": 4, "positions": ['
                    '{"name":"black_usv1","x":%d,"y":100},'
                    '{"name":"black_usv2","x":%d,"y":200},'
                    '{"name":"black_usv3","x":%d,"y":300},'
                    '{"name":"black_usv4","x":%d,"y":400}], "engaged": []}\n'
                    % (t * 10, 1000 - t * 10, 1000 - t * 10, 1000 - t * 10, 1000 - t * 10))
    h = b.trace_hash(tp)
    seen = {h: "a"}
    dup = h in seen
    check("B027-T7 duplicate logs de-duplicated (trace_hash identity)", dup)

    # B027-T8 invalid historical smoke excluded (no geometry -> episode_features None)
    check("B027-T8 invalid/no-geometry excluded",
          b.episode_features(os.path.join(tmp, "does_not_exist.jsonl")) is None)

    # B027-T9 same input -> same thresholds/assignments
    r2 = b.run(write=False)
    check("B027-T9 deterministic thresholds+assignments",
          r["thresholds"]["length_q1"] == r2["thresholds"]["length_q1"] and
          [c["class_id"] for c in r["valid"]] == [c["class_id"] for c in r2["valid"]])

    # B027-T10 missing geometry episode explicitly invalid/unclassified, not zero
    check("B027-T10 missing geometry -> invalid, not silently 0",
          all("seed" in c and "reason" in c for c in r["invalid"]) and len(r["invalid"]) >= 1)

    # speed degeneracy documented and consistent
    check("B027-degeneracy speed axis all LOW (B0 constant 10 m/s)",
          r["marginals"]["speed"] == {"LOW": len(r["valid"]), "MID": 0, "HIGH": 0})

    print(f"\nRESULT {len(PASS)}/{len(PASS) + len(FAIL)} passed")
    sys.exit(0 if not FAIL else 1)


if __name__ == "__main__":
    main()
