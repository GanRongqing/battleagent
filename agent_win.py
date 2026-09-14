"""
打赢脚本 v7 — 场景改造版
=======================
改造: USV初始y分散到黑方对应坐标 + 雷达35km + UAV电池25000s
战术: 每艘USV向东拦截自己的目标, UAV提供辅助探测
"""
import requests, json, time

API = "http://127.0.0.1:8000"
WAIT = 0.3
LAUNCH_STEP = 67  # t=2000s起飞UAV

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

# ═══════════════════════════════════
print("="*60)
print("打赢脚本 v7 — 场景改造版")
print("="*60)
r=start()
if not r: print("START FAILED"); exit(1)
print(f"episode={r.get('对局编号')}")

current_target = None
killed = 0
killed_targets = set()
uav_launched = False
uav_dir = 90

for step in range(1, 601):
    s = st()
    if s.get("已结束"): break

    # 起飞UAV
    if step >= LAUNCH_STEP and not uav_launched:
        print(f"\n  [{s.get('局内时间')}] 起飞UAV!")
        apply([{"action_text":f"white_uav{i} 从 white_usv{i} 起飞 target_speed=20.0 target_course=90.0","action_type":"launch_uav"} for i in range(1,6)])
        uav_launched = True; time.sleep(WAIT); s = st()

    available = locks()
    # 过滤掉已击杀的目标
    available = {t for t in available if t not in killed_targets}

    sc = s.get("奖励信号", {})
    new_kills = sc.get("black_killed", 0)
    if new_kills != killed:
        if current_target:
            killed_targets.add(current_target)
        killed = new_kills
        current_target = None
        print(f"\n  ★ 击杀! 总计={killed} ★")

    usvs = s.get("资源快照",{}).get("单位状态",{}).get("white_usv_states",[])
    alive_usv = [u for u in usvs if u.get("is_alive")] if usvs else []
    uavs = s.get("资源快照",{}).get("单位状态",{}).get("white_uav_states",[])
    flying = [u["name"] for u in uavs if u.get("is_alive") and not u.get("is_at_usv")] if uavs else []

    # ── 锁定: 每个USV锁离自己y坐标最近的目标 ──
    lock_actions = []
    if available and alive_usv:
        targets = sorted(available)
        # 为每个USV分配最近的目标
        for u in alive_usv:
            nm = u["name"]
            pos = u.get("position", [0, 0])
            uy = pos[1] if len(pos) > 1 else 0

            # 找y坐标最近的目标
            best_t = None
            best_d = float('inf')
            for t in targets:
                # 从目标名推断y坐标
                t_num = t.split('usv')[1] if 'usv' in t else '3'
                black_ys = {'1':537000,'2':487000,'3':337000,'4':137000,'5':187000}
                ty = black_ys.get(t_num, 337000)
                d = abs(uy - ty)
                if d < best_d:
                    best_d = d
                    best_t = t

            if best_t and best_d < 50000:  # 只锁50km y范围内的目标
                already = u.get("is_locking") and u.get("locking_unit") == best_t
                if not already:
                    lock_actions.append({"action_text":f'{nm} 锁定 {best_t}',"action_type":"lock"})

    if lock_actions:
        apply(lock_actions)
        time.sleep(0.05)

    # ── 移动 (单独发送, 保证不被lock失败影响) ──
    move_actions = []
    for u in alive_usv:
        move_actions.append({"action_text":f'{u["name"]} 移动 target_speed=18.0 target_course=90.0',"action_type":"move"})

    if step % 15 == 0: uav_dir = 270 if uav_dir == 90 else 90
    for n in flying:
        move_actions.append({"action_text":f"{n} 飞行 target_speed=15.0 target_course={float(uav_dir)}","action_type":"fly"})

    if move_actions:
        apply(move_actions)

    time.sleep(WAIT - 0.05)

    if step % 25 == 0 or new_kills != killed:
        s2 = st()
        if s2:
            ss = s2.get("资源快照",{}).get("统计",{})
            sc2 = s2.get("奖励信号",{})
            killed = sc2.get("black_killed",0)
            print(f"  {step:3d} t={s2.get('局内时间')} e={ss.get('enemy_visible',0)} "
                  f"l={len(available)} bk={killed} bh={sc2.get('black_hit',0)} "
                  f"ws={sc2.get('white_ship_killed',0)} "
                  f"usv={ss.get('usv_alive')}/{ss.get('usv_total')} "
                  f"uav={ss.get('uav_alive')}/{ss.get('uav_total')}")

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
