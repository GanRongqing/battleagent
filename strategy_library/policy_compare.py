# -*- coding: utf-8 -*-
"""strategy_library/policy_compare.py — artifact/semantic/empirical novelty validator."""
import math
import statistics

from .policy_models import ValidationRecord


def compare_artifacts(man_a, man_b):
    a = man_a.get("bundle_hash") if isinstance(man_a, dict) else man_a.bundle_hash
    b = man_b.get("bundle_hash") if isinstance(man_b, dict) else man_b.bundle_hash
    return a is not None and a == b


def semantic_difference(card_a, card_b):
    diff = {}
    if card_a.get("strategy_family") != card_b.get("strategy_family"):
        diff["strategy_family"] = [card_a.get("strategy_family"), card_b.get("strategy_family")]
    ta, tb = card_a.get("declared_traits", {}), card_b.get("declared_traits", {})
    trait_diff = {k: [ta.get(k), tb.get(k)] for k in set(ta) | set(tb) if ta.get(k) != tb.get(k)}
    if trait_diff:
        diff["declared_traits"] = trait_diff
    return diff


def empirical_distance(fp_a, fp_b):
    """Standardized Euclidean over the intersection of available numeric features."""
    use = []
    for k in fp_a["behavior_features"]:
        if k in fp_b["behavior_features"] and fp_a["behavior_features"][k] and \
                fp_b["behavior_features"][k]:
            use.append(k)
    if not use:
        return None, [], use
    deltas = []
    for k in use:
        ma = fp_a["behavior_features"][k]["mean"]
        mb = fp_b["behavior_features"][k]["mean"]
        sd = math.sqrt((fp_a["behavior_features"][k]["std"] ** 2 +
                        fp_b["behavior_features"][k]["std"] ** 2) / 2) or 1.0
        deltas.append({"feature": k, "a_mean": round(ma, 2), "b_mean": round(mb, 2),
                       "delta": round(ma - mb, 2),
                       "normalized_delta": round((ma - mb) / sd, 3)})
    dist = math.sqrt(sum(d["normalized_delta"] ** 2 for d in deltas) / len(deltas))
    return dist, deltas, use


def validate(card_a, man_a, fp_a, card_b, man_b, fp_b, n_min=10):
    artifact_same = compare_artifacts(man_a, man_b)
    sem = semantic_difference(card_a, card_b)
    dist, deltas, used = empirical_distance(fp_a, fp_b)
    # multi-seed stable: require n>=n_min per side and finite distance
    na = fp_a["episode_count"]; nb = fp_b["episode_count"]
    suff = na >= n_min and nb >= n_min
    stable = bool(suff and dist is not None)
    if artifact_same:
        verdict = "IDENTICAL_ARTIFACT"
    elif not suff or dist is None:
        verdict = "INSUFFICIENT_EVIDENCE"
    elif dist < 0.2:
        verdict = "EMPIRICALLY_DUPLICATE"
    elif dist >= 0.2:
        verdict = "EMPIRICALLY_DISTINCT"
    else:
        verdict = "INCONCLUSIVE"
    return ValidationRecord(candidate_policy_id=card_a["policy_id"],
                            reference_policy_id=card_b["policy_id"],
                            artifact_same=artifact_same, semantic_difference=sem,
                            empirical_distance=round(dist, 4) if dist is not None else None,
                            feature_differences=deltas,
                            multi_seed_stable=stable,
                            multi_scenario_stable=None,
                            novelty_verdict=verdict,
                            evidence={"features_used": used, "n": [na, nb]})
