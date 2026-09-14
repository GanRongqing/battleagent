"""
优先防御策略 — 保守拦截, 保命优先
=================================
核心: 不像进攻那样激进压上, USV保持更远距离(33-38km)游走锁定,
      UAV延迟起飞低速巡航(减少损耗), 被锁立即后撤, 绝不深入黑方射程

区别于优先进攻:
  进攻: SAFE_MIN=30.5km, UAV满速突前180km, 激进
  防御: SAFE_MIN=33km,  UAV延迟起飞低速, 保守

目标: 击杀黑方阻止突破, 同时最大化USV存活
"""
import requests, json, time, math

API = "http://127.0.0.1:8000"
WAIT = 0.3
USV_SPEED = 18
SAFE_MIN = 33_000   # 低于此距离后撤(保守: 33km)
SAFE_MAX = 38_000   # 高于此距离前进
UAV_LAUNCH_STEP = 50  # 延迟起飞(t=1500s)
UAV_CRUISE_X = 100_000  # UAV巡航位置(比进攻180km靠后, 保守)

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
print("优先防御策略 — 保守拦截")
print("="*60)
r=start()
if not r: print("START FAILED"); exit(1)
print(f"episode={r.get('对局编号')}")

# 阶段0: USV全速向东推进(部署到防线)
actions = []
for i in range(1, 6):
    actions.append({"action_text":f"white_usv{i} 移动 target_speed={USV_SPEED}.0 target_course=90.0","action_type":"move"})
apply(actions)
time.sleep(WAIT)

