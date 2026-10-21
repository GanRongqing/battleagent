# 06 — E14 中文最终报告（终局时间线与结果归因审计）

## 一、三个核心问题
### Q1 为什么终局附近缺少有效定位？
**UNRESOLVED。** E13 的“突破者 usv10/usv21、末段 10m/s”证据来自 **w1=W2-4**，不是 W2-5。W2-5（w3）的
实际突破者在现有日志中**无法识别**（w3 的 base_server.log 没有突防打印，而 ended_reason 记为 1 艘）。
因此“W2-5 终局缺少定位是因为时间窗口不足”**不成立/未证实**。

### Q2 位置变化是连续还是口径跳变？
- W2-5 的 game log 中 26 个曾被定位的黑方位置随步进平滑变化；突破发生在终局最后一次 update。
- “两次突破 / 一次计数”的差异已被证明是**跨 episode/跨场景的日志误归因**，不是仿真状态跳变。
**（现象归因：VERIFIED；底层“为何 Agent 未定位”仍 UNRESOLVED。）**

### Q3 现有证据是否支持“时间窗口不够”？
**不支持。** E13 的时间窗结论建立在错误的突破者数据上，予以**降级为 UNRESOLVED**，不再作为修改 Agent 的依据。

## 二、终局计数核对（单位级退出）
| 类别 | 数量 | 依据 | 置信 |
|---|---|---|---|
| 黑方总数 | 30 | route1 usvNum | VERIFIED |
| 战斗击毁 | 27 | Agent [META] enemy_kills | VERIFIED |
| 突破 | 1 | ended_reason | VERIFIED（计数）/ 具体 ID UNRESOLVED |
| 终局存活 | 2 | 30−27−1（推断） | INFERRED |
| 从未被定位 | 4（usv1-4） | active 集合 | VERIFIED |

## 三、“两次突破 vs 一次计数”归因（VERIFIED 纠正）
- 两条 `usv10/usv21 突防成功` 打印位于 **w1 = W2-4**；W2-5 结果在 **w3**。E13 把 W2-4 的突破者当成了 W2-5。
- `tzb_engine` 用 `black_breakthrough = len(judge.black_success)`：同一次 `_judge` 中“打印即 append”，
  **不存在单局内“打印 2 次却计 1 次”的源码路径**。观察到的 2 条来自**不同场景/局**。
- W2-5（w3）**没有**突防打印，但 ended_reason 记为 1 艘 → 最可能是 worker/engine 重启时
  `base_server.log` 被截断（“w” 模式）而状态/对局日志保留。=> 该局突破者身份 **UNRESOLVED**。

## 四、其他日志口径
- 每个 worker 的 `POST /start` 出现 2 次 = 日志行 + uvicorn 访问行，**实际只有 1 次**。VERIFIED。
- 每个 worker 有两份 game log（如 031055/031059），内容一致（同 1317 步、同 reason），为**重复保存**。VERIFIED。
- Trace ON/OFF：E12 已证 W2-1 轨迹 `3cf09e4fd0a6` 在 ACE / C13 ON / C13 OFF 下完全一致。VERIFIED。

## 五、哪个软件问题已被证实 / 哪些假设被排除
- **已证实的工程问题（证据/归因层，不是战斗逻辑）**：worker 的 `base_server.log` 与 game log **缺少
  episode/scenario 标识**，且会因重启被截断；同一 worker 还会**重复保存 game log** —— 这直接导致了 E13 的
  跨场景误读。属**日志归属/可追溯性缺陷**，不是引擎计数 bug，也不是 Agent 战术 bug。
- **被排除**：单局内“打印 2 次 / 计数 1 次”的引擎计数错误（源码不支持）；“C13 静默无效是接线错误”
  （E12 已证是 `_threat_pos` 为空回退）；“C14 因覆盖不足失败”（C14 改变了覆盖与轨迹，结果不变）。
- **仍未解决**：W2-5 真实突破者身份；W2-5 终局“是否可拦截”；UAV 逐架损失路径；C10 一步群灭路径。

## 六、后续修复应在哪个组件
1. **评测/日志组件（优先，读-only 增强）**：`worker_runtime`/API 日志加 **episode_id + scenario + run_id**
   前缀；game log 去重；重启不截断历史（轮转文件）。这不是策略修改，能消除此类误归因。
2. **证据补全后再谈战术**：在不改引擎前提下，用带 episode 标识的日志重跑 W2-5 C10，定位真实突破者及其
   合法观测轨迹，再决定是否需要拦截/覆盖改动。在此之前**不修改 Agent**。

## 七、本轮不修改
- 未改黑方、战斗物理、武器雷达、裁判、突破线、评分、场景身份。
- 未做新的战术候选；未宣称任何胜利；E13 的“时间窗不足”已降级为 UNRESOLVED。
