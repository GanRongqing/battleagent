# 07 — E25 中文最终报告（自适应技能组合与通用边界安全）

## 交付
- 可执行 Skill Registry：`adaptive_skills.py`（SituationFeatures / Composer / 技能轴）+ `agent_hybrid_safe_recon.py`(C27)、`agent_hybrid_adaptive.py`(C28)。
- Situation Feature Extractor / Adaptive Composer：`adaptive_skills.extract` / `Composer`（滞回、可选 `SKILL_TRACE`）。
- Universal Boundary Safety：`universal_safety.BoundaryAwareSafety`（在 ActionSafety 之后、/apply 之前，覆盖全部 USV 运动）。
- Boundary Event Attribution：`raw_logs/e25_area_c27.jsonl`（引擎 AREA_TRACE，默认关闭）。
- 单测：`test_universal_safety.py` 5/5、`test_adaptive.py` 6/6、`test_fleet_recon.py` 3/3、`test_boundary_safe.py` 4/4。

## 消融与六场景结果
| 方案 | 正式胜率 | pooled 官方 CER | 白 USV 越界 |
|---|---|---|---|
| A C10 | 0/6 | 0.725 | 0 |
| B C25 | 1/6 | 0.833 | 57 |
| **C C25+边界安全(C27)** | **1/6** | **1.922** | **0** |
| D 组合器(无安全) | 未测 | 未测 | 未测 |
| E 组合器+安全(C28) | 0/6 | 1.574 | 0 |

C27 逐场景（K/L，官方 CER）：W2-1 16/5(3.20)、W2-2 30/8(3.75, **Victory**)、W2-3 12/10(1.20)、W2-4 10/8(1.25)、W2-5 16/9(1.78)、W2-6 14/11(1.27)。pooled 98/51=**1.922**。
C28 逐场景：W2-1 20/2、W2-2 21/20、W2-3 12/5、W2-4 12/3、W2-5 20/16、W2-6 11/15；pooled 96/61=1.574。

## 机制归因（分别确认）
- **前沿侦察（B vs A）**：W2-1 首次击毁 0→13，pooled 0.725→0.833（但产生 57 次 USV 越界）。
- **通用边界安全（C vs B）**：pooled 0.833→**1.922**，白 USV 越界 **57→0**（引擎 AREA_TRACE 证实：50 次越界全为 UAV，USV 为 0）。
- **自适应组合（E vs C）**：pooled 1.922→1.574，**未优于** C27；W2-1/W2-4 更好，但 W2-2/W2-6 回退。组合器 v1 未证明净收益。

## 成功标准核对（如实）
1. 仅依赖合法观测：**代码核查通过**（无场景 ID/Seed 分支）；重命名/隐藏元数据/扰动/交接测试 **未运行（NOT_MEASURED）**。
2. 白 USV 自身导航越界：**归零（VERIFIED，AREA_TRACE）**。
3. 正式胜率高于基线：C10 0/6 → C27 1/6（W2-2 Victory）。**达成**。
4. pooled 官方 CER > 1：**C27 1.922 > 1（达成）**。
5. 改善来源于“态势识别与技能组合”而非识别样本：**部分未达成**——主要增益来自前沿侦察+通用边界安全（基础设施），组合器(C28)未超过 C27；故不宣称“自适应组合”已带来总体提升。

## 判定与建议
- **晋级统一候选：C27（C25 + Universal Boundary Safety）**：0 次 USV 越界、pooled 1.922、正式胜率 1/6。
- C28（自适应组合器）保留为实验分支：W2-1/W2-4 更优，但 W2-2/W2-6 回退，pooled 低于 C27，不晋级。
- 遗留问题（UNRESOLVED）：UAV 因前沿 tether 冲出东界（50 次 UAV AREA_OUT）——不影响 USV CER，下一步应对 UAV `fly` 也施加上界约束。
- 下一轮最值得攻克：修好组合器的 CONTACT_MAINTENANCE（其在 W2-2 有目标时退回屏列导致回退），并让 UAV 也受通用边界安全约束。
