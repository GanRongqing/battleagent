# Public Repo Secret Audit

Scope: working tree (`/root/autodl-tmp/hsystem`), excluding `.venv/`, `__pycache__/`,
`hsystem/pomdp_api/api_logs/`, `docs/acceptance_evidence/`.

| file | line | secret_type | severity | redacted_preview |
|---|---|---|---|---|
| run_formal_eval.py | 72-79 | ANTHROPIC_AUTH_TOKEN (env read from ~/.cline/data/secrets.json) | INFO | `os.environ.get("ANTHROPIC_AUTH_TOKEN")` / `secrets.get("deepSeekApiKey")` |
| run_priority_eval.py | 77-85 | same pattern | INFO | env/user-home read |
| config_backup/agent_llm_v1.py | 18 | `DS_KEY = os.getenv("ANTHROPIC_AUTH_TOKEN","")` | INFO | env read |
| config_backup/agent_llm_v1.py | 84 | `"x-api-key": <variable>` | INFO | header uses variable, not literal |

## Verdict: PASS (no hardcoded credentials found)
- No literal API keys / tokens / private keys are committed.
- LLM eval scripts read the key from the user home `~/.cline/data/secrets.json` (or env),
  which is OUTSIDE the repo.
- **W5 stable runtime does not need any secret** when `LLM_ENABLED=false`.

## Notes
- `api_logs/games/*.json` may contain runtime payloads; not scanned here (excluded, large).
- Do not commit `~/.cline/data/secrets.json` or any `.env` with tokens.
