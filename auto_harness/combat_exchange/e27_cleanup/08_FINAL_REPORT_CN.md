# 08 — E27 中文最终报告（磁盘清理与工程精简）
1. **清理前剩余**：`/` 2.2G 可用（93%），`/root/autodl-tmp` 6.6G 可用（90%）。
2. **占用最大**：`hsystem/pomdp_api/api_logs/games` 37G（4183 个历史引擎 JSON）；`/tmp/opencode/parallel_runs` 7.7G；`build` 184M；`__pycache__` 186.6MB；`.venv` 1.1G（受保护）。
3. **实际删除**：历史 api 游戏日志 4183 个（39,237,743,138 B，逐文件清单 `tmp_games_manifest.csv`）；`hsystem/build`；1328 个 `__pycache__`+pyc；`/tmp` 运行日志（六场景 C27/C30 证据已先压缩保存到 e25/e26 raw_logs）。
4. **实际释放**：`/dev/md127` **约 37 GB**（54G→17G 已用）；`/` **约 7–8 GB**（28G→20G 已用）。总计约 44 GB。
5. **清理后剩余**：`/` 约 11G 可用（65%）；`/root/autodl-tmp` **44G 可用（28%）**。
6. **C30 运行依赖**：全部保留（源码、`adaptive_skills.py`、`universal_safety.py`、fleet_recon、split_screen、in-place `.so`、引擎/裁判/场景）。清理后真实 smoke：W2-2 C30 = 30/8 valid。
7. **六场景验收证据**：保留（e24/e25/e26 报告、`games_c27`/`games_c30` 压缩原始日志、results JSONL、AREA/LOCK trace）。
8. **C10/C27 复现**：未受影响（源码与基线入口保留）。
9. **未处理的高风险大文件**：`hsystem/.venv` 1.1G、两处 `.git`（82M/59M）、`runtime_audit` 77M、`w6_anti_evasion` 25M 等——按要求列为受保护，未删除。
10. **后续防膨胀**：新增 `.gitignore`（缓存类）；评测默认关闭大体积逐步 TRACE；历史引擎 JSON 定期按可再生策略清理并保留清单。
