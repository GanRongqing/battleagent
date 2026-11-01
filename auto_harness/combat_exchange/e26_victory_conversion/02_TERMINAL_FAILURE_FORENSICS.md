# 02 — TERMINAL FAILURE FORENSICS (C27, `/result` reason)
| scenario | terminal | result_reason | K/L |
|---|---|---|---|
| W2-1 | Defeat | 敌方3艘艇突破防线 | 16/5 |
| W2-2 | **Victory** | 敌方所有单位被击毁 | 30/8 |
| W2-3 | Defeat | 敌方1艘艇突破防线 | 12/10 |
| W2-4 | Defeat | 敌方1艘艇突破防线 | 10/8 |
| W2-5 | Defeat | 敌方2艘艇突破防线 | 16/9 |
| W2-6 | Defeat | 敌方1艘艇突破防线 | 14/11 |
**All five Defeats are Black breakthroughs** (not timeout / not White-wipe / not other). VERIFIED from
`result_reason`. Exact breach timestamps/IDs: BREACH_TRACE was not enabled on the C27 run → **NOT_MEASURED**
(counts VERIFIED). Earliest actionable node = the 1–3 unengaged Black reaching x<=50 km before being
killed; White no-target USVs press east, leaving the western breakthrough line open.
