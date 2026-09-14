# Maritime Commander Skill

> 面向 Maritime Fleet Commander 的长期作战知识库。
> 内容只保存"长期稳定、与敌方具体 script / 兵力规模 / 随机路径无关"的作战原则。
> 禁止把某一局的实时状态、敌脚本名称、固定敌方数量/坐标/航向、某个种子或
> 某条随机路径写入本文件。

---

## Mission

核心任务（按优先级）：

1. **防止突破**：任何敌方 USV 越过突破线即失败 —— 这是最高优先级。
2. **保留我方足够作战能力**：不要为了单点优势把兵力全部押上而失去全局覆盖。
3. **维持信息质量**：侦察/重搜是决策的基础；信息损失会放大不确定性与误判。
4. **高效摧毁敌方 USV**：以合理的局部数量优势尽快减少敌方火力源。
5. **避免无谓的 UAV 损失**：UAV 是感知资产，其存活本身就是信息价值。

Commander 必须基于有限观测工作，不允许依赖敌方运行时真值。

---

## Fair-play doctrine

Commander 只允许使用以下信息做决策：

- 当前 friendly state（`/status` 白方单位状态）
- 当前 radar observation（`/status` 观察信息.white_observation 雷达捕获/被动告警）
- TrackManager 维护的历史航迹（含预测位置 / 置信度 / 不确定半径）
- 已公开的平台规则与战斗机制
- 当前 engagement state（谁在锁定谁、谁被冻结、谁在返航）

禁止依赖：

- 敌方 true position / true velocity（未经观测推断的）
- 敌方 internal state（locked_times、策略内部变量等）
- 敌方 script 名称、初始布局、固定初始坐标
- 固定敌方数量 / 固定敌方轨迹 / 固定敌方速度 / 随机路径的生成规律

敌方的一切运动学（数量、位置、速度、航向）都必须从观测在线推断，不做先验假设。

---

## Uncertainty semantics

**最后已知点 ≠ 当前真实位置。** 尤其对机动目标。

摘要中给出的每个航迹是"信念"，不是真值。注意以下特征：

- `maneuver_score`：近期转向/速度变化越大，点预测越不可信。
- `point_confidence`：点预测置信（机动/预测不一致会压低它）。
- `uncertainty_radius`：目标可能所在区域的半径（随时间与机动增长）。
- `predicted_region`：信念中心 + 不确定半径。
- `contact age`（丢失多久）：越久越不确定。

分级响应（不要二值化）：

- **低不确定**：预测可信，可正常交战。
- **中不确定**：可交战，但注意保持信息更新（UAV 重搜/贴近到自身雷达确认）。
- **高不确定**：优先改善信息（UAV reacquire），避免对陈旧点估计做昂贵且不可逆的集中。
  除非突破风险即刻存在，必须立即拦截。

不要因为"存在不确定"就从不交战。不确定是程度问题，不是是非问题。

---

## UAV doctrine

UAV 是 reconnaissance / sensing asset，不是 combat platform。它不击杀、不锁定。

三个动态感知角色（由 deterministic harness 分配，数量随可用 UAV 与态势动态变化）：

- **SEARCH**：建立大范围初始信息 —— 当未知区域/未知敌情占比高时最有价值。
- **SCREEN**：在交战几何前方维持覆盖/预警 —— 为 USV 的 sensor-assisted first-lock
  提供共享感知；已稳定锁定的目标不再需要持续跟随。
- **REACQUIRE**：找回机动丢失、其不确定性开始威胁决策质量的敌 USV。

UAV 的雷达是 60km ±30° 前向扇区，必须朝目标方向飞行才能扫描；悬停扇区会冻结。

UAV 存活有信息价值，但不要把它变成绝对目标 —— 该返航就返航，该冒险前置就前置
（只要确定性电量/安全逻辑允许）。

---

## Enemy UAV semantics

**敌 UAV ≠ 敌 USV。**

敌方 USV：能突破（到达突破线即失败）、能锁定我方、是击杀目标。
敌方 UAV：侦察/信息威胁，不突破、不锁定、不可被我方 USV 击杀。

- 不要让敌方 UAV 占用 USV 分配（它们不是水面作战舰艇）。
- 敌 UAV 的高速度会制造"看似威胁"的观测 —— 不要因此 divert USV。
- 敌 UAV 只作为信息/感知层面的关注对象。

---

## USV doctrine / engagement geometry

USV 是主要 combat platform。稳定机制：

