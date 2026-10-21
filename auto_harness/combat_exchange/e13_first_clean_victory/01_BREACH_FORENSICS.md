# 01 — W2-5 BREACH FORENSICS (E13)

## Actual breachers (engine stdout, `base_server.log`)
- `BLUE.Ship.Ship.usv10突防成功！` and `BLUE.Ship.Ship.usv21突防成功！` — **two** units, in the same
  `update` call (same instant).
- Note discrepancy: `ended_reason` text says “敌方**1**艘艇突破防线”, while the engine printed **2** breach
  events. Clean Victory requires breakthrough==0, so the discrepancy does not change the Defeat verdict,
  but the printed count is authoritative for “who breached”.

## Their routes (offline truth, route-1; diagnosis only)
- usv10: (360.4,+105)@6 → (272.8,+55)@6 → (185.2,+55)@10 → (10,+55)@10  → **north inner lane y=+55 km**
- usv21: (360.4,−105)@6 → (272.8,−55)@6 → (185.2,−55)@10 → (10,−55)@10 → **south inner lane y=−55 km**
- Final leg accelerates to **10 m/s** from x≈185 km, so both are fast late dashers on opposite flanks.

## White state at the end
- 6 survivors, **static at x≈120 km, y between −142 and −73 km** (all on the SOUTH side), none locking,
  for the last ~8 min. No Black with x≤160 km appears in `active_enemies` near the screen in that window.
- usv10's logged active position stays near x≈306–316 km and usv21 near x≈288–298 km across hours
  (only ~10 km change) — either they hold then dash, or the reported positions are stale/held. This is
  flagged for instrumentation; the impact is that White has **no positioned track near the screen** to engage.

## Hypothesis (status)
- “Northern flank uncovered” — **PARTIALLY CONFIRMED**: the north lane (usv10 y=+55) has no White USV
  anywhere near (all survivors y≤−73). But the south lane (usv21 y=−55) was also not countered despite a
  survivor at y≈−73/x=120, i.e. **the endgame also fails to detect/engage the fast dasher**.
- Root cause is a **coverage + endgame-detection** combination, not a single north-flank gap.
  North gap: VERIFIED (no northern coverage). Endgame engagement failure: INFERRED (needs the
  observation/track trace at the final leg).
