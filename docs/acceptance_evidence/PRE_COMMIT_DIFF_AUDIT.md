# Pre-Commit Diff Audit (Stage 1)

Audited in the git mirror (`githsysys`, branch `main`), which is the actual git repo.

## `git diff --stat` (tracked files)
```
 hsystem/requirements.txt | 5 +++++
 1 file changed, 5 insertions(+)
```
The only tracked-file change is an ADDITIVE dependency edit (no deletions).

## File classification

| category | files |
|---|---|
| DEPENDENCY | `hsystem/requirements.txt` (added fastapi/uvicorn/pydantic; existing deps preserved) |
| DOCUMENTATION | `README.md`, `SKILL_MD_SHA256.txt.STALE.md`, all `docs/acceptance_evidence/*.md` |
| ACCEPTANCE_HELPER | `scripts/acceptance/import_smoke.py`, `scripts/acceptance/run_single_w5.py`, `scripts/acceptance/collect_hashes.py` |
| HASH_METADATA | `SKILL_CURRENT_SHA256.txt`, `docs/acceptance_evidence/VERSION_MANIFEST.json`, `docs/acceptance_evidence/HASH_SEMANTICS.md`, `docs/acceptance_evidence/HASH_CONFLICT_AUDIT.md` |
| EVIDENCE | `docs/acceptance_evidence/*.json` (samples/snapshot), `*.sh`, `run/single_episode_result.json`, `run/logs/S2_B0_RANDOM_s1001.log` |
| BEHAVIOR_CODE | **NONE** |

## Behavior-code gate
- No changes under `agent_hybrid_v5.py`, `TrackManager`, `ThreatAllocator`, `USVController`,
  `UAVManager`, `ActionSafety`, weapon/radar/physics/judge.
- W5 source sha256 before == after == `e823e7bed219f4693aa778a838df1400c161f8e7e44001502e5bceb0ae804252`.

**BEHAVIOR_CODE = NONE -> gate PASS.**

## Exclusions verified
- No `__pycache__/`, `*.pyc`, `*.db`, `*.sqlite*`, pid files, `/tmp` content.
- No secrets: `.env.example` `ANTHROPIC_AUTH_TOKEN=` is empty; no token strings in new files.
- No large raw logs (only the 24 KB single-episode agent log, part of evidence).
