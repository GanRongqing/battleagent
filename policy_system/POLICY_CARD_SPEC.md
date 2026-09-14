# Policy Card Spec
Four separated concepts:
1. PolicyCard = DECLARED semantics (what the designer wants). Fields policy_id/version/side/
   strategy_family/declared_intent/trigger_and_switch/known_strengths/known_weaknesses/
   declared_traits/status/evaluation_role/parent/description. known_weaknesses must be
   non-empty or explicitly unknown. DECLARED != EMPIRICAL.
2. ArtifactManifest = what actually executed (entrypoint + hashes + deterministic bundle hash).
3. EmpiricalFingerprint = from tournament logs only (behavior_features, response_signature,
   feature_availability; missing => unavailable, never 0).
4. ValidationRecord = artifact/semantic/empirical/stability/novelty verdict.
Immutable policy_id: behavior change => NEW policy_id; metadata-only updates allowed in place.
Status: candidate/dev/validation/active/historical/sealed. evaluation_role decouples
"strong" from "valuable" (weak-but-failure_probe is pool-eligible).
