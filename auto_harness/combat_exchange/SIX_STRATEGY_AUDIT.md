# Six Strategy Audit (combat_exchange)

Re-verified from the registered scenario/route (NOT filenames). Exactly **6** registered strategies.

| strategy_id | strategy_name | initial formation | route family | black USV | black UAV | speed | geometry |
|---|---|---|---|---|---|---|---|
| 1 | 横向编队-中央汇聚箭头突防 | horizontal | 中央汇聚 (路线1) | 30 | 0 | 6,10 | central convergence arrowhead |
| 2 | 菱形编队-接近后扇形展开突防 | diamond | 扇形展开 (路线4) | 30 | 0 | 6,10 | narrow approach → fan-out |
| 3 | 菱形编队-两翼包抄中央突进 | diamond | 两翼包抄 (路线3) | 30 | 0 | 6,10 | flank envelop + center thrust |
| 4 | 菱形编队-南北两翼镜像夹击 | diamond | 南北镜像 (路线2) | 30 | 0 | 6,10 | north/south mirror pincer |
| 5 | 菱形编队-中央汇聚箭头突防 | diamond | 中央汇聚 (路线1) | 30 | 0 | 6,10 | central convergence arrowhead |
| 6 | 菱形编队-MUSV外侧绕行SUSV中央收缩 | diamond | MUSV绕行 (路线5) | 30 | 0 | 6,10 | outer detour + center contraction |

Notes:
- White (red) = 20 combat USV + 10 UAV; Black (blue) = 30 combat USV (single unit type).
- All routes deterministic (fixed JSON waypoints); seed does not affect route.
- S1 (horizontal) vs S5 (diamond) share route 1 (中央汇聚) — formation is the only difference.

W5 frozen baseline (reused from six_strategy_w5_eval, seeds 11001/11002, LLM off):
- Overall pooled CER = 131 kills / 180 losses = **0.73**, exchange wins = 4/12.
