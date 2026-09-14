# White Harness Phase 1 — Design (anti-leak containment)

Inherits: W5 frozen execution; W6 allocator/execution decoupling (execution_override=false);
W7 lesson (no broad heuristic search); Phase0 N=100 evidence (single leak / containment gap).

## Change surface
ThreatAllocator overlay only (WHO/WHAT/TARGET). No USVController / BT / ActionSafety /
weapon / lock / physics / sensor changes. execution_override = false.

## Mechanisms
M1 crossing-risk estimator (legal track belief -> ETA to BREAK_X; LOW/MED/HIGH/CRITICAL).
M2 effective boundary blocker checker (boundary-side or intercept-feasible assigned USV).
M3 minimal containment assignment (one blocker: free -> bounded preemption; TTL 900s hysteresis).
Runtime audit (env W8_AUDIT_LOG): per-call crossing risk, blocker counts, selection, preemption.

## Candidate
white-auto-0001-v1, family anti_leak_containment, parent W5, deterministic (no LLM commander).
Entry point agent_hybrid_w8_containment.py. Bundle hash in ANTI_LEAK_ARTIFACT.json.

## Lifecycle
candidate -> dev -> validation -> active only after DEV + fresh + cross-opponent pass.
