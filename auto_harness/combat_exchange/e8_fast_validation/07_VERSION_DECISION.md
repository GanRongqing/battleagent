# 07 — VERSION DECISION
## Frozen validation candidate
**ACE + `LIFECYCLE_HANDOFF_V1=1`** (`OBS_TI_REVIVE=0`, `TARGET_LIFECYCLE_V2=0`).
Rationale: E7 evidence is valid and clean (W2-6 1.077, W2-4 2.400); it is the simplest candidate;
C10's incremental value could not be assessed (invalid pair).
## Not promoted
- `GLOBAL_DEFAULT` NOT changed; all flags remain default **OFF**.
- C10 + E7: not promoted (INCONCLUSIVE).
- C11: DROP (unchanged).
## Risks to carry into fresh-RNG validation
1. W2-2 may regress (0/20) — must be re-tested with a proven-separated scenario.
2. W2-6 margin is small (1.077) and from a single deterministic trajectory.
3. C10 incremental value unknown (needs a clean re-run).
4. The global `_KILLED` has no cross-episode reset (latent); the E8 multi-job run also exposed a
   scenario-separation issue that must be fixed in the runner before multi-strategy panels.
