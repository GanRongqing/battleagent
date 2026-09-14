"""
致胜策略 v7 — 简化UAV管理, 确保存活
关键: UAV低速(20m/s)飞行+定期转向, 永不出界
接敌时间: ~7857s ≈ 262步
UAV在接敌前100步起飞, 保证在战场中线提供探测
"""
import requests, json, time

API = "http://127.0.0.1:8000"
WAIT = 0.7
STEP_S = 30  # MACRO_STEP_DURATION
RATIO = 50   # 仿真比例
ENGAGEMENT_T = 7857  # 接敌时间(sim seconds)
ENGAGEMENT_STEP = ENGAGEMENT_T // STEP_S  # ≈262

def api(m, p, **kw):
    try:
        r = requests.request(m, f"{API}{p}", json=kw.get("json"), timeout=10)
        if r.status_code == 200:
            ct = r.headers.get("content-type", "")
            return r.json() if "application/json" in ct else r.text
        return {"e": r.status_code}
    except: return {"e": "conn"}

def start(): return api("POST","/start",json={"script_name":"测试用例1"})
def apply(a): return api("POST","/apply",json={"actions":a})
def status(): return api("GET","/status")
def result(): return api("GET","/result")
def stop(): return api("GET","/stop")
def legal(): return api("GET","/legal_actions")

def st(): s=status(); return s if isinstance(s,dict) else None
def alive_usvs():
    s=st()
    if not s: return [f"white_usv{i}" for i in range(1,6)]
    return [u["name"] for u in s.get("资源快照",{}).get("单位状态",{}).get("white_usv_states",[]) if u.get("is_alive")]
def flying_uavs():
    s=st()
    if not s: return [],[]
    us=s.get("资源快照",{}).get("单位状态",{}).get("white_uav_states",[])
    return [u["name"] for u in us if u.get("is_alive") and not u.get("is_at_usv")], \
           [u["name"] for u in us if u.get("is_alive") and u.get("is_at_usv")]
def get_locks():
    la=legal()
    if not isinstance(la,dict): return set()
    av=set()
    for lt in la.get("动作",{}).get("[lock]",[]):
        p=lt.split()
        if len(p)>=3: av.add(p[2].split("（")[0])
    return av

# ═══════════════════════════════════════
print("="*60)
print("启动")
print("="*60)
print(start().get("说明","?"))

# ═══ 阶段1: USV向东推进, UAV暂不出动 ═══
# USV保持向东, 等接近接敌距离再起飞UAV
print("\n阶段1: USV向东 + UAV暂留甲板")
for step in range(1, ENGAGEMENT_STEP - 80):  # ~182步, 到t≈5460s
    usvs = alive_usvs()
    apply([{"action_text":f"{n} 移动 target_speed=18.0 target_course=90.0","action_type":"move"} for n in usvs])
    time.sleep(WAIT)
    if step % 60 == 0:
        s=st()
        if s:
            ss=s.get("资源快照",{}).get("统计",{})
            print(f"  step={step} t={s.get('局内时间')} usv={ss.get('usv_alive')}/{ss.get('usv_total')}")

# ═══ 阶段2: 起飞UAV, 低速向东侦察 ═══
# 此时t≈5460s, USV在x≈98km, 黑方在x≈205km, 距离107km
# UAV起飞向东20m/s, 飞80步=2400s, 到达x≈98k+48k=146km
# UAV雷达60km覆盖86-206km, 刚好能看到黑方(x≈205-10*2400=181km)
print(f"\n阶段2: 起飞UAV侦察 (step={ENGAGEMENT_STEP-80})")
actions = []
for i in range(1, 6):
    actions.append({
        "action_text": f"white_uav{i} 从 white_usv{i} 起飞 target_speed=25.0 target_course=90.0",
        "action_type": "launch_uav"
    })
for i in range(1, 6):
    actions.append({
        "action_text": f"white_usv{i} 移动 target_speed=18.0 target_course=90.0",
        "action_type": "move"
    })
