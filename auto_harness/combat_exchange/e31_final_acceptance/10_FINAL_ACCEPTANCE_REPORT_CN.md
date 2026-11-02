# 10 — E31 中文最终验收报告（C31 Release Freeze）

## 必答问题
1. **冻结策略的 Commit 与源码哈希？** 基线 `d82d9fc`；C31 入口 `agent_hybrid_c31.py`，安全层
   `scenario_agnostic_safety.py`（BUFFER=5000）。**VERIFIED**
2. **5km Buffer 是否实际启用？** 是（BUFFER=5_000，安全改写 trace 中 preventive_buffer 生效）。**VERIFIED**
3. **TRACE ON/OFF 是否行为一致？** W2-1 与 S10 的轨迹哈希与 K/L 完全一致（96ad…/1a73…）。**VERIFIED**
4. **13 场景是否全部有效？** 13/13 valid=True。**VERIFIED**
5. **13 场景是否全部 CER>1？** **是（13/13）**。**VERIFIED**
6. **W2 pooled CER？** **98/51 = 1.922**（6/6 场景 >1）。**VERIFIED**
7. **非 W2 pooled CER？** **52/4 = 13.000**（7/7 场景 >1）。**VERIFIED**
8. **13 场合并 pooled CER？** **150/55 = 2.727**。**VERIFIED**
9. **White USV AREA_OUT 是否全 0？** **是（0）**。**VERIFIED（引擎 AREA_TRACE）**
10. **White UAV AREA_OUT 是否全 0？** **是（0）**；仅黑方 25 次。**VERIFIED**
11. **Safety 是否存在不合理改写？** `unexpected_rewrites = 0`；改写均为 predicted_out / preventive_buffer /
    current_out 三类几何合理触发；内部（远离边界）不改写。**VERIFIED**
12. **是否仍有固定 W2 地图假设？** 否：使用真实公开 Polygon（W2 矩形 / scale 八边形），缺失地图标记不可用且不回退。**VERIFIED**
13. **是否有场景身份/敌真值泄漏？** 否（仅公开地图顶点；无场景名/ID/Seed/敌情）。**VERIFIED**
14. **相比 E30 是否战斗回退？** 无：13/13 K/L 与 E30 完全一致（W2 98/51、非 W2 52/4）。**VERIFIED**
15. **是否具备完整复现能力？** 是：`accept.sh` + 结果/哈希/原始 trace（raw_logs）。**VERIFIED**
16. **C31 是否可正式封版？** **C31 RELEASE ACCEPTED**。**VERIFIED**

## 13 场结果（seed 43001）
W2：16/5、30/8、12/10、10/8、16/9、14/11 → **98/51=1.922**。
非 W2：S10 5/0、S10RW 5/0、S15 8/1、S20 10/3、S30 15/0、EXTD 3/0、EXTT 6/0 → **52/4=13.0**。
合并：**150/55=2.727**。

## Gate 结论
A Identity PASS · B Positive 13/13 PASS · C Boundary（USV=0,UAV=0）PASS · D Legal PASS ·
E Reproducible PASS · F No tactical change PASS。

## 封版
**C31 RELEASE ACCEPTED**（white-combat-0031-v1）。Combat Exchange 优化阶段结束。
