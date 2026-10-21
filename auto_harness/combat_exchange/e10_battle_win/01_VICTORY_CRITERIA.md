# 01 — 真实胜负判定（源码：hsystem/pomdp_api/main.py::_build_result 1231-1280）
| 条件（engine `ended_reason`） | 结果 |
|---|---|
| “敌方所有…击毁” / “敌方…击毁” | **Victory** |
| “我方所有…” 或 含“突破” | **Defeat** |
| 白方 USV+UAV 全灭 | Defeat |
| 白方 USV 全灭 | Defeat |
| 否则按 env 综合得分（>0 胜 / <0 负 / =0 平） | Victory/Defeat/Tie |

黑方突破判定：`judge_system._judge` 中 black_ship `coords[0] <= destination(50_000)` → 记为突破并 kill。
=> **正式任务胜利 = 击毁全部黑方且无突破**；任何一艘黑方突破即判负，与 CER 无关。
E9 六场景全部为 `Result.Defeat`（W2-1 我方全灭；W2-2/W2-4 敌方突破 2；W2-5 突破 1；W2-3/W2-6 亦突破）。
CER/击毁/损失仅作诊断，不得冒充任务胜利。
