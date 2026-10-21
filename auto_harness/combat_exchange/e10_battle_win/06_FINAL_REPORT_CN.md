# 06 — E10 最终交付报告（中文）

## 真实胜负规则
见 `01_VICTORY_CRITERIA.md`：**击毁全部黑方且无突破 = Victory**；任何“突破”或白方全灭 = Defeat。
E9/E10 六场景**全部为 Result.Defeat**（多为黑方 1–2 艘突破）。CER 仅作诊断，不是胜利。

## 诊断（W2-1 / W2-2，E9 已验证身份轨迹）
- **W2-1**：首次雷达接触 6780s（仅 4 目标）；**10 架 UAV 在 ~14880s 前全部被击毁**；随后长期
  `MISSION=GLOBAL_REACQUIRE`，USV 保持 x=120km 静态屏列；来袭黑方仅剩 passive 方位（绝对方位），
  **从未形成 own-lock**，27150s 起被逐一击毁，29730s 全灭。→ 主因 **Observation Failure（前出传感器过早损失）**，
  次因 **GLOBAL_REACQUIRE 静态屏列 / 重搜不动**。
- **W2-2**：首次 own-lock 6870s，仅 3 目标被定位，19 死、2 突破 → **交战窗口/覆盖不足**。
- 对照：W2-4（14 存活）、W2-5（27 杀、仅 1 突破）说明交战充分时白方可接近胜利。

## 已实施的战术修复：C12 BEARING_GUIDED_REACQUIRE
`agent_hybrid_bearing_reacquire.py`（white-combat-0012-v1，parent ACE）。唯一机制：`GLOBAL_REACQUIRE`
下，收到 passive 方位告警的可用 USV 沿该**绝对方位**前出 80km 定位，替代静态屏列。仅用合法观测，无真值/场景标签，
不改锁定/武器/黑方。非该任务态时与 ACE 完全一致。

## 成绩（seed 43001，全部 Layer-1/2/3 身份通过）
| 场景 | ACE K/L (CER) | C12 K/L (CER) | 变化 |
|---|---|---|---|
| W2-1 | 0/20 (0.000) | 0/20 (0.000) | 0 |
| W2-2 | 4/19 (0.211) | **7/19 (0.368)** | **+0.157** |
| W2-3 | 15/13 (1.154) | **16/13 (1.231)** | **+0.077** |
| W2-4 | 12/6 (2.000) | 12/6 (2.000) | 0 |
| W2-5 | 16/15 (1.067) | 16/15 (1.067) | 0 |
| W2-6 | 10/18 (0.556) | **13/15 (0.867)** | **+0.311** |
| 汇总 | 57/91 = 0.626 | **64/88 = 0.727** | **+0.101** |

## 结论
- **已解决**：C12 在 W2-2/W2-3/W2-6 带来真实提升，汇总交换比 0.626→0.727，且未造成任何场景回退；
  身份校验 6/6 通过。统一 C12 汇总（0.727）与最强旧统一版本 C10（0.725）相当，但更简单且改善弱场景。
- **未达到**：**W2-1 仍 0 击毁（0/20）**；六场景仍全部为任务 Defeat（黑方突破未根除）。因此
  **没有实现“全场景任务胜利”**，也没有场景达成 Victory。
- **能力回退**：无（W2-4/W2-5 持平，其余不降）。

## W2-1 未解决根因与下一步
根因是**前出传感器（UAV）在交战前即被全部击毁**，白方随后只能拿到被动方位，无法形成定位航迹/锁定
（并叠加可能的探测-锁定距离不对称）。下一步（未实施）：
1. UAV 生存/戒备：保持对已探测黑方的安全间距、避免深入被击毁，维持前出雷达覆盖；
2. 更早的 UAV 前出与方位引导搜索（把 C12 的方位引导同样用于 UAV）；
3. 若引擎存在白方锁定距离短于黑方的硬性不对称，则需在**不改引擎**前提下以编队/数量/先敌发现弥补，并如实标注上限。

## 代码与复现
- 新增：`agent_hybrid_bearing_reacquire.py`；`run_agent_wrapper.py` 增加 `bearing`；`parallel_runner.POLICY` 增加 `C12`。
- 未改：ACE/C10/C11/Engine/Black/裁判/评分；未改默认 flags（全部 OFF）；未覆盖 E9 及历史数据。
- 启动/评测（确定性，身份校验）：
```
LIFECYCLE_HANDOFF_V1=0 OBS_TI_REVIVE=0 TARGET_LIFECYCLE_V2=0 \
python auto_harness/evaluation/parallel_runner/parallel_runner.py \
  --strategies W2-1,W2-2,W2-3,W2-4,W2-5,W2-6 --seeds 43001 --policies C12 \
  --workers 6 --epoch E10 --run-id <RUN>
python auto_harness/combat_exchange/e9_evaluation_recovery/scripts/verify_identity.py <RUN> <SID> C12
```
- Git commit：见本轮提交。
