# 13 — First-Divergence Cases

Proxy-timeline from per-step agent logs (per-target persistence / HP / lock-legal transitions are
**NOT_MEASURED** — not present in the frozen-agent logs; no instrumentation added).

Selected episodes (ROBUST_WIN): W2-2 seed43001, W2-4 seed43001.
Selected episodes (ROBUST_LOSS): W2-1 seed43001, W2-6 seed43003.

| t-transition (proxy) | WIN (W2-2/W2-4) | LOSS (W2-1/W2-6) | diverge? |
|---|---|---|---|
| t0 first detection (vis>0) | early | early | no |
| t_first_engagement (engaged>0) | ~6.9k s | ~12.3k s | **YES — LOSS starts ~1.8x later** |
| t_first_lock (lock>0) | ~6.9k s | ~6.6k s | no (similar) |
| peak visible tracks | 16.4 | 7.35 | **YES — LOSS sees ~half** |
| active-engagement fraction | 0.198 | 0.075 | **YES (2.6x)** |
| final kills | 19.5 | 7.3 | YES |
| USV alive at end | 9.2 | 1.2 | **YES — LOSS wiped** |

## Answer: where does failure start?
The **earliest** divergence is at **DETECTED → PERSISTENT/ACTIONABLE → ENGAGED**: the LOSS
strategies (enemy converges centrally / MUSV flanks outside) keep roughly **half the visible
tracks** and form the first engagement **~1.8x later**, then hold engagements/locks only ~1/3 as
often. Kill collapse (7.3 vs 19.5) and the near-total USV wipe (1.2 vs 9.2) follow **after** this
front-funnel deficit. So a **front-of-funnel (track/engagement-formation)** deficit is the earliest
signal, with a **survival collapse** as the dominant downstream magnitude.
