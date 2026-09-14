"""
优先进攻策略 v2 — 游走锁定 (安全距离压制)
=========================================
核心: UAV满速突前侦察(60km), USV在30-38km安全区间锁定黑方
  关键: 黑方30km雷达才发现在我们, 我方USV雷达35km+UAV网络能在40km锁定
  保持距离>30km → 黑方永远看不到我们 → 我们单方面锁定黑方!

锁定逻辑:
  distance > 38km → 全速前进(90°)
  32km < distance < 38km → 锁定黑方 + 缓慢跟随
  distance < 32km → 后撤(270°)脱离黑方30km探测
  一旦is_locked(被黑方锁) → 立即后撤脱离40km
"""
import requests, json, time, math

API = "http://127.0.0.1:8000"
WAIT = 0.3
UAV_SPEED = 100
USV_SPEED = 18
SAFE_MIN = 30_500   # 低于此距离后撤(31km,黑方30km雷达边界外)
SAFE_MAX = 36_000   # 高于此距离前进(36km,USV雷达35km能覆盖)
RETREAT_DIST = 45_000  # 被锁后撤到45km再重新接近

def api(m, p, **kw):
    try:
        r = requests.request(m, f"{API}{p}", json=kw.get("json"), timeout=10)
        if r.status_code == 200:
            ct = r.headers.get("content-type","")
            return r.json() if "application/json" in ct else r.text
    except: pass
    return None

def start(): return api("POST","/start",json={"script_name":"测试用例1"})
def apply(a): return api("POST","/apply",json={"actions":a})
def status(): return api("GET","/status")
def result(): return api("GET","/result")
def stop(): return api("GET","/stop")

def st(): s=status(); return s if isinstance(s,dict) else {}
def locks():
    la=api("GET","/legal_actions")
    if not isinstance(la,dict): return set()
    return {lt.split()[2].split("（")[0] for lt in la.get("动作",{}).get("[lock]",[]) if len(lt.split())>=3}

def get_enemy_positions(s):
    """从status提取黑方位置 {name: [x,y]}"""
    obs = s.get("资源快照",{}).get("观察信息",{}).get("white_observation",{})
    result = {}
    for e in obs.get("雷达捕获",[]) or []:
        if e.get("name") and e.get("position"):
            result[e["name"]] = e["position"][:2]
    return result

# ═══════════════════════════════════
print("="*60)
print("优先进攻 v2 — 游走锁定")
print("="*60)
r=start()
if not r: print("START FAILED"); exit(1)
print(f"episode={r.get('对局编号')}")

# t=0: 起飞UAV满速突前 + USV全速推进
actions = []
for i in range(1, 6):
    actions.append({"action_text":f"white_uav{i} 从 white_usv{i} 起飞 target_speed={UAV_SPEED}.0 target_course=90.0","action_type":"launch_uav"})
for i in range(1, 6):
    actions.append({"action_text":f"white_usv{i} 移动 target_speed={USV_SPEED}.0 target_course=90.0","action_type":"move"})
apply(actions)
time.sleep(WAIT)

killed = 0
killed_targets = set()
uav_dir = 90
uav_dash_done = False
UAV_DASH_STEPS = 50  # 满速冲到x≈150km后悬停侦察

# 目标分配: USV名 → 黑方y
BLACK_Y = {'1':537000,'2':487000,'3':337000,'4':137000,'5':187000}
def nearest_target(usv_name, available):
    """为USV分配y最近的目标"""
    u_num = usv_name.split('usv')[1]
    uy = BLACK_Y.get(u_num, 337000)
    best_t, best_d = None, float('inf')
    for t in available:
        t_num = t.split('usv')[1] if 'usv' in t else '3'
        d = abs(uy - BLACK_Y.get(t_num, 337000))
        if d < best_d:
            best_d, best_t = d, t
    return best_t

