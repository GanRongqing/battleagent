"""
优先侦察 → 打赢 v9 (v7改良版)
================================
1. 全队向东, UAV暂留 (0~180步)
2. 起飞UAV侦察 (180步=5400s)
3. UAV巡航 + USV接敌, 5v1先杀black_usv3
4. 杀完center后: 2北上, 2南下, 1留守追击剩余黑方艇
"""
import requests, json, time

API = "http://127.0.0.1:8000"
WAIT = 0.7

def api(m, p, **kw):
    try:
        r = requests.request(m, f"{API}{p}", json=kw.get("json"), timeout=10)
        if r.status_code == 200:
            ct = r.headers.get("content-type","")
            return r.json() if "application/json" in ct else r.text
        return None
    except: return None

def start(): return api("POST","/start",json={"script_name":"测试用例1"})
def apply(a): return api("POST","/apply",json={"actions":a})
def status(): return api("GET","/status")
def result(): return api("GET","/result")
def stop(): return api("GET","/stop")
def obs(): return api("GET","/obs")

def st():
    s=status()
    return s if isinstance(s,dict) else {}

def get_locks():
    la=api("GET","/legal_actions")
    if not isinstance(la,dict): return set()
    av=set()
    for lt in la.get("动作",{}).get("[lock]",[]):
        p=lt.split()
        if len(p)>=3: av.add(p[2].split("（")[0])
    return av

def info():
    """获取简要状态"""
    s=st()
    if not s: return "NO_STATUS"
    rs=s.get("资源快照",{}).get("统计",{})
    sc=s.get("奖励信号",{})
    return (f"t={s.get('局内时间')} e={rs.get('enemy_visible',0)} "
            f"bk={sc.get('black_killed',0)} bh={sc.get('black_hit',0)} "
            f"ws={sc.get('white_ship_killed',0)} "
            f"usv={rs.get('usv_alive')}/{rs.get('usv_total')} "
            f"uav={rs.get('uav_alive')}/{rs.get('uav_total')} f={rs.get('uav_flying')}")

# ============================================================
print("="*60)
print("优先侦察 → 打赢 v9")
print("="*60)
r=start()
if r: print(f"启动成功: episode={r.get('对局编号')}")

# ═══ 阶段1: USV向东推进, UAV暂留 (180步=5400s) ═══
print("\n阶段1: 向东推进 (180步)")
for step in range(1, 181):
    s=st()
    usvs=s.get("资源快照",{}).get("单位状态",{}).get("white_usv_states",[])
    alive_usv=[u["name"] for u in usvs if u.get("is_alive")] if usvs else [f"white_usv{i}" for i in range(1,6)]

    apply([{"action_text":f"{n} 移动 target_speed=18.0 target_course=90.0","action_type":"move"} for n in alive_usv])
    time.sleep(WAIT)
    if step%60==0: print(f"  {step:3d} {info()}")

# ═══ 阶段2: 起飞UAV侦察 ═══
print("\n阶段2: 起飞UAV侦察")
s=st()
usvs=s.get("资源快照",{}).get("单位状态",{}).get("white_uav_states",[])
ondeck=[u["name"] for u in usvs if u.get("is_alive") and u.get("is_at_usv")] if usvs else [f"white_uav{i}" for i in range(1,6)]
alive_usv=[u["name"] for u in s.get("资源快照",{}).get("单位状态",{}).get("white_usv_states",[]) if u.get("is_alive")] if s else [f"white_usv{i}" for i in range(1,6)]

actions=[]
for n in ondeck:
    actions.append({"action_text":f"{n} 从 white_usv{n[-1]} 起飞 target_speed=25.0 target_course=90.0","action_type":"launch_uav"})
for n in alive_usv:
    actions.append({"action_text":f"{n} 移动 target_speed=18.0 target_course=90.0","action_type":"move"})
apply(actions)
time.sleep(WAIT)
print(f"  {info()}")

# ═══ 阶段3: UAV巡航 + 接敌 (100步) ═══
print("\n阶段3: UAV巡航+接敌")
uav_dir=90
for step in range(1, 101):
    s=st()
    usvs=s.get("资源快照",{}).get("单位状态",{}).get("white_usv_states",[])
    uavs=s.get("资源快照",{}).get("单位状态",{}).get("white_uav_states",[])
    alive_usv=[u["name"] for u in usvs if u.get("is_alive")] if usvs else [f"white_usv{i}" for i in range(1,6)]
    flying=[u["name"] for u in uavs if u.get("is_alive") and not u.get("is_at_usv")] if uavs else []
    available=get_locks()

    actions=[]
    # 有目标就锁!
    if available and alive_usv:
        tgt=sorted(available)[0]
        for n in alive_usv:
            actions.append({"action_text":f"{n} 锁定 {tgt}","action_type":"lock"})
    for n in alive_usv:
        actions.append({"action_text":f"{n} 移动 target_speed=18.0 target_course=90.0","action_type":"move"})

    if step%15==0: uav_dir=270 if uav_dir==90 else 90
    for n in flying:
        actions.append({"action_text":f"{n} 飞行 target_speed=15.0 target_course={float(uav_dir)}","action_type":"fly"})

    apply(actions); time.sleep(WAIT)
    if step%20==0 or available: print(f"  {step:3d} {info()} locks={len(available)}")

