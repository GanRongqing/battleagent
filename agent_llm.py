"""
LLM驱动的泛化海战agent
======================
核心: 用DeepSeek推理决策, 只依赖公平观测(/obs 语义文本 + /legal_actions 动作空间)
不依赖任何黑方数量/位置先验 → 天然泛化到任意黑方方案(5~15艘, 任意布局)

流程(每宏观步30s):
  GET /obs           → 公平语义观测(雷达探测)
  GET /legal_actions → 当前可执行动作空间
  DeepSeek推理       → 输出动作列表
  POST /apply        → 执行 → 推进
"""
import os, json, time, requests, re

API = "http://127.0.0.1:8000"
# DeepSeek (Anthropic兼容端点)
DS_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.deepseek.com/anthropic") + "/v1/messages"
DS_KEY = os.getenv("ANTHROPIC_AUTH_TOKEN", "")
DS_MODEL = os.getenv("ANTHROPIC_MODEL", "deepseek-v4-flash")

SYSTEM_PROMPT = """你是海军指挥官，控制5艘无人艇(USV)和5架无人机(UAV)防御舰队。
任务：在敌方舰艇突破防线(x≤50000米)前，锁定并击沉它们，同时尽量保存我方单位。

作战规则：
- 锁定：USV在40km内锁定敌舰，持续300秒后命中(80%概率)，命中使敌冻结300秒，累计2次命中击沉敌舰
- 雷达：我方USV雷达35km，UAV雷达60km(±30°扇区，朝航向方向)；敌方USV雷达30km，会锁定40km内我方USV
- 突破线：敌方任1艘到达x≤50000即失败
- 每艘USV只能同时锁1个目标，锁定中不可切换

决策优先级（按顺序执行，非常重要）：
1. 【保命优先】观测中任何USV显示"被锁定"或"已冻结"→ 该USV立即后撤(航向270°，全速18)，脱离敌方锁定范围
2. 【主动攻击】雷达捕获到敌舰(观测的[雷达捕获]里有敌舰) → 让附近USV锁定最近的敌舰(动作"锁定")，持续锁定才能击杀
3. 【侦察】开局或有UAV在甲板且雷达无目标 → 起飞UAV向东方(90°)侦察
4. 【推进】USV无目标且未被锁 → 缓慢向东推进(90°，速度10-18)，保持队形
5. 【防守距离】USV接近敌舰时保持30-40km距离，不要贴脸；如果太近(敌舰很接近)则后撤

错误教训（务必避免）：
- 不要一直让USV全速90°冲向敌舰从不后撤——会被敌舰锁定歼灭
- 发现敌舰后必须锁定，光靠近不打没有用
- USV被锁定了还往前冲=送死

每次决策：
1. 仔细读观测：雷达捕获几个敌舰、在哪；我方USV谁被锁了/冻结了；UAV电量
2. 按上面的优先级为每个单位决定动作
3. 只输出JSON动作数组: [{"action_text":"...","action_type":"..."}]"""


def api(method, path, **kw):
    try:
        r = requests.request(method, f"{API}{path}", json=kw.get("json"), timeout=15)
        if r.status_code == 200:
            ct = r.headers.get("content-type", "")
            return r.json() if "application/json" in ct else r.text
        return None
    except Exception:
        return None


