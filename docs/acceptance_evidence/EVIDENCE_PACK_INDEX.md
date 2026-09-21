# Evidence Pack Index

Index of `docs/acceptance_evidence/`. This pack was produced for tutorial
《Harness 策略系统运行、集成与升级教程 v1.0》.

Legend:
- **verified** = value confirmed against current source or a real run this round.
- **live-derived** = captured from a live process/session this round.
- **derived** = computed/summarized from source or artifacts (not a live capture).
- **static** = reference text authored this round (no runtime capture).

| file | purpose | source | verified/live-derived | status |
|---|---|---|---|---|
| README.md | pack overview + index | authored | static | COMPLETE |
| EVIDENCE_PACK_INDEX.md | this file | authored | static | COMPLETE |
| VERSION_MANIFEST.json | frozen artifacts + git + env manifest | source hashes + git | verified | COMPLETE |
| HASHES.sha256 | sha256 of frozen artifacts | source files | verified | COMPLETE |
| HASH_CONFLICT_AUDIT.md | historical vs current hash conflicts | SKILL_MD_SHA256.txt, white_harness_versions.jsonl | verified | COMPLETE |
| HASH_SEMANTICS.md | field semantics (source vs bundle vs skill) | source + audit | verified | COMPLETE |
| ENVIRONMENT_REPORT.md | interpreter/OS/env facts | live env | live-derived | COMPLETE |
| pip_freeze.txt | installed package snapshot | live env | live-derived | COMPLETE |
| environment_export.yml | conda env export | live env | live-derived | COMPLETE |
| DEPENDENCY_AUDIT.md | imports vs requirements | source + imports | verified | COMPLETE |
| DEPENDENCY_FIX_REPORT.md | requirements fix + smoke | source + smoke | verified | COMPLETE |
| requirements-acceptance.txt | minimal acceptance deps snapshot | derived | derived | COMPLETE |
| PUBLIC_REPO_SECRET_AUDIT.md | credential scan (no hardcoded secrets) | source scan | verified | COMPLETE |
| ARCHITECTURE_SOURCE_MAP.md | components + line numbers | agent_hybrid_v5.py | verified | COMPLETE |
| RUNTIME_PATH_STATUS.md | 10 runtime-path questions | source | verified | COMPLETE |
| DECISION_AUTHORITY.md | WHO/WHAT/TARGET/HOW ownership | source | verified | COMPLETE |
| API_REFERENCE.md | endpoint list + line numbers | pomdp_api/main.py | verified | COMPLETE |
| API_VERSION_AUDIT.md | v1 vs v2 API | source | verified | COMPLETE |
| BACKEND_STARTUP_REFERENCE.md | backend CLI args + start | base_server.py | verified | COMPLETE |
| RUNTIME_COMMANDS.sh | start/health/run/stop commands | authored | static | COMPLETE |
| HEALTH_CHECK.json | live /health sample | live API | live-derived | COMPLETE |
| SCRIPTS_SAMPLE.json | live /scripts sample | live API | live-derived | COMPLETE |
| STATUS_SAMPLE.json | live /status sample | live API | live-derived | COMPLETE |
| LEGAL_ACTIONS_SAMPLE.json | live /legal_actions sample | live API | live-derived | COMPLETE |
| OBS_SAMPLE.txt | live /obs sample | live API | live-derived | COMPLETE |
| SINGLE_EPISODE_RUN.md | canonical W5 episode result | live run seed1001 | live-derived | COMPLETE |
| run/single_episode_result.json | machine result of episode | live run | live-derived | COMPLETE |
| run/logs/S2_B0_RANDOM_s1001.log | full agent stdout | live run | live-derived | COMPLETE |
| LLM_OFFLINE_SMOKE.md | LLM-off completion proof | live run | live-derived | COMPLETE |
| TEST_INVENTORY.md | test catalog | test files | verified | COMPLETE |
| TEST_REPORT.md | core test run results | live test run | live-derived | COMPLETE |
| LOGGING_REFERENCE.md | log locations + authority | source/artifacts | verified | COMPLETE |
| METRIC_SOURCE_OF_TRUTH.md | canonical metric definitions | source/ledger | verified | COMPLETE |
| RUNTIME_A_TO_F_EXAMPLE.md | A-F audit artifact example | runtime_audit | live-derived | COMPLETE |
| SINGLE_TARGET_TRACE.md | real detect->assign->kill chain | episode log | live-derived | COMPLETE |
| STRATEGY_LIBRARY_ACCEPTANCE.md | policy system acceptance | strategy_library/ | verified | COMPLETE |
| POLICY_REGISTRY_SNAPSHOT.json | registry DB snapshot | strategy_library.db | live-derived | COMPLETE |
| SKILL_ACCEPTANCE.md | skill hash + history | skills/ | verified | COMPLETE |
| AUTO_HARNESS_INVENTORY.md | phase inventory + outcomes | auto_harness/ | verified | COMPLETE |
| CASE_STUDY_ANTI_LEAK.md | white-auto-0001-v1 case | phase1 artifacts | verified | COMPLETE |
| CASE_STUDY_MEASUREMENT_CORRECTION.md | proxy refutation case | phase3/4/5 | verified | COMPLETE |
| MARL_INTEGRATION_REFERENCE.md | MARL integration point | authored/source | static | COMPLETE |
| BT_INTEGRATION_REFERENCE.md | BT status + boundary | authored/source | static | COMPLETE |
| SCENARIO_REPRODUCIBILITY.md | scenario/seed reproduction | source | verified | COMPLETE |
| EVALUATION_COMMANDS.md | eval command catalog | authored | static | COMPLETE |
| CLEAN_ROOM_READINESS.md | fresh-machine checklist | authored | static | COMPLETE |
| KNOWN_ISSUES.md | known issues table | artifacts | verified | COMPLETE |
| ACCEPTANCE_GAP_REPORT.md | what is NOT verified | authored | static | COMPLETE |
| GIT_STATE.md | git repo/remote/commit facts | git | live-derived | COMPLETE |
| LOCAL_ONLY_OR_UNPUSHED.md | local-only work list | git + filesystem | verified | COMPLETE |

## Totals
- Top-level files: 45
- `run/`: 2 files (log + result JSON)
- Pack size: ~296 KB
