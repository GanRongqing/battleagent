#!/bin/bash
# 冒烟评估: 连续运行 agent_hybrid_v1.py (启用UAV) 5局, 记录结果
# 用法: bash run_smoke.sh [局数]  (默认5)
N="${1:-5}"
PY="/root/miniconda3/envs/hsystem_env/bin/python"
APIPORT=8000
SUMMARY=/tmp/smoke_results.txt
> "$SUMMARY"

for i in $(seq 1 "$N"); do
    # 确保无残留对局
    curl -s -m 5 http://127.0.0.1:${APIPORT}/stop >/dev/null 2>&1
    sleep 2
    LOG=/tmp/smoke_run${i}.log
    echo "=== 冒烟第 ${i}/${N} 局 ===" | tee -a "$SUMMARY"
    start=$(date +%s)
    PYTHONUNBUFFERED=1 $PY /root/autodl-tmp/hsystem/agent_hybrid_v1.py --uavs > "$LOG" 2>&1
    rc=$?
    end=$(date +%s)
    # 解析结果
    res=$(grep -oE "对局结果: Result\.[A-Za-z]+" "$LOG" | head -1)
    kills=$(grep -oE "击杀蓝舰: [0-9]+" "$LOG" | head -1)
    usv=$(grep -oE "我方USV损失: [0-9]+" "$LOG" | head -1)
    uav=$(grep -oE "UAV损失: [0-9]+" "$LOG" | head -1)
    brk=$(grep -oE "突破: [0-9]+" "$LOG" | head -1)
    echo "  $res | $kills | $usv | $uav | $brk | rc=$rc | $((end-start))s" | tee -a "$SUMMARY"
    sleep 3
done
echo "=== 冒烟评估完成 ===" | tee -a "$SUMMARY"
cat "$SUMMARY"