def call_deepseek(obs_text, legal_text, history=""):
    """调用DeepSeek, 返回动作JSON数组"""
    user_prompt = f"""当前观测：
{obs_text}

当前可执行动作空间：
{legal_text}

历史动作（最近若干步）：
{history}

请根据敌情和我方状态，为每个需要行动的单位选择动作。输出格式必须是JSON数组，字段名为action_text和action_type，示例：
[{{"action_text":"white_usv1 移动 target_speed=18.0 target_course=90.0","action_type":"move"}},
 {{"action_text":"white_uav1 从 white_usv1 起飞 target_speed=40.0 target_course=90.0","action_type":"launch_uav"}}]
如果没有单位需要行动，输出 [{{"action_text":"空操作，等待一个宏观步 [noop]","action_type":"noop"}}]
只输出JSON数组本身，不要任何解释、前后缀、markdown或中文注释。action_text和action_type必须来自动作空间。"""
    payload = {
        "model": DS_MODEL,
        "max_tokens": 2000,
        "thinking": {"type": "disabled"},  # 禁用思考, 直接输出text, 避免被thinking占满token
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    try:
        resp = requests.post(DS_URL, headers={
            "x-api-key": DS_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }, json=payload, timeout=60)
        if resp.status_code != 200:
            return None
        data = resp.json()
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        return parse_actions(text)
    except Exception as e:
        return None


def parse_actions(text):
    """从LLM输出解析动作数组, 容错处理"""
    # 提取JSON数组
    m = re.search(r'\[.*\]', text, re.DOTALL)
    if not m:
        return None
    try:
        arr = json.loads(m.group(0))
        # 规范化: 确保有action_text和action_type
        actions = []
        for a in arr:
            if isinstance(a, dict) and a.get("action_text"):
                actions.append({
                    "action_text": str(a["action_text"]).strip(),
                    "action_type": str(a.get("action_type", infer_type(a["action_text"]))).strip(),
                })
        return actions if actions else None
    except Exception:
        return None


def infer_type(text):
    if "锁定" in text: return "lock"
    if "起飞" in text: return "launch_uav"
    if "降落" in text: return "land_uav"
    if "移动" in text: return "move"
    if "飞行" in text: return "fly"
    return "noop"


# ═══════════════════════════════════════════════
def main():
    print("=" * 60)
    print("LLM泛化海战agent (DeepSeek驱动)")
    print("=" * 60)

    r = api("POST", "/start", json={"script_name": "测试用例1"})
    if not r:
        print("START FAILED (检查环境是否运行)"); return
    print(f"启动: {r.get('说明', r)}")

    history = []
    step = 0
    max_steps = 100  # 限制步数避免无限跑

    while step < max_steps:
        step += 1

        # 获取公平观测
        obs_text = api("GET", "/obs")
        legal_text = api("GET", "/legal_actions")
        if not obs_text or not legal_text:
            # 检查是否结束
            st = api("GET", "/status")
            if st and isinstance(st, dict) and st.get("已结束"):
                print(f"\n对局结束: {st.get('对局结果')}")
                break
            print("  (获取观测失败, 跳过)"); time.sleep(1); continue

        # 检查是否已结束
        if isinstance(legal_text, dict) and "detail" in legal_text:
            st = api("GET", "/status")
            if st and isinstance(st, dict) and st.get("已结束"):
                print(f"\n对局结束: {st.get('对局结果')}")
                break

        # LLM决策
        legal_str = json.dumps(legal_text, ensure_ascii=False) if isinstance(legal_text, dict) else str(legal_text)
        history_str = "\n".join(history[-6:]) if history else "无"
        actions = call_deepseek(obs_text, legal_str, history_str)

        if not actions:
            # LLM失败, 用noop兜底
            actions = [{"action_text": "空操作，等待一个宏观步 [noop]", "action_type": "noop"}]
            print(f"  step={step} LLM解析失败, 用noop")

        # 执行
        api("POST", "/apply", json={"actions": actions})
        history.append(json.dumps([a["action_text"][:50] for a in actions], ensure_ascii=False))

        if step % 5 == 0:
            st = api("GET", "/status")
            if st and isinstance(st, dict):
                s = st.get("资源快照", {}).get("统计", {})
                sc = st.get("奖励信号", {})
                print(f"  step={step} t={st.get('局内时间')} "
                      f"敌可见={s.get('enemy_visible',0)} "
                      f"击杀={sc.get('black_killed',0)} "
                      f"我方USV={s.get('usv_alive')}/{s.get('usv_total')} "
                      f"UAV={s.get('uav_alive')}/{s.get('uav_total')}")

        time.sleep(0.5)

    # 结果
    print("\n" + "=" * 60)
    r = api("GET", "/result")
    if isinstance(r, dict):
        print(f"结果: {r.get('对局结果')} — {r.get('结果说明')}")
        sc = r.get('奖励信号', {})
        print(f"击杀: {sc.get('black_killed',0)} 损失USV: {sc.get('white_ship_killed',0)} 损失UAV: {sc.get('white_uav_killed',0)} 突破: {sc.get('black_breakthrough',0)}")
    api("GET", "/stop")
    print("Done")


if __name__ == "__main__":
    main()
