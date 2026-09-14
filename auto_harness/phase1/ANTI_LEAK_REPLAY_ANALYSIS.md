# Anti-Leak Offline Replay (proxy, corpus 6001-6100)

- failures=35 clean=65
- failure trigger coverage (HIGH proxy): 1.0
- failure trigger coverage (CRITICAL proxy): 0.343
- clean false-trigger rate (HIGH proxy): 0.431
- clean false-trigger rate (CRITICAL proxy): 0.077
- median actionable lead (first HIGH-proxy step): 20793 s
- mean unblocked-high steps: fail 6.2 vs clean 1.54

PROXY: no per-step White USV positions in corpus; risk uses boundary proximity and engaged==0 as the unblocked proxy. Mechanism sanity only, not outcome proof.