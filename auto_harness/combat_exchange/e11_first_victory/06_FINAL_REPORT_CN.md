# 06 — E11 中文总结（首次胜利诊断）

## 结论先行
- **本轮未取得任何一场 Victory。** 六场景仍全部 Defeat。
- **未完成一个被验证的修复。** C13（威胁规避式 UAV 搜索）实测 **NO_EFFECT**（与 ACE 轨迹完全一致）。

## W2-5（最接近胜利：C10 27/14，仅 1 艘突破）
- 终局 `ended_reason`：“敌方1艘艇突破防线”；6 艘白方存活，全部集中在 **x≈120km、y≈−142…−73km（南侧）**；
  剩余黑方在 x>214km。突破者不在末期 active 中。
- 全程**从未被定位**的黑方为 usv1/usv2（usv3/usv4 仅被动）。=> 最可能是一艘从**北侧空档**绕过的黑方。
- 根因归类：**覆盖/兵力分布问题（北翼空档）**，不是软件故障。

## UAV 损失（关键发现）
- W2-5 中 10 架 UAV 在同一时刻被击毁；死前 30s，它们位于 x=212–244、y=−72…−142，距已知黑方 **12–30km**，
  即深入黑方交战包线。W2-1 亦在交战前很早损失全部 UAV，导致只剩被动方位、无法形成 own-lock（0 击毁）。
- `UAVManager._global_search_fly` 只按“未覆盖格”选点，不考虑已知威胁；这是真实缺陷。
- **但是**：C13 在 `_global_search_fly` 中加入“距已知黑方 ≥50km”的选点后，UAV 死亡时刻**完全不变**
  （W2-1 03:16、W2-5 04:42，前后一致）=> UAV 的损失并不发生在这条路径上（更可能是 SCREEN/REACQUIRE
  接近路径，或当步 track 可见性时序）。

## 已做/未做
- 已做：新增 `agent_hybrid_safe_uav_search.py`（C13，parent ACE），注册 runner；诚实验收。
- 未做：未修改黑方/物理/裁判/评分；未改默认 flags；未跑无意义的六场景回归（C13 为 no-op）。

## 下一步（精确）
1. **只读 instrumentation**：每步记录每架 UAV 的 role、action、最近黑方距离、track 可见性，定位 12–30km
   死亡到底由 SCREEN / REACQUIRE / SEARCH / GLOBAL_SEARCH 哪条路径造成（当前 `NEED_INSTRUMENTATION`）。
2. 在该路径实施**UAV 安全间距**（保持 ≥50km，UAV 雷达 60km 仍可探测），而非仅在 global search 选点。
3. W2-5 北翼覆盖：加入“屏列覆盖下限/两翼平衡”，避免幸存兵力全部聚于南侧。
4. 修复通过后，再按 Level A（W2-1/W2-5）→ 六场景回归 → 验收。

## 复现
```
LIFECYCLE_HANDOFF_V1=0 OBS_TI_REVIVE=0 TARGET_LIFECYCLE_V2=0 \
python auto_harness/evaluation/parallel_runner/parallel_runner.py \
  --strategies W2-1,W2-5 --seeds 43001 --policies C13 --workers 2 --epoch E11 --run-id <RUN>
python auto_harness/combat_exchange/e9_evaluation_recovery/scripts/verify_identity.py <RUN> <SID> C13
```
