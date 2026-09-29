# 针对上周第4问和第7问的系统改进

## 1. 第4问：每次生成代码，怎么维护？

**答：是，新版本仍然来自离线 code candidates。**
但现在每个版本同时记录五样东西，而不是只有一个大文件：

- Code Diff（代码文本变化）
- Semantic Diff（策略机制变化，人能读）
- Mechanism Card（失败→根因→机制→适用条件→证据→结论）
- Validation（单测 / DEV / Fresh）
- Lineage（父子版本谱系）

因此：**代码可以变化，"经验"不依赖具体 Python 实现。**

放一个 ACE 例子：
- Failure：有可见目标 + 有空闲 USV + 目标 0 owner，但 allocator 不派兵；
- Root Cause：默认 intent `focus=2` + `reserve=0.20` 太保守；
- Mechanism：当出现「可见且 0-owner 的目标 + 空闲战斗 USV」时临时释放 reserve；
- Evidence：assignment coverage 43.5%→75.7%，never-assigned 82→34；
- Combat（DEV）：CER 0.373 → 1.065，6/6 策略改善；
- Status：`DEV_OUTCOME_SUPPORTED / FRESH_UNCONFIRMED`（Fresh 那轮因误杀 API 无效）。

## 2. 如何沉淀可泛化经验？

长期存的不是 `if/else`，而是结构化机制：

```
Context → Failure → Root Cause → Mechanism → Effect → Confidence
```

例：`有目标 + 有空闲 USV + 0 owner → under-commitment → dynamic reserve release`。

C2 的**负经验**同样被结构化保存：
> "never reached lock range" 不等于 "close more aggressively"
> （C2 锁率升了但 TTFL 变慢、战斗混合 → INCONCLUSIVE）。

## 3. 第7问：Prediction 怎么泛化？

之前：`TrackManager → 单一运动学外推`。
现在：`TrackManager → PredictorManager → 多个 predictor → 在线评分 → 选中的 prediction`。

已实现：统一接口、3 个 predictor（ConstantVelocity / ConstantTurn / RecentVelocity）、
在线误差评分（EMA）、动态 model selection、uncertainty 输出、shadow 记录。**默认 shadow-only，不改战斗行为。**

## 4. 后续如何扩展？

Model Bank → CBR（相似历史机动检索）→ Streaming residual learning → LLM 离线生成新 predictor。
这些都只留了干净的 extension point，**没有伪装成已实现**。

## 5. 一句话总结

> 代码可以变，但机制经验保持稳定；敌人可以变，但 predictor library 可以持续增长。
