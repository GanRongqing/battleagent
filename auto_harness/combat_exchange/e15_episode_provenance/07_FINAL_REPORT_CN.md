# 07 — E15 中文最终报告（Episode 归属修复与失败定位）

## 必答问题
1. **W2-5 实际突破者是否确认？** **是，已确认：`usv4`**（北侧内线，突破 t=39492s，x=49,995m，y=+115,000m）。依据为带 episode 标识的 `BREACH_TRACE`。
2. **真实失败节点是否定位？** **是：观测/航迹形成（Observation / Track）**。usv4 全程 **0 次雷达定位接触**，仅 **10 次被动方位**（首 02:34）→ TrackManager 无定位航迹 → 未分配、未锁定、未交战。属最早环节，先于分配/控制/合法性。
3. **27 kills 中有多少可确认是 Combat Kills？** 依源码，突破单位在下一 `_judge` 死亡清理里也被计入 `black_killed`；本局 **27 包含 1 次突破** ⇒ **26 Combat Kills + 1 Breakthrough**（越界移除未单独记录 = NOT_MEASURED）。
4. **日志串线/覆盖问题是否消除？** **已消除（本轮范围内）**：新增 episode 标识的突破诊断、唯一 episode_id/attempt、scenario 化 agent 日志名、内容哈希去重、Episode Manifest；本轮用**单 worker 单 episode**保证归属。多 episode 复用同一 worker 仍未 provenance-safe（已记录为限制）。
5. **是否进行战术修改？** **未新增战术候选**（C12/C14 均已在之前验证无效/无胜）。本轮为证据修复与定位。
6. **Clean Victory 是否增加？** **否，仍为 0。**
7. **下一步最有价值的单一修复？** **前出传感器（UAV）对北侧内线被动目标的早期定位**：让 UAV/前出 USV 在北侧产生定位雷达航迹，再走现有分配/锁定链；同时先解决 UAV 早期损失路径（E12 UNRESOLVED）。

## Clean Victory 定义与核验
`Engine Victory AND black_breakthrough == 0`。W2-5 C10（27/14，1 突破）与 C12（16/15，2 突破）均 Defeat ⇒ Clean Victory = 0。

## 证据等级
- 突破者=usv4：**VERIFIED**（episode-tagged 引擎事件 + 路线）。
- usv4 从未被定位、仅被动：**VERIFIED**（game log active=0，passive=10）。
- “26 combat + 1 breach”拆分：**INFERRED**（源码机制确认，逐单位击杀原因未单独记录）。
- C12 在 W2-5 无改善：**VERIFIED**（16/15，2 突破）。
- 北翼空档：**VERIFIED（终局无北侧兵力）**；但“仅因空档”不足以解释，因该目标从未被定位。

## 交付/约束
- 目录：`auto_harness/combat_exchange/e15_episode_provenance/`（01 归属修复、02 Manifest、03 突破事件、04 真值 vs 观测、05 退出归因、06 根因、07 中文报告、provenance.py、test_provenance.py 5/5）。
- 未改黑方/物理/武器雷达/裁判/突破线/评分/场景身份；未改 Agent 战术；未宣称胜利。Trace ON 与 E9 基线轨迹一致（`384b46b27af4`）。
