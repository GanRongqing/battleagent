# 04 — “两次突破 vs 一次计数”归因
## Finding: the two breach prints belong to a DIFFERENT scenario (W2-4), not W2-5. VERIFIED
- In run `e9_B_c10_off`, the two `BLUE.Ship.Ship.usv10/usv21突防成功！` lines are in **w1**, whose game log is
  **W2-4 (菱形编队-南北两翼镜像夹击)**. They are **not** from the W2-5 episode.
- E13's “breachers usv10/usv21” was therefore a **cross-worker / cross-episode misattribution**. VERIFIED.
## W2-5 (w3) has NO breach print, despite `ended_reason=敌方1艘艇突破防线`. UNRESOLVED
- `tzb_engine` sets `black_breakthrough = len(judge.black_success)` and the reason from it; `judge._judge`
  appends + prints in the destination branch. A breach with no print is inconsistent, most likely because the
  worker's `base_server.log` was rewritten (truncated) by a worker/engine restart, losing the print while the
  game log/state survived. The actual W2-5 breacher identity is therefore **UNRESOLVED**.
## Engine counting itself: no 2-vs-1 bug found. VERIFIED (within one episode)
- `black_breakthrough` is a strict count of `black_success` entries; there is no code path that can print a
  breach without appending it (same loop). So a genuine single-episode “2 printed / 1 counted” is not
  supported by the source; the observed pair came from two different episodes/scenarios.
## Other log artefacts
- 2 `POST /start` per worker = the formatted log line + the uvicorn access line (one real start). VERIFIED.
- 2 game logs (`031055`, `031059`) are duplicate saves of the **same** episode (identical 1317 steps and
  reason). VERIFIED.
