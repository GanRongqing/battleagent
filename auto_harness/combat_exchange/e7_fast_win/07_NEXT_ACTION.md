# 07 — NEXT ACTION
1. Keep `LIFECYCLE_HANDOFF_V1=0` as default until human review (do not promote silently).
2. If approved: run a fresh-epoch evaluation (independent RNG draws) of ACE with HANDOFF=1 across
   W2-6/W2-4/W2-2 to test whether `W2-6 > 1` and W2-4 stability reproduce.
3. Only after that consider promoting; do not generate C12 from this line.
4. Also fix the global `_KILLED` cross-episode reset (documented in E6) as part of hardening.
