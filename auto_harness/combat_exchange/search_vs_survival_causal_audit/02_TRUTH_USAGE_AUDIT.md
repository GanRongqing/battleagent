# Truth Usage Audit

- Truth/observed data read ONLY from existing agent stdout logs (vis/lost/engaged counts) — these are
  the agent's own legal-observation aggregates, not raw truth.
- No simulator truth was injected into TrackManager/Allocator/Controller/ActionSafety/ACE.
- No runtime path reads diagnostic truth. No diagnostic logger added (so no side-effect risk).
- No oracle invented. Policy files untouched (ACE sha 7527253c… unchanged).
