# 正式实验统计

## Experimental Setup

- Frozen Agent: agent_hybrid_v5.py (hash in config_manifest.json)
- Frozen Skill: skills/maritime_commander/SKILL.md (hash in config_manifest.json)
- Random-waypoint enemy movement, fixed_frontage, seed 1001–1030 per scale
- N = 30 per setting, total 90 episodes

## Main Results

| 场景 | N | Clean Win | 95% CI | 平均击杀 | 平均USV损失 | 探索面积km² | 探索比例 | Breakthrough | OOB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5+5 vs 10 | 30 | 29 | [0.8333, 0.9941] | 9.97 | 1.73 | 57455.8 | 0.2972 | 0 | 0 |
| 10+10 vs 20 | 30 | 28 | [0.7868, 0.9815] | 19.87 | 4.1 | 67085.8 | 0.3471 | 2 | 0 |
| 15+15 vs 30 | 30 | 28 | [0.7868, 0.9815] | 29.93 | 6.67 | 74610.0 | 0.386 | 2 | 0 |

## Key Findings

- Clean win rate: S1 0.97 → S2 0.93 → S3 0.93 (N=30 each; reporting observed rates, no statistical generalization claimed).
- Friendly USV loss (mean): S1 1.73 → S2 4.1 → S3 6.67.
- Enemy combat USV killed (mean, event-based): S1 9.97 → S2 19.87 → S3 29.93.
- Explored area (mean km²): S1 57455.8 → S2 67085.8 → S3 74610.0; explored ratio 0.2972 → 0.3471 → 0.386.
- Failure modes: see failure_cases.csv (auto-classified from auditable evidence only).
- OOB: see FORMAL_EVAL_SUMMARY.md (reported as observed in formal eval only).

> N=30 per setting. Results reported as observed; no over-generalization beyond this sample.
