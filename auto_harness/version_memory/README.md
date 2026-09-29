# Mechanism-Level Version Memory

Sidecar metadata + tooling that stores **experience** for each code candidate independently of the
code itself. **Does not touch any runtime agent.** No W5/ACE/C2 file is modified.

Principle: *code version != experience*. Each generation keeps a structured record:

```
Failure Pattern -> Root Cause -> Mechanism -> Applicability -> Code Scope -> Evidence -> Outcome -> Confidence -> Limitations
```

## Layout
```
version_memory/
  schema/        mechanism_card.schema.json, version_manifest.schema.json
  cards/W5|ACE|C2/   MECHANISM_CARD.json, VERSION_MANIFEST.json, CODE_DIFF.patch, SEMANTIC_DIFF.md
  tools/         build_mechanism_card.py, build_semantic_diff.py, validate_card.py, compare_versions.py
  tests/         test_version_memory.py
  VERSION_LINEAGE.md
```

## Default mode
Sidecar only. Nothing here is imported by any agent.