apply(actions)
time.sleep(WAIT)

# ═══ 阶段3: UAV巡航 + USV接近到40km ═══
# 剩余80步到接敌, UAV低速巡航保持位置
print(f"\n阶段3: 巡航+接敌 (80步)")
uav_course = 90
for step in range(1, 100):  # 多给20步余量
    usvs = alive_usvs()
    flying, on_deck = flying_uavs()
    available = get_locks()

    actions = []
    # USV: 有目标就锁, 否则继续向东
    if available and usvs:
        tgt = sorted(available)[0]
        for n in usvs:
            actions.append({"action_text":f"{n} 锁定 {tgt}","action_type":"lock"})
        for n in usvs:
            actions.append({"action_text":f"{n} 移动 target_speed=18.0 target_course=90.0","action_type":"move"})
    else:
        for n in usvs:
            actions.append({"action_text":f"{n} 移动 target_speed=18.0 target_course=90.0","action_type":"move"})

    # UAV: 低速巡航, 每20步转向
    if step % 20 == 0:
        uav_course = 270 if uav_course == 90 else 90
    for n in flying:
        actions.append({"action_text":f"{n} 飞行 target_speed=15.0 target_course={float(uav_course)}","action_type":"fly"})

    apply(actions)
    time.sleep(WAIT)

    if step % 15 == 0 or available:
        s=st()
        if s:
            ss=s.get("资源快照",{}).get("统计",{})
            sc=s.get("奖励信号",{})
            print(f"  step={step:3d} t={s.get('局内时间')} e={ss.get('enemy_visible',0)} "
                  f"locks={len(available)} bk={sc.get('black_killed',0)} bh={sc.get('black_hit',0)} "
                  f"ws={sc.get('white_ship_killed',0)} usv={ss.get('usv_alive')}/{ss.get('usv_total')} "
                  f"uav={ss.get('uav_alive')}/{ss.get('uav_total')}")

        if s and s.get("已结束"):
            break

# ═══ 阶段4: 持续战斗 ═══
print("\n阶段4: 持续战斗")
current_target = None
for cstep in range(1, 100):
    s=st()
    if s and s.get("已结束"): break

    usvs = alive_usvs()
    flying, _ = flying_uavs()
    available = get_locks()

    actions = []
    if available and usvs:
        targets = sorted(available)
        if current_target not in available:
            current_target = targets[0]
            print(f"  >>> 目标: {current_target} <<<")

        for n in usvs:
            actions.append({"action_text":f"{n} 锁定 {current_target}","action_type":"lock"})
        for n in usvs:
            actions.append({"action_text":f"{n} 移动 target_speed=18.0 target_course=90.0","action_type":"move"})
    else:
        for n in usvs:
            actions.append({"action_text":f"{n} 移动 target_speed=18.0 target_course=90.0","action_type":"move"})
        for n in flying:
            actions.append({"action_text":f"{n} 飞行 target_speed=15.0 target_course={float(uav_course)}","action_type":"fly"})

    if not actions:
        actions.append({"action_text":"空操作，等待一个宏观步 [noop]","action_type":"noop"})

    apply(actions)
    time.sleep(WAIT)

    if cstep % 10 == 0 or available:
        s=st()
        if s:
            ss=s.get("资源快照",{}).get("统计",{})
            sc=s.get("奖励信号",{})
            print(f"  step={cstep:3d} t={s.get('局内时间')} e={ss.get('enemy_visible',0)} "
                  f"locks={len(available)} bk={sc.get('black_killed',0)} bh={sc.get('black_hit',0)} "
                  f"ws={sc.get('white_ship_killed',0)} usv={ss.get('usv_alive')}/{ss.get('usv_total')}")

# ═══ 结果 ═══
print("\n"+"="*60)
res=result()
if isinstance(res,dict):
    print(f"结果: {res.get('对局结果')} — {res.get('结果说明')}")
    print(f"奖励: {json.dumps(res.get('奖励信号',{}), ensure_ascii=False)}")
stop()
