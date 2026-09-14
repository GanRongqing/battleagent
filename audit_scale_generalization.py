#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""audit_scale_generalization.py — 规模泛化耦合审计

检查 SKILL.md + agent_hybrid_v2.py + 场景配置 是否存在规模耦合
（固定我方/敌方数量、固定 reserve、固定扇区数、TrackManager/UAVManager/
USVController 依赖固定数量、Commander 提示词含规模标签等）。

白名单（合法机制，不视为耦合）:
  35km/40km/60km 雷达距离, 300s 锁窗口, 80% 命中率, 2 次命中击沉,
  30v30 的场景部署坐标只出现在 scenario_builder（场景配置，非 agent 策略）。

用法: python audit_scale_generalization.py
"""
import os
import re
import sys
import json

ROOT = "/root/autodl-tmp/hsystem"
AGENT = os.path.join(ROOT, "agent_hybrid_v2.py")
SKILL = os.path.join(ROOT, "skills", "maritime_commander", "SKILL.md")
SCENARIO_DIR = os.path.join(ROOT, "hsystem", "sim_script", "20250819TZB")
SCES = os.path.join(ROOT, "hsystem", "simserver", "config", "sces.json")
POMDP = os.path.join(ROOT, "hsystem", "pomdp_api", "main.py")

WRAPPERS = ["scenario_10v10.py", "scenario_15v15.py", "scenario_20v20.py",
            "scenario_30v30.py"]
SCALE_NAMES = ["scenario_10v10", "scenario_15v15", "scenario_20v20",
               "scenario_30v30"]
SCALE_TAG = re.compile(r"\b(10v10|15v15|20v20|30v30|scenario_[a-z0-9]+)\b")

# ── 合法机制数字（白名单，出现不算耦合） ──
MECH_NUMS = {"35", "40", "60", "300", "80", "2", "300000", "260000", "15000",
             "405000", "250000", "550000"}


def read(p):
    try:
        with open(p, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def find_lines(text, patterns, exclude=None):
    """返回匹配 (行号, 行内容)，exclude 为排除正则。"""
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        if exclude and exclude.search(line):
            continue
        if any(p.search(line) for p in patterns):
            out.append((i, line.strip()))
    return out


AGENT_FIXTURE = re.compile(r"(FakeObs|MiniObs|selftest|mocktest|scaletest|"
                           r"def check\(|check\(|assert |\.tracks\[.b[0-9]|"
                           r"prev_black_killed=|engaged=True|for t in \(100)")


def audit():
    skill = read(SKILL)
    agent = read(AGENT)
    # 运行时区 = 第一个测试函数之前（离线 fixture 中的 15 属测试数据，非运行时策略）
    runtime = agent.split("def selftest_trackmanager")[0]
    results = []  # (item, PASS/FAIL, detail)

    def item(name, ok, detail):
        results.append((name, "PASS" if ok else "FAIL", detail))

    # ═══ 1) Single Skill ═══
    skill_ok = os.path.exists(SKILL) and "Maritime Commander" in skill
    item("Single Skill file (maritime_commander/SKILL.md)", skill_ok,
         f"exists={os.path.exists(SKILL)}")

    # ═══ 2) Single Prompt / no per-scale prompt ═══
    per_scale_prompt = re.compile(r"prompt_?(10v10|15v15|20v20|30v30|5v5|8v7)",
                                  re.IGNORECASE)
    pp = find_lines(agent, [per_scale_prompt])
    item("Single System Prompt + schema (no prompt_10v10 etc.)", not pp,
         "matches=" + (str([l for _, l in pp]) if pp else "none"))

    # ═══ 3) Commander scenario-label blind ═══
    labels = re.compile(r"(SCENARIO|scenario_label|你是.{0,10}(10v10|30v30)"
                        r"|10v10 场景|30v30 场景)")
    tagged = [l for _, l in find_lines(skill, [labels])] + \
             [l for _, l in find_lines(runtime, [labels])]
    # SCENARIO_SCRIPT 环境变量名允许（它是脚本选择，不是注入 Commander 的标签）
    tagged = [l for l in tagged if "SCENARIO_SCRIPT" not in l]
    item("Commander scenario-label blind (no '10v10/30v30' in prompt/summary)",
         not tagged, "matches=" + str(tagged) if tagged else "none")

    # ═══ 4) Fixed friendly count ═══
    # runtime 逻辑中不得硬编码我方数量；fixtures 除外
    fcnt = re.compile(r"(usv_total|usv_alive|uav_total|uav_alive|friendly)"
                      r"[^\n]{0,10}(==|= ?|>=|<=)[ ]*([5-9]|1[0-9]|2[0-9]|3[0-9])")
    hits = find_lines(runtime, [fcnt])
    item("No hardcoded friendly count in runtime logic", not hits,
         "matches=" + str([l for _, l in hits]) if hits else "none")

    # ═══ 5) Fixed enemy count / expected_enemy_count ═══
    ecnt = re.compile(r"(expected_enemy_count|num_black_usv\s*=|num_black_uav\s*="
                      r"|enemy_count\s*=|kill_count\s*==|len\([^)]*\)\s*==\s*15"
                      r"|range\(\s*15\s*\))")
    ehits = find_lines(runtime, [ecnt])
    item("No fixed enemy count / expected_enemy_count (TrackManager dynamic)",
         not ehits, "matches=" + str([l for _, l in ehits]) if ehits else "none")

    # ═══ 6) Fixed reserve count ═══
    # agent: allocate_usvs 必须用比例；SKILL: 不得"保持 N 艘预备"
    reserve_ratio_in_agent = ("reserve_ratio" in agent and
                              "int(round(len(available) * ratio))" in agent)
    sres = re.compile(r"(保持|always keep)[^\n]{0,15}[0-9]+ ?艘|"
                      r"预备 ?[0-9]+ ?艘")
    skill_res = find_lines(skill, [sres])
    item("Reserve ratio-based (agent) + no absolute reserve doctrine (skill)",
         reserve_ratio_in_agent and not skill_res,
         "agent_ratio=" + str(reserve_ratio_in_agent) +
         (" skill_matches=" + str([l for _, l in skill_res]) if skill_res else ""))

    # ═══ 7) Fixed sector count ═══
    sec = re.compile(r"([0-9]+ ?个?扇区|[0-9]+ ?sector|"
                     r"(idx ?- ?8)[^0-9]|range\(\s*5\s*\)|"
                     r"5 ?sectors ?× ?3)")
    sect_hits = find_lines(runtime, [sec]) + find_lines(skill, [sec])
    item("No fixed sector / fan count (UAV search adaptive)", not sect_hits,
         "matches=" + str([l for _, l in sect_hits]) if sect_hits else "none")

    # ═══ 8) TrackManager count-independent ═══
    tm_dynamic = ("for e in obs.active" in agent and
                  "self.tracks[name] = EnemyTrack" in agent and
                  "del self.tracks[name]" in agent and
                  "if name in self.killed_names" in agent)
    tm_ok = tm_dynamic and not find_lines(agent, [re.compile(r"range\(15\)")])
    item("TrackManager count-independent (create/update/drop dynamic)",
         tm_ok, "dynamic_patterns=" + str(tm_dynamic))

    # ═══ 9) UAVManager count-independent ═══
    uav_ok = ("n_uavs = max(1, obs.uav_alive)" in agent and
              "_search_fly(name, pos, n_uavs)" in agent and
              "step_deg = 90.0 / n" in agent and
              "(idx - 8)" not in agent)
    item("UAVManager count-independent (search fan adapts to UAV count)",
         uav_ok, "adaptive_fan=" + str(uav_ok))

    # ═══ 10) USVController count-independent ═══
    usv_ok = ("for u in obs.usvs:" in runtime and
              "for trk, usvs in alloc_result.items()" in runtime and
              "for tname, t in tracks.items():" in runtime)
    usv_hits = find_lines(runtime, [re.compile(r"range\((8|10|15)\)")])
    item("USVController count-independent (state machine over obs.usvs)",
         usv_ok and not usv_hits,
         "dynamic_loop=" + str(usv_ok) +
         (" fixed=" + str([l for _, l in usv_hits]) if usv_hits else ""))

    # ═══ 11) Scenario builder parameterized ═══
    builder_ok = os.path.exists(os.path.join(SCENARIO_DIR, "scenario_builder.py")) \
        and "def build_scenario" in read(os.path.join(SCENARIO_DIR, "scenario_builder.py")) \
        and "def _deploy_ys" in read(os.path.join(SCENARIO_DIR, "scenario_builder.py"))
    wrap_ok = all(os.path.exists(os.path.join(SCENARIO_DIR, w)) for w in WRAPPERS)
    item("Parameterized scenario (build_scenario + 4 wrappers + linspace deploy)",
         builder_ok and wrap_ok,
         f"builder={builder_ok} wrappers={wrap_ok}")

    # ═══ 12) sces.json + AVAILABLE_SCRIPTS ═══
    sces_ok = all(
        SCALE_NAMES[i] in read(SCES) for i in range(4))
    av_ok = all(n in read(POMDP) for n in SCALE_NAMES)
    item("Scenario registration (sces.json 4 entries + AVAILABLE_SCRIPTS 4)",
         sces_ok and av_ok, f"sces={sces_ok} available={av_ok}")

    # ═══ 13) Commander context bounded (top-K summary) ═══
    topk = "K = min(8, len(tracks))" in agent and \
        "more tracks not detailed" in agent and \
        "tracks[:K]" in agent
    item("TacticalSummary top-K bounded (Commander context ~constant)", topk,
         "topk=" + str(topk))

    # ── 汇总 ──
    print("=" * 60)
    print("=== SCALE GENERALIZATION AUDIT ===")
    print("=" * 60)
    all_ok = True
    for name, verdict, detail in results:
        all_ok = all_ok and verdict == "PASS"
        print(f"  [{verdict}] {name}")
        if verdict == "FAIL" and detail:
            print(f"            → {detail}")
    print("-" * 60)
    print(f"  FINAL: {'PASS' if all_ok else 'FAIL'} "
          f"({sum(1 for _, v, _ in results if v == 'PASS')}/{len(results)} checks)")
    print("=" * 60)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(audit())
