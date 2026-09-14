#!/bin/bash
# 冒烟评估: 连续运行 agent_hybrid_v2.py (LLM Commander + UAV) N局, 记录结果
# 用法: bash run_smoke_v2.sh [局数]  (默认5)
N="${1:-5}"
PY="/root/miniconda3/envs/hsystem_env/bin/python"
APIPORT=8000
SUMMARY=/tmp/smoke_v2_results.txt
> "$SUMMARY"

for i in $(seq 1 "$N"); do
    # 确保无残留对局
    curl -s -m 5 http://127.0.0.1:${APIPORT}/stop >/dev/null 2>&1
    sleep 2
    LOG=/tmp/smoke_v2_run${i}.log
    echo "=== V2冒烟第 ${i}/${N} 局 ===" | tee -a "$SUMMARY"
    start=$(date +%s)
    LLM_ENABLED=true PYTHONUNBUFFERED=1 $PY /root/autodl-tmp/hsystem/agent_hybrid_v2.py --uavs > "$LOG" 2>&1
    rc=$?
    end=$(date +%s)
    # 解析结果 (权威结果来自 /result)
    res=$(grep -oE "对局结果: Result\.[A-Za-z]+" "$LOG" | head -1)
    meta=$(grep -oE "\[META\].*" "$LOG" | head -1)
    echo "  $res | rc=$rc | $((end-start))s" | tee -a "$SUMMARY"
    [ -n "$meta" ] && echo "  $meta" | tee -a "$SUMMARY"
    sleep 3
done
echo "=== V2冒烟评估完成 ===" | tee -a "$SUMMARY"
cat "$SUMMARY"