for step in range(1, 701):
    s = st()
    if s.get("已结束"): break

    # UAV前出转巡航
    if step >= UAV_DASH_STEPS and not uav_dash_done:
        uav_dash_done = True
        print(f"\n  [{s.get('局内时间')}] UAV前出到位")

    available = locks()
    available = {t for t in available if t not in killed_targets}
    sc = s.get("奖励信号", {})
    new_kills = sc.get("black_killed", 0)
    if new_kills != killed:
        killed = new_kills
        print(f"\n  ★ 击杀! 总计={killed} ★")

    usvs = s.get("资源快照",{}).get("单位状态",{}).get("white_usv_states",[])
    alive_usv = [u for u in usvs if u.get("is_alive")] if usvs else []
    uavs = s.get("资源快照",{}).get("单位状态",{}).get("white_uav_states",[])
    flying = [u for u in uavs if u.get("is_alive") and not u.get("is_at_usv")] if uavs else []
    enemy_pos = get_enemy_positions(s)

    # 每艘USV的目标
    usv_target = {}
    for u in alive_usv:
        nm = u["name"]
        t = nearest_target(nm, available)
        if t: usv_target[nm] = t

    # ── 锁定: 逐艘单独发送(一艘失败不影响其他) ──
    for u in alive_usv:
        nm = u["name"]
        t = usv_target.get(nm)
        if t and not (u.get("is_locking") and u.get("locking_unit") == t):
            # 单艘发送, 失败不影响其他USV
            apply([{"action_text":f'{nm} 锁定 {t}',"action_type":"lock"}])
            time.sleep(0.03)

    # ── USV移动: 游走锁定(31-36km安全区间) + 被锁后撤 + 边界保护 ──
    move_actions = []
    for u in alive_usv:
        nm = u["name"]
        course = 90  # 默认前进
        spd = USV_SPEED
        ux = u.get("position",[0,0])[0] if u.get("position") else 0

        # 被黑方锁了或冻结 → 立即后撤脱离
        if u.get("is_locked") or u.get("is_frozen"):
            course = 270
            spd = USV_SPEED
        # 边界保护: 只防追出区域
        elif ux < 5_000:
            course = 90
            spd = USV_SPEED
        elif ux > 295_000:
            course = 270
            spd = USV_SPEED
        else:
            # 游走锁定: 根据与目标距离控制
            t = usv_target.get(nm)
            if t and t in enemy_pos:
                ex, ey = enemy_pos[t]
                uy = u.get("position",[0,0])[1] if u.get("position") else 0
                dist = math.hypot(ex-ux, ey-uy)
                if dist < SAFE_MIN:
                    course = 270  # 太近(进入黑方30km探测), 后撤
                    spd = USV_SPEED
                elif dist > SAFE_MAX:
                    course = 90  # 太远, 前进接近
                    spd = USV_SPEED
                else:
                    course = 90  # 安全区间, 缓慢跟随保持距离
                    spd = 10
            else:
                course = 90
                spd = USV_SPEED
        move_actions.append({"action_text":f"{nm} 移动 target_speed={float(spd)} target_course={float(course)}","action_type":"move"})

    # ── UAV: 满速冲到180km附近, 之后低速朝西巡航(雷达对准黑方来向) ──
    # 用位置控制, 不依赖步数
    uav_x = {}
    for u in flying:
        if u.get("position"):
            uav_x[u["name"]] = u["position"][0]
    uav_reached = any(x >= 170_000 for x in uav_x.values()) if uav_x else False
    if uav_reached:
        uav_dash_done = True
    if not uav_dash_done:
        # 前出阶段: 满速向东冲
        for u in flying:
            move_actions.append({"action_text":f'{u["name"]} 飞行 target_speed={UAV_SPEED}.0 target_course=90.0',"action_type":"fly"})
    else:
        for u in flying:
            ux = uav_x.get(u["name"], 0)
            # 维持x≈180km附近, 朝西(270°)雷达对准黑方
            if ux < 172_000:
                # 偏西了, 朝东回180km
                move_actions.append({"action_text":f'{u["name"]} 飞行 target_speed=25.0 target_course=90.0',"action_type":"fly"})
            elif ux > 188_000:
                # 偏东了, 朝西回180km
                move_actions.append({"action_text":f'{u["name"]} 飞行 target_speed=25.0 target_course=270.0',"action_type":"fly"})
            else:
                # 在180km附近, 低速5m/s朝西(雷达对准西方黑方)
                move_actions.append({"action_text":f'{u["name"]} 飞行 target_speed=5.0 target_course=270.0',"action_type":"fly"})

    if move_actions:
        apply(move_actions)

    time.sleep(WAIT - 0.05)

    if step % 25 == 0 or new_kills != killed:
        s2 = st()
        if s2:
            ss = s2.get("资源快照",{}).get("统计",{})
            sc2 = s2.get("奖励信号",{})
            killed = sc2.get("black_killed",0)
            # DEBUG: USV位置 + 到目标距离
            pos_info = []
            for u in s2.get("资源快照",{}).get("单位状态",{}).get("white_usv_states",[]):
                if u.get("is_alive"):
                    p = u.get("position",[0,0])
                    nm = u["name"]
                    t = usv_target.get(nm)
                    dist = "?"
                    if t and t in enemy_pos:
                        ex, ey = enemy_pos[t]
                        dist = f"{math.hypot(ex-p[0], ey-p[1])/1000:.0f}k"
                    pos_info.append(f'{nm[-1]}:({p[0]/1000:.0f}k,{p[1]/1000:.0f}k)->{dist}')
            print(f"  {step:3d} t={s2.get('局内时间')} e={ss.get('enemy_visible',0)} "
                  f"bk={killed} bh={sc2.get('black_hit',0)} "
                  f"ws={sc2.get('white_ship_killed',0)} "
                  f"usv={ss.get('usv_alive')}/{ss.get('usv_total')} "
                  f"uav={ss.get('uav_alive')}/{ss.get('uav_total')} | {' '.join(pos_info)}")

# ═══ 结果 ═══
print("\n"+"="*60)
r=result()
if isinstance(r,dict):
    won = "Victory" in str(r.get('对局结果',''))
    print(f"结果: {r.get('对局结果')} — {r.get('结果说明')}")
    sc=r.get('奖励信号',{})
    net=sc.get('black_killed',0)*10-sc.get('white_ship_killed',0)*10-sc.get('white_uav_killed',0)*3-sc.get('black_breakthrough',0)*20
    print(f"击杀: {sc.get('black_killed',0)} 损失USV: {sc.get('white_ship_killed',0)} 损失UAV: {sc.get('white_uav_killed',0)} 突破: {sc.get('black_breakthrough',0)}")
    print(f"净得分: {net}  {'🏆 VICTORY!' if won else '❌'}")
stop()
print("Done")
