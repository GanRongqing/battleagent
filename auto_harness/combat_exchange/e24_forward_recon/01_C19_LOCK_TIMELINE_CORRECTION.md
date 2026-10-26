# 01 — C19 LOCK TIMELINE CORRECTION (raw LOCK_TRACE)
Correction to the E23 summary: the 4 White kills of Black are **not** all at 11221 s. From
`UNIT_KILLED / faction=BLUE` in `/tmp/opencode/e23_lock_c19.jsonl`:
| engine_time | target (Black) |
|---|---|
| 11221 s | usv18 |
| 11311 s | usv12 |
| 11551 s | usv21 |
| 11641 s | usv9 |
Also: Black's 48 completed windows / 40 hits are **episode-cumulative**, not all before the first White
loss. Note: some chains complete **after the attacker died** (engine settles them); we distinguish
engine-counted kills vs attacker-alive hits where possible. **VERIFIED** from raw trace.
