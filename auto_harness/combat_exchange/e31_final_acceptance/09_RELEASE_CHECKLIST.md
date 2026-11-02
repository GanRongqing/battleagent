# 09 — RELEASE CHECKLIST
| Gate | requirement | status | evidence |
|---|---|---|---|
| A Identity | 13/13 valid, same engine/source | **PASS** | results_13.jsonl; EngineHash a509457250bc2799 |
| B Positive exchange | 13/13 Official CER>1 | **PASS** | 03/04/05 CSVs |
| C Boundary safety | white USV/UAV AREA_OUT = 0 | **PASS** | engine AREA_TRACE: 0 white USV, 0 white UAV |
| D Legal observation | only obs + public map; no scenario/ID/seed branch | **PASS** | code inspection; public_area channel |
| E Reproducibility | commands + hashes + logs | **PASS** | 01 manifest, raw_logs, accept.sh |
| F No tactical modification | tactics unchanged | **PASS** | 13/13 K/L identical to E30; only neutral counters |
=> **C31 RELEASE ACCEPTED**
