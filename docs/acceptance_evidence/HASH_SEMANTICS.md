# Hash Semantics

Different hash fields in this repo mean DIFFERENT things. They MUST NOT be forced to
match. This document defines each field and its true source of computation.

## Definitions

| field | meaning | how computed | current value |
|---|---|---|---|
| `source_sha256` | sha256 of the CURRENT source file bytes | `sha256sum <file>` | W5 `agent_hybrid_v5.py` = `e823e7bed219f469…` |
| `legacy_source_sha256` | sha256 of the HISTORICAL frozen W5 agent file (before the inert W6 integration hook was added) | recorded constant in `coevolution_final/make_config_manifest.py:61` (`W5_LEGACY_FROZEN_HASH`) | `a7842b29c81cc567…` |
| `bundle_sha256` | directory-bundle hash over `*.py` (name+sha256), see `sha_dir()` in `coevolution_final/make_config_manifest.py:23` | `sha_dir(<dir>)` | **null for W5** — no bundle hash is defined for W5 |
| `skill_sha256` | sha256 of `skills/maritime_commander/SKILL.md` | `sha256sum` | `155b02019dc92c6e…` |
| `api_sha256` | sha256 of `hsystem/pomdp_api/main.py` | `sha256sum` | `c47686228557b79f…` |
| `git_commit` | git commit of the acceptance snapshot | `git rev-parse HEAD` | `5f19890a36a94fb9…` |

## Why W5 source and legacy hashes differ

`agent_hybrid_v5.py` (current file) = legacy frozen W5 policy + an INERT W6 integration hook
(`_w6_intercept` slot, None-default). Under a W5-only run the hook is never set, so the file is
**behaviorally identical** to the legacy frozen W5 that produced all prior baselines.
Source: `coevolution_final/make_config_manifest.py:63-66`, `coevolution_final/EXISTING_RESULTS_AUDIT.md:10`.

Therefore:
- `e823e7be…` = current runtime file sha256 (`W5_RUNTIME_FILE_HASH`)
- `a7842b29…` = legacy frozen policy hash (`W5_LEGACY_FROZEN_HASH`)
- These are BOTH valid for W5 but describe different artifacts. Do NOT unify them.

## white_harness_versions.jsonl

The `hash` field in this file is a per-version **harness version hash**. For W5 it equals the
legacy source hash `a7842b29…` (there is no directory bundle for W5). Only W6 versions carry a
separate `anti_evasion_dir_hash`. So `white_harness_versions.jsonl["W5"].hash` is NOT a
`source_sha256` and NOT a `bundle_sha256` in the strict sense; see the schema note below.

## Historical / stale records

- `SKILL_MD_SHA256.txt` (repo root) records a STALE skill hash `e1f7839a…`.
  Current skill hash `155b0201…` is in `SKILL_CURRENT_SHA256.txt`.
  The stale file is preserved for provenance; see `SKILL_MD_SHA256.txt.STALE.md`.
- `SKILL_MD_SHA256.txt` was NOT overwritten, per the "do not destroy historical evidence" rule.

## Acceptance source of truth

For acceptance, use `docs/acceptance_evidence/VERSION_MANIFEST.json` → `hashes` block:
`source_sha256`, `legacy_source_sha256`, `bundle_sha256` (null), `skill_sha256`, `api_sha256`, `git_commit`.
