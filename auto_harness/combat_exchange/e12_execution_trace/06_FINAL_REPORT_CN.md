# 06 — E12 中文总结（执行追踪与评测完整性审计）

## 核心结论
1. **C13 为何无效果（VERIFIED）**：C13 的 `ThreatAwareUAVManager` **确实被安装并调用**，但其
   `_global_search_fly` **每次都走了回退分支**（`not self._threat_pos`）。证据：C13 轨迹中
   base `global_search` 调用 **1116 次**、`c13_global_search` **0 次**；ACE 与 C13 的候选中心与动作完全一致。
   原因是 **W2-1 在全局搜索时几乎没有定位到的敌舰航迹**（正是 C13 想解决的场景），威胁集合为空 → 直接回退
   到原逻辑。**不是接线失败**，`_global_search_fly` 被调用了 1116 次。
2. **Debug ON/OFF 行为一致（VERIFIED）**：ACE、C13(trace ON)、C13(trace OFF) 的 W2-1 轨迹哈希均为
   `3cf09e4fd0a6`。instrumentation 无副作用。
3. **死亡事件完整性（VERIFIED）**：UAV 存活→死亡状态转移数与“被击毁”事件数一致（10=10，C10/ACE/W2-5/W2-6）。
4. **Clean Victory（VERIFIED 无）**：三个样例均为“突破”判负，Clean Victory=False；未改裁判顺序。
5. **跨版本纠错（VERIFIED）**：E11 的“10 架 UAV 同一步在 12–30km 被击毁”是 **C10** 的现象；ACE/C13 的
   UAV 是**逐个**在 04:17–04:42 损失。C13 不应据此被评判。
6. **未证实假设**：W2-5 北翼空档 = **INFERRED**；C10 一步群灭 UAV 的精确路径 = **UNRESOLVED**；
   ACE/C13 逐架 UAV 进入敌包线的具体角色/动作路径 = **UNRESOLVED**。

## 观察性增量
- 新增只读 UAV 执行追踪（`UAV_TRACE`，默认关闭）：每步记录 mission/uav_alive、`_global_search_fly`
  调用与候选、C13 分支的 `nthreats/nsafe/center`。行为中性。
- 未修改 Agent 决策、战斗物理、裁判、评分；未改默认 flags；保留 E9–E11 证据。

## 验收
- 无 Victory（如实报告）。C13 仍为 **NO_EFFECT**，不得标记成功。
- 下一步（精确）：把逐架 UAV 的 **role / action / 最近黑方距离 / track 可见性** 全量记录（已在本轮原型），
  定位 ACE/C13 逐架损失与 C10 群灭的真实路径后，再实施 UAV 安全间距；并单独用离线真值视图确认 W2-5 北翼假设。
