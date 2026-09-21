# Hash Conflict Audit

| source file | claimed artifact | claimed hash | current actual hash | match | interpretation |
|---|---|---|---|---|---|
| SKILL_MD_SHA256.txt | skills/maritime_commander/SKILL.md | e1f7839ac1a820dc… | 155b02019dc92c6e… | NO | historical skill hash; SKILL.md changed since |
| white_harness_versions.jsonl | W5 | a7842b29c81cc567… | (agent_hybrid_v5.py) e823e7bed219f469… | NO | jsonl records a harness-bundle hash, not the current file sha256 |
| docs/acceptance_evidence/VERSION_MANIFEST.json | agent_hybrid_v5.py | e823e7bed219f469… | e823e7bed219f469… | YES | current acceptance hash (source of truth) |

## Rule
The **current acceptance hash** is the one computed this round into VERSION_MANIFEST.json / HASHES.sha256.
Historical hashes in reports/jsonl are version history and MUST NOT be presented as the current frozen hash.
