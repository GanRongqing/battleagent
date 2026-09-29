# external_opponent_import/ — External Black Opponent Import Pipeline

State machine (STRICT):
```
NO FILES -> WAITING_FOR_EXTERNAL_ARTIFACTS
FILES    -> STATIC_AUDIT
count != 5+6 -> INCOMPLETE_EXTERNAL_DELIVERY (STOP)
count == 5+6 -> BLACK_IDENTITY_VALIDATION
identity unclear -> QUARANTINE (STOP)
11/11 static PASS -> 11 SMOKE episodes (seed e.g. 41001, deterministic ON)
smoke fail -> FIX ADAPTER ONLY -> rerun failed smoke
11/11 smoke PASS -> FREEZE ARTIFACTS
freeze complete -> RUN 75-EPISODE ACE GENERALIZATION (N=5, fresh panel e.g. 42001-42005)
```

Hard rules: never execute unknown external code before static audit; never copy external files into the
production registry; never modify ACE/Frozen W5/existing Black identities; never substitute unrelated
strategies (B4 mix, White plans, AUTO1, dispersed, two-wave) to reach 15.

Layout: `schemas/` (JSON schemas), `tools/` (pipeline scripts, read-only until smoke), `templates/`,
`tests/`, `BLACK_POLICY_CONTRACT.md`, `external_wave_registry.json` (sandbox registry — production
`strategy_library.db` is NOT touched at this stage).
