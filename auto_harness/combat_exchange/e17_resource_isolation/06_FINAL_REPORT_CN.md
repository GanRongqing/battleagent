# 06 — E17 中文最终报告（被动恢复资源隔离）

## 必答问题
1. **Track-Only 是否与 C10 等价？** **是（VERIFIED）**：Track-Only v2 的 K/L、轨迹哈希、突破者
   （27/14、`384b46b27af4`、usv4）与 C10 完全一致。关键前提：被动历史必须**单独存储、不改动基础航迹的
   `last_seen_time`**（v1 改了 freshness → 16/17，已纠正）。
2. **C15 是否覆盖了不应覆盖的 UAV 行为？** **是（VERIFIED，源码）**：C15 在 `super().step()` 之后**无条件**
   覆盖被选无人机的动作，仅用“存活数≥2”判断，无角色/电量检查，且用固定名字 `white_uav10`——可覆盖
   RETURN/LANDING/SCREEN/REACQUIRE，造成角色记录与实际动作不一致、屏列覆盖损失（C15 定位数 26→21、击毁 27→19）。
3. **C16 是否真实改变决策？** **是（VERIFIED）**：轨迹 `87a6d23f51b8` ≠ C10 `384b46b27af4`，突破者 usv4→usv8。
   但它**没有定位 usv4**（0 步 radar），说明改的是其它目标的定向路径。
4. **原始定位覆盖是否得以保留？** **否**：C16 定位黑方 26→22，击毁 27→23。仅用 SEARCH 态无人机仍造成覆盖下降。
5. **是否仍存在定位能力与全局表现的负向权衡？** **是（VERIFIED）**：C16 未取得突破下降，反而使 W2-5 变差。
6. **Clean Victory 是否增加？** **0**（仍 Defeat，1 突破）。
7. **下一步最值得解决的具体约束**：**前出传感器数量与可用性约束**——单架 SEARCH 态 UAV 既要屏列/重搜又要
   定向定位，且目标选择是“最新被动接触”，不能稳定服务突破航道（usv4 未被服务）。应先解决 UAV 生存/数量
   （E12 UNRESOLVED），或让定位任务按**威胁/航道优先级**选择目标并占用**不影响屏列**的资源。

## 判定
- **C16 不晋级**（无 Clean Victory、W2-5 变差）；**保留 C10**。
- **Track-Only 数据修复可作为中性基础**保留（不影响 C10），但单独不产生战果。
- 未改黑方/物理/武器雷达/裁判/评分/突破线/场景身份；未用真值/场景标签；动作仍走正常 /apply。

## 交付
`auto_harness/combat_exchange/e17_resource_isolation/`：01 Track-Only、02 契约修复、03 C15 抢占审计、04 C16 设计、
05 定向对照、06 中文报告、`test_passive_isolated.py`（10/10）、`raw_logs/`。
代码：`agent_hybrid_passive_isolated.py`（Track-Only + C16）。Git commit 见本轮提交。
