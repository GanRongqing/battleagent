# 00 — ACE 12-Strategy N=2 Quick Generalization Eval (plan)

Set = OLD_LOCAL(4) + WAVE1(2, wang.rar) + WAVE2(6, 六个策略.zip) = 12.
White = ACE (frozen `agent_hybrid_allocator_expand.py`), LLM off, DETERMINISTIC_STEP_MODE=ON.
Seeds = 43001, 43002 (fresh). N=2/strategy → 24 episodes.

Opponent invocation:
- B0-B3 : scenario `scenario_composition` + `RW_CFG_FILE` profile field (B0_RANDOM/B1_MULTI_AXIS/
          B2_COORDINATED_PRESSURE/B3_ADAPTIVE); composition 20 white USV + 10 UAV vs 30 black.
- W1-1  : scenario `external_dispersed`   (分散式)
- W1-2  : scenario `external_twowave`     (两波次)
- W2-1..6: scenarios `横向编队-中央汇聚箭头突防`, `菱形编队-接近后扇形展开突防`,
          `菱形编队-两翼包抄中央突进`, `菱形编队-南北两翼镜像夹击`,
          `菱形编队-中央汇聚箭头突防`, `菱形编队-MUSV外侧绕行SUSV中央收缩`

Metrics: black kills + white USV losses from canonical `[META]`; CER=kills/losses;
pooled CER=Σkills/Σlosses; Exchange Win = kills>losses. UAV excluded from CER.
N=2 ⇒ descriptive only; no statistical generalization claims.