killed = 0
killed_targets = set()
uav_launched = False
uav_reached = False

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

    # 延迟起飞UAV
    if step >= UAV_LAUNCH_STEP and not uav_launched:
        print(f"\n  [{s.get('局内时间')}] UAV延迟起飞")
        apply([{"action_text":f"white_uav{i} 从 white_usv{i} 起飞 target_speed=40.0 target_course=90.0","action_type":"launch_uav"} for i in range(1,6)])
        uav_launched = True
        time.sleep(WAIT)
        s = st()

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

    # ── UAV充电管理: 计算返航目标(低电量UAV) + 处理停靠/起飞 ──
    return_targets = {}
    if uavs:
        # 收集存活USV信息: 名字 + 位置 + 已停UAV
        usv_info = []
        for u in alive_usv:
            p = u.get("position", [0, 0])
            usv_info.append({
                "name": u["name"],
                "x": p[0] if p else 0,
                "y": p[1] if len(p) > 1 else 0,
                "parked": [n for n in (u.get("uav") or [])],
            })
        # 停靠的UAV: 充满则重新起飞
        for u in uavs:
            if not u.get("is_alive"): continue
            nm = u["name"]
            batt = u.get("battery_format", 100)
            is_flying = not u.get("is_at_usv", True)
            if not is_flying and batt >= 90:
                actual_home = u.get("home_name", "")
                if actual_home:
                    apply([{"action_text":f'{nm} 从 {actual_home} 起飞 target_speed=40.0 target_course=90.0',"action_type":"launch_uav"}])
                    time.sleep(0.03)

        # 低电量飞行中的UAV: 分配返航母艇(每艘母艇只停1架UAV)
        # 按电量从低到高排序, 电量最低的优先选母艇
        low_batt_uavs = []
        for u in uavs:
            if not u.get("is_alive"): continue
            is_flying = not u.get("is_at_usv", True)
            if not is_flying: continue  # 已在母艇上
            batt = u.get("battery_format", 100)
            if batt >= 35: continue  # 电量充足
            up = u.get("position", [0, 0])
            low_batt_uavs.append({
                "name": u["name"],
                "batt": batt,
                "x": up[0] if up else 0,
                "y": up[1] if len(up) > 1 else 0,
            })
        # 电量最低的先分配
        low_batt_uavs.sort(key=lambda x: x["batt"])
        assigned_usv = set()  # 已分配的母艇
        for lu in low_batt_uavs:
            best, best_dist = None, float('inf')
            for usv in usv_info:
                if usv["name"] in assigned_usv: continue  # 母艇已被其他UAV占用
                if len(usv["parked"]) >= 1: continue  # 已停UAV
                d = math.hypot(usv["x"]-lu["x"], usv["y"]-lu["y"])
                if d < best_dist:
                    best_dist, best = d, usv["name"]
            if best:
                return_targets[lu["name"]] = best
                assigned_usv.add(best)
        # DEBUG: 打印返航目标
        if step % 25 == 0 and return_targets:
            print(f"    [充电] 返航: {return_targets}")

    # ── 锁定: 逐艘单独发送 ──
    for u in alive_usv:
        nm = u["name"]
        t = usv_target.get(nm)
        if t and not (u.get("is_locking") and u.get("locking_unit") == t):
            apply([{"action_text":f'{nm} 锁定 {t}',"action_type":"lock"}])
            time.sleep(0.03)

    # ── USV移动: 保守游走锁定(33-38km) + 被锁后撤 + 边界保护 ──
    move_actions = []
    for u in alive_usv:
        nm = u["name"]
        course = 90
        spd = USV_SPEED
        ux = u.get("position",[0,0])[0] if u.get("position") else 0

        # 被锁或冻结 → 立即后撤(防御核心: 保命)
        if u.get("is_locked") or u.get("is_frozen"):
            course = 270
            spd = USV_SPEED
        elif ux < 5_000:
            course = 90
            spd = USV_SPEED
        elif ux > 295_000:
            course = 270
            spd = USV_SPEED
        else:
            # 保守游走锁定
            t = usv_target.get(nm)
            if t and t in enemy_pos:
                ex, ey = enemy_pos[t]
                uy = u.get("position",[0,0])[1] if u.get("position") else 0
                dist = math.hypot(ex-ux, ey-uy)
                if dist < SAFE_MIN:
                    course = 270  # 太近, 后撤(保守)
                    spd = USV_SPEED
                elif dist > SAFE_MAX:
                    course = 90  # 太远, 前进
                    spd = USV_SPEED
                else:
                    course = 90  # 安全区间, 缓慢跟随
                    spd = 10
            else:
                course = 90
                spd = USV_SPEED
        move_actions.append({"action_text":f"{nm} 移动 target_speed={float(spd)} target_course={float(course)}","action_type":"move"})

    # ── UAV移动: 低电量UAV返航, 其他正常巡航 ──
    # 收集母艇位置用于返航计算
    usv_pos_map = {}
    for u in alive_usv:
        p = u.get("position", [0, 0])
        usv_pos_map[u["name"]] = (p[0] if p else 0, p[1] if len(p) > 1 else 0)

    uav_x = {}
    for u in flying:
        if u.get("position"):
            uav_x[u["name"]] = u["position"][0]
    if flying and any(x >= UAV_CRUISE_X for x in uav_x.values()):
        uav_reached = True

    for u in flying:
        nm = u["name"]
        # 返航UAV: 飞向母艇, 接近后降落
        if nm in return_targets:
            home_name = return_targets[nm]
            if home_name in usv_pos_map:
                hx, hy = usv_pos_map[home_name]
                up = u.get("position", [0, 0])
                ux, uy = up[0] if up else 0, up[1] if len(up) > 1 else 0
                dist = math.hypot(hx-ux, hy-uy)
                if dist < 8_000:
                    # 已接近母艇, 降落
                    move_actions.append({"action_text":f'{nm} 降落到 {home_name}',"action_type":"land_uav"})
                else:
                    # 朝母艇飞行(计算方位角)
                    bearing = math.degrees(math.atan2(hx-ux, hy-uy)) % 360
                    move_actions.append({"action_text":f'{nm} 飞行 target_speed=40.0 target_course={bearing:.1f}',"action_type":"fly"})
            continue
        # 正常巡航UAV
        ux = uav_x.get(nm, 0)
        if uav_reached:
            # 在100km附近低速巡航, 朝西雷达对准黑方
            if ux < (UAV_CRUISE_X - 5_000):
                move_actions.append({"action_text":f'{nm} 飞行 target_speed=25.0 target_course=90.0',"action_type":"fly"})
            elif ux > (UAV_CRUISE_X + 5_000):
                move_actions.append({"action_text":f'{nm} 飞行 target_speed=25.0 target_course=270.0',"action_type":"fly"})
            else:
                move_actions.append({"action_text":f'{nm} 飞行 target_speed=5.0 target_course=270.0',"action_type":"fly"})
        else:
            # 前出到100km
            move_actions.append({"action_text":f'{nm} 飞行 target_speed=40.0 target_course=90.0',"action_type":"fly"})

    if move_actions:
        apply(move_actions)

    time.sleep(WAIT - 0.05)

    if step % 25 == 0 or new_kills != killed:
        s2 = st()
        if s2:
            ss = s2.get("资源快照",{}).get("统计",{})
            sc2 = s2.get("奖励信号",{})
            killed = sc2.get("black_killed",0)
            pos_info = []
            for u in s2.get("资源快照",{}).get("单位状态",{}).get("white_usv_states",[]):
                if u.get("is_alive"):
                    p = u.get("position",[0,0])
                    pos_info.append(f'{u["name"][-1]}:{p[0]/1000:.0f}k')
            # UAV电量信息
            uav_info = []
            for u in s2.get("资源快照",{}).get("单位状态",{}).get("white_uav_states",[]):
                if u.get("is_alive"):
                    b = u.get("battery_format", -1)
                    pos = "飞" if not u.get("is_at_usv", True) else "舰"
                    uav_info.append(f'{u["name"][-1]}:{b:.0f}%{pos}')
            print(f"  {step:3d} t={s2.get('局内时间')} e={ss.get('enemy_visible',0)} "
                  f"bk={killed} bh={sc2.get('black_hit',0)} "
                  f"ws={sc2.get('white_ship_killed',0)} "
                  f"usv={ss.get('usv_alive')}/{ss.get('usv_total')} "
                  f"uav={ss.get('uav_alive')}/{ss.get('uav_total')} | {' '.join(pos_info)} | UAV:{' '.join(uav_info)}")

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