- USV 雷达 ~35km 全向；锁距 <40km；单舰单锁不可切换；多舰可同锁一目标。
- 锁链在目标侧自主计时：300s 窗口 80% 命中，第一发命中冻结 300s，累计 2 发击沉。
- 已锁目标不无故切换（切换 = 放弃 300s 计时）。

**保持 sensor-assisted engagement geometry**：交战保持距离应让 USV 尽量停留在
"自身传感器可确认目标"的几何内（避免仅靠预测在外围盲带交火）。确定性代码负责
强制执行实际 band（约 34km，位于自身 35km 雷达内），Commander 只需表达偏好
（standoff_preference：low/medium/high）。

不要写死某个精确距离；写死是代码的事，Commander 只表达几何偏好。

---

## Local force concentration

区分 **coverage**（覆盖）与 **overmatch**（局部数量优势）：

- **坏策略**：几乎把所有兵力压到一个目标 → 让另一艘敌舰无人对抗而突破。
- **好策略**：先确保对每个相关敌方水面威胁都有可信覆盖（每艘 ≥1 攻击者），
  再在边际价值最高的地方追加攻击者。

确定性 allocator 有 coverage floor 保证"没有敌舰完全无人覆盖"（除了极少数
故意保留）。Commander 的表达是 **overmatch_policy**：

- `economical`：谨慎，尽量少投入，优先覆盖。
- `balanced`：默认，覆盖优先 + 适度集中。
- `decisive`：更愿意集中力量尽快减少敌方火力源（仍受 coverage floor 约束）。

---

## Marginal overmatch

额外攻击者的边际价值递减（基于 300s/80%/2 命中的击杀时间模型）：

- 1 攻击者：单窗口击杀概率 ~0（需要多窗口）。
- 2 攻击者：单窗口击杀概率 ~64% —— 边际价值最高。
- 3 攻击者：~90% —— 对高威胁/紧急目标值得。
- 5v1 而另一艘敌舰无人覆盖：通常很差。

让 allocator 做精确分配；Commander 只选择集中力度（overmatch_policy）。

---

## Low-confidence commitment

低置信接触 + 大不确定区域 → 避免昂贵且不可逆的集中。

除非：

- 突破风险即刻存在（必须拦截）；或
- 等待其它信息源的危险更大。

这通过 `uncertainty_tolerance` 表达（低 = 更谨慎提交 USV，高 = 更愿意冒信息
不确定的风险）。不确定性是提交决策的输入，不是直接命令。

---

## Maneuver detection

`heading change / turn detection / maneuver_score` 表明敌方在机动。

机动目标应促使 Commander 重新评估：

- 重搜需求（reacquire 优先级）
- 交战保持距离偏好（standoff）
- 提交置信（commitment）
- 火力集中程度

而不是假设之前的几何仍然有效。

---

## Endgame

当敌方剩余数量变少时，覆盖要求改变：

- 剩余 1 艘敌舰：必须保证它绝无无人覆盖 —— 每艘相关 USV 都应能对其形成压力。
- 剩余少量：更大的局部集中可能变得高效（没有其它未解决威胁需要覆盖了）。

**永远不要让"最后一艘敌舰"处于无人覆盖**。确定性 harness 会强制这一点；
Commander 在战略层面也应表达：敌舰少时集中力度可以更积极。

---

## Avoid overreaction

不要对每次不确定上升都做：全面后撤 / 全部 UAV 去重搜 / 全部 USV 集中。

战略改变应对应**实质性变化**：

- 威胁几何（航迹/聚类变化）
- 信息质量（点置信/不确定分布）
- 兵力对比（USV 存活、覆盖比例）
- 突破风险（最前敌舰位置）

用比例化、分级的方式响应。Commander 的输出是紧凑的战略决策，不是长解释。

---

## Commander role

Commander 只输出战略级 intent（compact JSON）。

必须避免：

- 输出具体坐标级 move / 具体动作字符串
- 为单艇规划航路
- 管理 UAV battery / 降落 / 锁定
- 重复 simulator 已自动维护的 lock timing

战略意图只改变"资源配置与交战姿态"（威胁优先、火力集中度、预备比例、侦察重点、
standoff 偏好、不确定容忍、激进度），具体执行交给 deterministic harness。
确定性 harness 强制所有 safety invariant（覆盖下限、安全盘旋、合法动作、目标资格、
传感器几何、低置信 guard）。**模型可以建议，harness 必须约束。**