# ═══ 阶段4: 战斗! 5v1先杀center, 然后分兵 ═══
print("\n阶段4: 战斗")
current_target=None
killed_count=0
uav_dir=90
SPLIT_AFTER_KILL=1  # 杀1个后分兵

for cstep in range(1, 300):
    s=st()
    if s.get("已结束"): break

    usvs=s.get("资源快照",{}).get("单位状态",{}).get("white_usv_states",[])
    uavs=s.get("资源快照",{}).get("单位状态",{}).get("white_uav_states",[])
    alive_usv=[u for u in usvs if u.get("is_alive")] if usvs else []
    flying=[u["name"] for u in uavs if u.get("is_alive") and not u.get("is_at_usv")] if uavs else []
    available=get_locks()
    sc=s.get("奖励信号",{})
    new_kills=sc.get("black_killed",0)

    actions=[]

    if available and alive_usv:
        targets=sorted(available)
        if current_target not in available:
            current_target=targets[0]
            print(f"\n  >>> 锁定: {current_target} (已击杀={new_kills}) <<<")

        # ── 分兵逻辑: 杀了center后分散 ──
        if new_kills >= SPLIT_AFTER_KILL and len(alive_usv) >= 4:
            # 北组: usv1+usv2 向北, 南组: usv4+usv5 向南
            courses = {
                "white_usv1": 0, "white_usv2": 0,     # 北
                "white_usv3": 90,                       # 东
                "white_usv4": 180, "white_usv5": 180,  # 南
            }
            for u in alive_usv:
                nm=u["name"]
                c=courses.get(nm,90)
                if nm in [f"white_usv{i}" for i in range(1,6)]:
                    actions.append({"action_text":f"{nm} 锁定 {current_target}","action_type":"lock"})
                actions.append({"action_text":f"{nm} 移动 target_speed=18.0 target_course={float(c)}","action_type":"move"})
        else:
            # 集中火力5v1
            for u in alive_usv:
                actions.append({"action_text":f'{u["name"]} 锁定 {current_target}',"action_type":"lock"})
                actions.append({"action_text":f'{u["name"]} 移动 target_speed=18.0 target_course=90.0',"action_type":"move"})
    else:
        # 没有目标: 维持航向
        for u in alive_usv:
            nm=u["name"]
            # 如果已经分兵, 保持分散航向
            if new_kills >= SPLIT_AFTER_KILL:
                c={"white_usv1":0,"white_usv2":0,"white_usv3":90,"white_usv4":180,"white_usv5":180}.get(nm,90)
            else:
                c=90
            actions.append({"action_text":f"{nm} 移动 target_speed=18.0 target_course={float(c)}","action_type":"move"})

    # UAV巡航
    if cstep%15==0: uav_dir=270 if uav_dir==90 else 90
    for n in flying:
        actions.append({"action_text":f"{n} 飞行 target_speed=15.0 target_course={float(uav_dir)}","action_type":"fly"})

    if not actions:
        actions.append({"action_text":"空操作，等待一个宏观步 [noop]","action_type":"noop"})

    apply(actions); time.sleep(WAIT)

    if cstep%20==0 or available or new_kills!=killed_count:
        killed_count=new_kills
        print(f"  {cstep:3d} {info()} locks={len(available)}")

    if s.get("已结束"): break

# ═══ 结果 ═══
print("\n"+"="*60)
r=result()
if isinstance(r,dict):
    print(f"结果: {r.get('对局结果')} — {r.get('结果说明')}")
    sc=r.get('奖励信号',{})
    print(f"奖励: {json.dumps(sc, ensure_ascii=False)}")
    net=sc.get('black_killed',0)*10-sc.get('white_ship_killed',0)*10-sc.get('white_uav_killed',0)*3-sc.get('black_breakthrough',0)*20
    print(f"净得分: {net}")
    print(f"存活: {json.dumps(r.get('存活统计',{}), ensure_ascii=False, indent=2)}")
stop()
print("Done")
