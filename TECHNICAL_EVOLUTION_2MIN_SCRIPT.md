# Technical Evolution — 2 分钟讲稿（Skill Evolution 案例）

> 全部数据来自真实 artifact：`skill_evolution_runs/evo_losttrack_coverage/`、
> `runtime_audit/run_ep4_1787234142/step_336.json`、`skills/maritime_commander/history/`。

---

各位，我今天用一个真实案例说明"我们说的 Skill Evolution 是什么"。我们**不是让 Skill 在线乱改**——运行时 Skill 在每局里完全冻结，Agent 对 SKILL.md 只读。离线才允许进化，而且走完整可审计闭环：证据 → 判定 → 三个 LLM 角色讨论 → diff → 测试 → 人工审批 → 回滚。

**一、从真实 step 336 出发。** 在 DeepSeek 对局 run_ep4 的第 336 步（仿真 6598 秒），触发 `lost_high_threat`：一条敌舰 black_usv3 已丢失 64 秒、不确定半径 6.9 公里，但舰队仍把 3 艘 USV 全押在它身上；同一时刻另外 3 艘可见敌舰 0 覆盖，全局覆盖质量只有 0.16。Commander 自己的回复里都写了"优先重搜以维持覆盖"，但当时的 Skill 文档没有给出这条优先级。

**二、原 Skill 哪里不够。** 旧文 `Low-confidence commitment` 只约束"对单个低置信/丢失目标不要做昂贵不可逆的集中"，另有 Uncertainty semantics 说"高不确定优先重搜"。它缺的是：**当多个威胁区域存在覆盖缺口时，修复覆盖 vs 继续向单目标追加边际集中，谁优先**。

**三、Analyst 提出了什么。** 结构化输出判定这是 STRATEGIC_DOCTRINE + RECON，建议改 doctrine，但它提了 3 条，其中包含硬性成分："攻击者数不得超过维持覆盖的余量"、"coverage 质量应作为集中力度的输入"。

**四、Critic 否掉了什么。** Critic 给了 `accept_analyst=false`：单步证据过拟合、硬阈值在变规模下不可泛化、跟 allocator 的 coverage floor 职责重叠、把分配细节写进 Commander 文档越权、以及 endgame 只剩一艘高威胁敌舰时硬规则反而阻止正确集中。

**五、Editor 最终只加了哪两行。** 在 `Low-confidence commitment` 末尾追加一句定性原则：

> **覆盖缺口优先于边际集中**：当多个敌舰未受覆盖时，修复覆盖比追加对单一目标的火力更有价值。

就是 `+2` 行，不写数量、不写阈值、不写场景。old hash `aebc47bf…` → new hash `155b0201…`。

**六、为什么这个改动更通用。** 它把原则从"单目标置信度"提升到"全局覆盖缺口的资源排序"，scale-agnostic：5+5、10+10、15+15 都成立；endgame 和即时突破风险仍保留既有例外。Editor 明确拒绝了所有数值化方案——这正是"不要让 LLM 说了就算"。

**七、验证与发布。** Static audit PASS；6 个单元/fair-play 测试全过；三个 DEV 回归（5+5 Harness、10+10 Harness、5+5 Commander）全部 Victory、0 parse/policy 错、0 异常、Commander 延迟 3.4s vs 基线 3.7s，无粗回归。显式 `--approve`（approved_by=operator）后发布 v1，旧版备份在 `history/SKILL_aebc47bf8632.md`，`--rollback` 按 hash 精确恢复，已验证。

**八、这才是我们所谓的 Skill Evolution。** 从"只约束对不确定目标的提交"，进化到"覆盖缺口优先于边际集中"；证据可审计、diff 可展示、可以回滚，而运行中的 Agent 从未被在线改写。
