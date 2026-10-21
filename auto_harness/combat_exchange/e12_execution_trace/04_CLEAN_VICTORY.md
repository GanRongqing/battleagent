# 04 — CLEAN VICTORY CHECK
Rule (source `main.py::_build_result`): Victory only when `ended_reason` says all enemies destroyed;
**any “突破” ⇒ Defeat**. Clean Victory computed separately = `"敌方" in reason and "击毁" in reason and
"突破" not in reason and "我方" not in reason`.
| case | ended_reason | Engine result | Clean Victory |
|---|---|---|---|
| C10 W2-5 | 敌方1艘艇突破防线 | Defeat | **False** |
| ACE W2-5 | 敌方2艘艇突破防线 | Defeat | **False** |
| ACE W2-6 | 敌方1艘艇突破防线 | Defeat | **False** |
No scenario achieves Clean Victory. Judge order (breakthrough check before/with kill accounting) is
unchanged and was not modified.
