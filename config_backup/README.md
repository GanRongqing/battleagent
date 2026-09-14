# 打赢配置备份 (2026-08-04)

## 已验证：3局3胜, 全灭黑方5艘, 最高净得分+50

## 场景改动 (sim_20250819测试用例1.py)

| 参数 | 原值 | 新值 | 文件位置 |
|------|------|------|----------|
| USV初始y坐标 | 325k~345k(集中) | **137k~537k(分散)** | 第67行 |
| UAV初始y坐标 | 325k~345k(集中) | **137k~537k(分散)** | 第68行 |
| USV雷达距离 | 20km | **35km** | 第71行 |
| UAV电池 | 7200s | **25000s** | uavbattery.json |
| 仿真速度 | 50x | **100x** | 第51行 |

USV分散后的对应关系:
- white_usv1 @ y=537k ↔ black_usv1
- white_usv2 @ y=487k ↔ black_usv2
- white_usv3 @ y=337k ↔ black_usv3
- white_usv4 @ y=187k ↔ black_usv5
- white_usv5 @ y=137k ↔ black_usv4

## Agent 策略 (agent_win_v7.py)

1. **起飞UAV** (t=2000s): 5架UAV向东20m/s侦察
2. **全速向东**: 所有USV 18m/s航向90°
3. **每艘USV锁最近目标**: 根据y坐标分配各自的黑方艇
4. **UAV巡航**: 每15步转向, 保持战场中线
5. **击杀过滤**: 记录已击杀目标, 避免引擎bug(dead target仍出现在锁列表)

## 关键胜利要素

- USV雷达35km > 黑方30km → 先敌发现
- UAV电池25000s → 全程侦察不掉电
- 每艘USV有自己的目标 → 5线同时作战
- 单独发送lock(失败不影响move)

## 使用方法

```bash
# 1. 启动后端
cd /root/autodl-tmp/hsystem/hsystem/simserver
PYTHONPATH=".:..:../simulation" /root/miniconda3/envs/hsystem_env/bin/python base_server.py

# 2. 启动API
cd /root/autodl-tmp/hsystem/hsystem/pomdp_api
SIM_HOST=127.0.0.1 /root/miniconda3/envs/hsystem_env/bin/python main.py

# 3. 跑agent
cd /root/autodl-tmp/hsystem
/root/miniconda3/envs/hsystem_env/bin/python agent_win.py
```
