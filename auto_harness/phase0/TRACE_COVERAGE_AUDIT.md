# W5 Failure Corpus — Trace Coverage Audit (READ-ONLY)

Sampled W5 episode log (logs show): per-step lines `[t=...] step= | USV/uav/TRACKS/KILL/INTENT`,
`[ASSIGN]`, `[RELEASE]`, `[DETECT]`, and a final `[META]`. GameMetricsCollector ran for
exploration. No dedicated per-decision diagnostic dump exists for W5 (the W6 shadow/replay
dumps are W6-only and decision-neutral).

already_available (derivable from W5 logs + META + collector):
- outcome/clean/breakthrough/kills/losses/resolution/exploration, first_detection
- USV alive count over time (death time ~ first step the count drops) -> friendly death timeline
- DETECT/ASSIGN/RELEASE events with sim-time context (coarse detection/reacquire proxies)
- TRACKS vis/lost/engaged per step (lost-track windows, engaged counts)
- KILL progression; TOP target lines

missing (needs_derived / needs_new_logging):
- per-target offline truth (which target broke through, exact position/route) -> needs an
  offline diagnostic parser on top of the game log text only (no new White-side logging),
  marked offline_only=true where inferred (e.g., breakthrough target = the non-killed ship).
- high-risk zero-interceptor duration & reacquire latency: needs_derived_metric from
  ASSIGN/RELEASE + TRACKS (approximation) — not a new White policy hook.
- No new White runtime logging required: per-episode logs already carry the timeline; we add a
  read-only corpus runner that stores each log and parses it offline.

Conclusion: adequate for a deterministic failure miner on episode-level + coarse timeline
features; no White-side code modification is needed (keeps frozen W5 byte-identical).
