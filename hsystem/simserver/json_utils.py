"""
name: 刘文清
date: 2023-09-05
"""
import json
import json5
import random
from copy import deepcopy
import numpy as np

ENEMY_PROPERTY_M = "我"
ENEMY_PROPERTY_E = "敌"


def naive(config):
    """
    去掉配置字典中的说明文字，只保留键和值。
    配置字典的值可能是：字典、列表、布尔值、浮点值、整型、字符串
    {bool, dict, float, int, list, str}
    """
    
    if isinstance(config, dict):
        return {key: naive(value) for key, value in config.items()} if "value" not in config else naive(config["value"])
    
    if isinstance(config, list):
        return [naive(item) for item in config]
    
    return config


def load_yhgk_json(json_path, trim=True):
    """读取YHGK****.json配置, 并去除"value"

    Args:
        json_path (json): 配置json文件
        trim (bool): 是否修剪(去掉value层)

    Returns:
        config: 读入的配置字典
    """
    assert json_path is not None
    with open(json_path, 'r', encoding="UTF-8") as f:
        json_content = json5.load(f)
        json_config = naive(json_content) if trim else json_content
    return json_config


def dump_yhgk_json(json_path, json_config):
    assert json_path is not None
    assert json_config is not None
    with open(json_path, 'w', encoding="UTF-8") as f:
        json.dump(json_config, f, ensure_ascii=False, indent=4)


def _set_json_with_keylist(cur_config, key_list, key_idx, value):
    """为了屏蔽"value" 对set操作的影响，使用本方法递归查找对应

    Args:
        cur_config (dict, list): 当前配置
        key_list (list): key的列表
        key_idx (int): key_list的下标，表示递归的深度
        value (any): 需要set的具体值
    """
    assert key_idx < len(key_list), "下标越界！ %d >= %d" % (key_idx, len(key_list))
    cur_key = key_list[key_idx]
    if isinstance(cur_config, dict):
        if "value" in cur_config:
            _set_json_with_keylist(cur_config["value"], key_list, key_idx, value)  
        elif cur_key in cur_config:
            if key_idx == len(key_list) - 1:  
                cur_config[cur_key] = value
                return
            else:
                _set_json_with_keylist(cur_config[cur_key], key_list, key_idx + 1, value)  
        else:
            raise ("ERROR: key %s不在字典中" % (str(cur_key)))
    elif isinstance(cur_config, list):
        assert isinstance(cur_key, int), "ERROR: key %s非整数" % (str(cur_key))
        assert (cur_key >= 0 and cur_key < len(cur_config)) or (
                cur_key < 0 and cur_key >= -len(cur_config)), "ERROR: key %d下标越界%d" % (cur_key, len(cur_config))
        if key_idx == len(key_list) - 1:  
            cur_config[cur_key] = value
            return
        else:
            _set_json_with_keylist(cur_config[cur_key], key_list, key_idx + 1, value)  
    else:
        raise ("cur_config 类型错误 %s" % (type(cur_config)))
    return


def set_json_with_keylist(json_config, key_list, value):
    """设置json_config中的某个字段

    Args:
        json_config (dict): 读入的配置信息
        key_list (list): 关键字列表
        value (value): 需要设置的值

    Returns:
        dict: json_config，更新后的配置文件
    """
    _set_json_with_keylist(json_config, key_list, 0, value)
    return json_config


def _get_json_with_keylist(cur_config, key_list, key_idx):
    assert key_idx < len(key_list), "下标越界！ %d >= %d" % (key_idx, len(key_list))
    cur_key = key_list[key_idx]
    if isinstance(cur_config, dict):
        if "value" in cur_config:
            return _get_json_with_keylist(cur_config["value"], key_list, key_idx)
        elif cur_key in cur_config:
            if key_idx == len(key_list) - 1:
                return cur_config[cur_key]
            else:
                return _get_json_with_keylist(cur_config[cur_key], key_list, key_idx + 1)
        else:
            raise ("ERROR: key %s不在字典中" % (str(cur_key)))
    elif isinstance(cur_config, list):
        assert isinstance(cur_key, int), "ERROR: key %s非整数" % (str(cur_key))
        assert (cur_key >= 0 and cur_key < len(cur_config)) or (
                cur_key < 0 and cur_key >= -len(cur_config)), "ERROR: key %d下标越界%d" % (cur_key, len(cur_config))
        if key_idx == len(key_list) - 1:  
            return cur_config[cur_key]
        else:
            return _get_json_with_keylist(cur_config[cur_key], key_list, key_idx + 1)  
    else:
        raise ("cur_config 类型错误 %s" % (type(cur_config)))
        return None


def get_json_with_keylist(json_config, key_list):
    """读取json_config中的某个字段

    Args:
        json_config (dict): 读入的配置信息
        key_list (list): 关键字列表

    Returns:
        value: 返回查询的值
    """
    return _get_json_with_keylist(json_config, key_list, 0)


def get_war_ship(json_config, force_id, trimmed=True):
    """根据兵力id，从配置中查找该兵力的配置

    Args:
        json_config (dict): 读入的配置信息
        force_id (str): 兵力id

    Returns:
        dict: 该兵力的配置
    """
    war_ships = json_config["taskData"]["operUnit"]["warship"]
    for war_ship in war_ships:
        if force_id == get_json_value(war_ship, "shipGlobalId", trimmed):
            return war_ship
    return None


def get_airplan(json_config, model, trimmed=True):
    """根据飞机型号名称，从配置中查找该飞机的详细配置信息

    Args:
        json_config (dict): 读入的配置信息
        model (str): 飞机型号

    Returns:
        dict: 飞机的详细配置信息
    """
    airplans = json_config["taskData"]["operUnit"]["airplan"]
    for airplan in airplans:
        if model == get_json_value(airplan, "airplanName", trimmed):
            return airplan
    return None


def get_unit_from_operunit(json_config, force_id, trimmed=True):
    """根据兵力id，从配置中查找该兵力的配置

    Args:
        json_config (dict): 读入的配置信息
        force_id (str): 兵力id

    Returns:
        dict: 该兵力的配置
    """
    data = json_config["taskData"]["operUnit"]
    for k, v in data.items():
        if k not in ['airfield', 'landMissile']:
            continue
        for war_ship in v:
            if force_id == get_json_value(war_ship, f"{k}Id", trimmed):
                war_ship['__KEY__'] = k
                return war_ship
    return None


def get_war_ship_name(json_config, force_id, trimmed=True):
    """获取兵力的名字——舷号

    Args:
        json_config (dict): 读入的配置信息
        force_id (str): 兵力id

    Returns:
        str: 兵力的舷号
    """
    war_ship = get_war_ship(json_config, force_id, trimmed)
    return get_json_value(war_ship, "pennantNum", trimmed) if war_ship else None


def get_plane_name(json_config, force_id, trimmed=True):
    """从配置中根据兵力id，获得飞机的名字

    Args:
        json_config (dict): 读入的配置信息
        force_id (str): 飞机id

    Returns:
        str: 飞机的名字-attachNames
    """
    war_ships = json_config["taskData"]["operUnit"]["warship"]
    for war_ship in war_ships:
        for config_plane in war_ship["platformAttach"]:
            if "飞机" == get_json_value(config_plane, "attachClass", trimmed):
                attach_ids = get_json_value(config_plane, "attachIds", trimmed)
                for i, p_id in enumerate(attach_ids):
                    if p_id == force_id:
                        return get_json_value(config_plane, "attachNames", trimmed)[i]
    return None


def get_all_plane_id_to_name_dict(json_config, trimmed=True):
    plane_id_to_name_dict = dict()
    war_ships = json_config["taskData"]["operUnit"]["warship"]
    for war_ship in war_ships:
        for config_plane in war_ship["platformAttach"]:
            if "飞机" == get_json_value(config_plane, "attachClass", trimmed):
                attach_ids = get_json_value(config_plane, "attachIds", trimmed)
                attach_names = get_json_value(config_plane, "attachNames", trimmed)
                for i, p_id in enumerate(attach_ids):
                    if p_id:
                        plane_id_to_name_dict[p_id] = attach_names[i]
    return plane_id_to_name_dict


def get_war_ship_id_for_name(json_config, force_name, trimmed=True):
    """
    Args:
        json_config (dict): 读入的配置信息
        force_name (str): 兵力名称

    Returns:
        str: 该兵力的id
    """
    war_ships = json_config["taskData"]["operUnit"]["warship"]
    for war_ship in war_ships:
        if force_name == get_json_value(war_ship, "pennantNum", trimmed):
            return war_ship["shipGlobalId"]
    return None


def get_zz_point(json_config, trimmed=True):
    """从配置中读取zz点

    Args:
        json_config (dict): 读入的配置信息

    Returns:
        float,float: zz点的经度和纬度
    """
    zz_area = json_config["antiAirPlan"][0]["antiAirTask"]["antiAirArea"]
    lng = get_json_value(zz_area, "longitude", trimmed)
    lat = get_json_value(zz_area, "latitude", trimmed)
    return lng, lat


def get_threat_axis(json_config, trimmed=True):
    """从配置中读取威胁轴

    Args:
        json_config (dict): 读入的配置信息

    Returns:
        int: 威胁轴方向（度）
    """
    zz_area = json_config["antiAirPlan"][0]["antiAirTask"]["antiAirArea"]
    return get_json_value(zz_area, "threatAxis", trimmed)


def get_area_id(json_config, trimmed=True):
    """读取区域目标id

    Args:
        json_config (dict): 读入的配置信息

    Returns:
        str: 区域目标ID
    """
    air_area = json_config["antiAirPlan"][0]["antiAirTask"]["antiAirArea"]
    return get_json_value(air_area, "areaTargetId", trimmed)


def get_warfare_area(json_config):
    """查找数据

    Args:
        json_config (dict): 读入的配置信息

    Returns:
        dict: 区域数据
    """
    area_id = get_area_id(json_config)
    return get_area_for_area_id(json_config, area_id)


def get_submarine_search_area(json_config):
    """查找对潜搜索区域数据
    Args:
        json_config (dict): 读入的配置信息
    Returns:
        dict: 对潜搜索区域数据
    """
    area_id = json_config["antiSubmarPlan"][0]["antiSubmarTask"]["searchArea"][0]["areaTargetId"]
    return get_area_for_area_id(json_config, area_id)


def get_area_for_area_id(json_config, area_id):
    """根据区域id查找关联的区域数据

    Args:
        json_config (dict): 读入的配置信息
        area_id (str): 区域ID

    Returns:
        dict: 区域数据
    """
    air_areas = json_config["taskData"]["taskIntent"]["areaTarget"]
    for area in air_areas:
        if area["baseRegionId"] == area_id:
            return area
    return None


def get_air_scheme(json_config):
    """ 获取air_scheme """
    return json_config["antiAirPlan"][0]["antiAirScheme"]


def get_force_org_order(json_config):
    """
    取得防空队形数据
    Args:
        json_config: 方案数据
    Returns:
        防空队形数据
    """
    air_scheme = get_air_scheme(json_config)
    return air_scheme.get("forceOrgOrder", [])


def get_red_ship_names(json_config, trimmed=True):
    """
    Args:
        json_config: 方案数据
        trimmed: 方案是否预处理
    Returns:
    """
    names = []
    fleet_fmt = get_force_org_order(json_config)
    for dct in fleet_fmt:
        force_id = get_json_value(dct, "forceId", trimmed)
        ship_name = get_war_ship_name(json_config, force_id, trimmed)
        names.append(ship_name)
    return names


def get_red_force_name_list(json_config, trimmed=True):
    """
    Args:
        json_config (dict): 配置文件
        trimmed (bool, optional): json_config是否进行了裁剪. Defaults to True.

    Returns:
    """
    
    red_forces = json_config["antiAirPlan"][0]["antiAirTask"]["force"]
    return [get_json_value(force, "forceName", trimmed) for force in red_forces]


def get_red_plane_name_list(json_config, trimmed=True):
    """
    Args:
        json_config (dict): 总体配置文件
        trimmed (bool, optional): 是否json_config被修剪. Defaults to True.

    Returns:
    """
    red_forces = json_config["antiAirPlan"][0]["antiAirTask"]["force"]
    plane_model_list = ["BZK-005", "WZ2", "直-9C", "直-20F", "直-9S", "直-18F", "空警-500H", "歼-35", "歼-15D",
                        "歼-15T", "KE-600"]
    return [get_json_value(force, "forceName", trimmed) for force in red_forces if
            get_json_value(force, "forceModel", trimmed) in plane_model_list]


def get_air_wait_patrols(json_config):
    """读取防空巡逻区

    Args:
        json_config (dict): 读入的配置信息

    Returns:
        list(dict): 防空巡逻区
    """
    air_scheme = get_air_scheme(json_config)
    return air_scheme.get("airWaitPatrol", [])


def get_carrier_detail_info(json_config, enemy_property, trimmed=True):
    war_ships = json_config["taskData"]["operUnit"]["warship"]
    for war_ship in war_ships:
        if enemy_property in get_json_value(war_ship, "enemyProperty", trimmed) \
                and "" == get_json_value(war_ship, "platformType", trimmed):
            return war_ship
    return None


def get_red_carrier_name(json_config, trimmed=True):
    war_ship = get_carrier_detail_info(json_config, ENEMY_PROPERTY_M, trimmed)
    if war_ship:
        return get_json_value(war_ship, "pennantNum", trimmed)
    return None


def get_red_patrol_plane(json_config, trimmed=True):
    patrol_areas = get_air_wait_patrols(json_config)
    plane_id_to_name_dict = get_all_plane_id_to_name_dict(json_config, trimmed)
    patrol_planes = []
    for area in patrol_areas:
        patrol_forces = area["patrolForce"]
        for force in patrol_forces:
            force_id = get_json_value(force, "forceId", trimmed)
            force_name = plane_id_to_name_dict.get(force_id, None)
            if force_name:
                patrol_planes.append(force_name)
    return patrol_planes


def get_red_wait_plane(json_config, patrol_planes=None, trimmed=True):
    """
    Args:
        json_config (_type_): _description_
        patrol_planes (_type_, optional): _description_. Defaults to None.
        trimmed (bool, optional): _description_. Defaults to True.

    Returns:
        _type_: _description_
    """
    war_ships = json_config["taskData"]["operUnit"]["warship"]
    if not patrol_planes:
        patrol_planes = get_red_patrol_plane(json_config, trimmed)
    red_plane_name_list = set(get_red_plane_name_list(json_config, trimmed))
    return red_plane_name_list - set(patrol_planes)


def get_red_carrier_point(json_config, trimmed=True):
    war_ship = get_carrier_detail_info(json_config, ENEMY_PROPERTY_M, trimmed)
    if war_ship:
        
        longitude = get_json_value(war_ship, "longitude", trimmed)
        latitude = get_json_value(war_ship, "latitude", trimmed)
        return longitude, latitude
    return None


def get_red_carrier_attach_plane(json_config, trimmed=True):
    attach_plane_list = []
    war_ship = get_carrier_detail_info(json_config, ENEMY_PROPERTY_M, trimmed)
    if war_ship:
        
        platform_attach_list = war_ship["platformAttach"]
        for platform_attach in platform_attach_list:
            if get_json_value(platform_attach, "attachClass", trimmed) == "飞机":
                airplan_dict = get_airplan(json_config, get_json_value(platform_attach, "attachModel", trimmed),
                                           trimmed)
                attach_plane_list.append({
                    
                    "attachModel": get_json_value(platform_attach, "attachModel", trimmed),
                    
                    "attachNames": get_json_value(platform_attach, "attachNames", trimmed),
                    
                    "waitLevel": get_json_value(platform_attach, "waitLevel", trimmed),
                    "platformType": get_json_value(airplan_dict, "platformType", trimmed)
                })
    return attach_plane_list


def get_blue_carrier_name(json_config, trimmed=True):
    war_ship = get_carrier_detail_info(json_config, ENEMY_PROPERTY_E, trimmed)
    if war_ship:
        return get_json_value(war_ship, "pennantNum", trimmed)
    return None


def get_blue_carrier_point(json_config, trimmed=True):
    war_ship = get_carrier_detail_info(json_config, ENEMY_PROPERTY_E, trimmed)
    if war_ship:
        
        longitude = get_json_value(war_ship, "longitude", trimmed)
        latitude = get_json_value(war_ship, "latitude", trimmed)
        return longitude, latitude
    return None


def get_blue_force_name_list(json_config, force_type="all", trimmed=True):
    """
    Args:
        json_config (dict): 配置文件
        force_type (str): 兵力类型（all，ship，plane）
        trimmed (bool, optional): json_config是否进行了裁剪. Defaults to True.

    Returns:
    """
    ret_forces = []
    forces = json_config["antiAirPlan"][0]["antiAirTask"]["antiAirTarget"]
    plane_no_dict = {}
    for force in forces:
        cur_force_id = get_json_value(force, "attackTargetId", trimmed)
        war_ship = get_war_ship(json_config, cur_force_id)
        if war_ship is None:
            continue

        if force_type in ["all", "ship"]:
            ret_forces.append(get_json_value(war_ship, "pennantNum", trimmed))

        if force_type in ["all", "plane"]:
            for config_plane in war_ship["platformAttach"]:
                if get_json_value(config_plane, "attachClass", trimmed) != "飞机":
                    continue
                attach_model = get_json_value(config_plane, "attachModel", trimmed)
                attach_count_str = get_json_value(config_plane, "attachCount", trimmed)
                
                attach_count = int(attach_count_str) if attach_count_str else 0
                if attach_count:
                    cur_plane_no = plane_no_dict.get(attach_model, 0) + 1
                    for i in range(cur_plane_no, attach_count + cur_plane_no):
                        ret_forces.append(f"{attach_model}_{str(i).zfill(3)}")
                    plane_no_dict[attach_model] = i
    return ret_forces


def get_blue_plane_name_list(json_config, trimmed=True):
    """
    Args:
        json_config (dict): 总体配置文件
        trimmed (bool, optional): 是否json_config被修剪. Defaults to True.

    Returns:
    """
    return get_blue_force_name_list(json_config=json_config, force_type="plane", trimmed=trimmed)


def get_blue_aew_name(json_config, trimmed=True):
    """随机获取蓝方的一架预警机名称
    Args:
        json_config (dict): 读入的配置信息

    Returns:
        str: 蓝方某架预警机的名称
    """
    war_ships = json_config["taskData"]["operUnit"]["warship"]
    for war_ship in war_ships:
        enemy_property = get_json_value(war_ship, "enemyProperty", trimmed)
        if enemy_property == ENEMY_PROPERTY_M:
            continue

        for config_plane in war_ship["platformAttach"]:
            
            attach_class = get_json_value(config_plane, "attachClass", trimmed)
            if attach_class != "飞机":
                continue

            
            attach_model = get_json_value(config_plane, "attachModel", trimmed)
            airplane = get_airplan(json_config, attach_model, trimmed)
            
            if get_json_value(airplane, "platformType", trimmed) != "预警机":
                continue

            
            attach_count_str = get_json_value(config_plane, "attachCount", trimmed)
            
            attach_count = int(attach_count_str) if attach_count_str else 0
            if attach_count:
                
                plane_no = random.randint(1, attach_count)
                return f"{attach_model}_{str(plane_no).zfill(3)}"
    return None


def get_blue_battle_planes(json_config, plane_count=12, trimmed=True):
    """
    Args:
        json_config (dict): 读入的配置信息
    Returns:
    """
    ret = []
    blue_planes = get_blue_plane_name_list(json_config, trimmed)
    for plane_name in blue_planes:
        
        if "F/A-18E/F" in plane_name:
            ret.append(plane_name)

        if len(ret) == plane_count:
            break
    return ret


area_rule_map = [
    {"dimension": "Distance", "start": "startDistance", "end": "endDistance"},
    {"dimension": "Azimuth", "start": "startAzimuth", "end": "endAzimuth"},
    {"dimension": "Speed", "start": "minSpeed", "end": "maxSpeed"},
    {"dimension": "Heading", "start": "startCourse", "end": "endCourse"},
    {"dimension": "Height", "start": "minHeight", "end": "maxHeight"},
    {"dimension": "ShortCut", "start": "minFairwayCrosscut", "end": "maxFairwayCrosscut"}
]


def build_rule_from_area(dutyarea):
    """根据json中配置的dutyarea，构建rule

    Args:
        dutyarea (dict): 存储某一个area信息的字典, {startAzimuth: 0, endAzimuth: 360, ...}

    Returns:
        dict: 对应的rule, {"and":[{"dimension": _, "range":_}, ]}
    """
    crules = []
    for mode in area_rule_map:
        dimension, start, end = mode["dimension"], mode["start"], mode["end"]
        current_rule = {
            "dimension": dimension,
            "range": [dutyarea[start], dutyarea[end]]
        }
        crules.append(current_rule)
    return {"and": crules[:]}


def set_intercept_plane_num(json_config, value):
    key_list = ["antiAirPlan", 0, "antiAirOperEffect", "interceptPlaneNum"]
    return set_json_with_keylist(json_config, key_list, value)


def get_intercept_plane_num(json_config):
    key_list = ["antiAirPlan", 0, "antiAirOperEffect", "interceptPlaneNum"]
    return get_json_with_keylist(json_config, key_list)


def set_intercept_missile_num(json_config, value):
    key_list = ["antiAirPlan", 0, "antiAirOperEffect", "interceptMissileNum"]
    return set_json_with_keylist(json_config, key_list, value)


def get_intercept_missile_num(json_config):
    key_list = ["antiAirPlan", 0, "antiAirOperEffect", "interceptMissileNum"]
    return get_json_with_keylist(json_config, key_list)


def set_lose_plane_num(json_config, value):
    key_list = ["antiAirPlan", 0, "antiAirOperEffect", "losePlaneNum"]
    return set_json_with_keylist(json_config, key_list, value)


def get_lose_plane_num(json_config):
    key_list = ["antiAirPlan", 0, "antiAirOperEffect", "losePlaneNum"]
    return get_json_with_keylist(json_config, key_list)


def set_lose_ship_num(json_config, value):
    key_list = ["antiAirPlan", 0, "antiAirOperEffect", "loseShipNum"]
    return set_json_with_keylist(json_config, key_list, value)


def get_lose_ship_num(json_config):
    key_list = ["antiAirPlan", 0, "antiAirOperEffect", "loseShipNum"]
    return get_json_with_keylist(json_config, key_list)


def set_shoot_missile_num(json_config, value):
    key_list = ["antiAirPlan", 0, "antiAirOperEffect", "shootMissileNum"]
    return set_json_with_keylist(json_config, key_list, value)


def get_shoot_missile_num(json_config):
    key_list = ["antiAirPlan", 0, "antiAirOperEffect", "shootMissileNum"]
    return get_json_with_keylist(json_config, key_list)


def set_lose_total(json_config, value):
    """ 设置综合损失 """
    key_list = ["antiAirPlan", 0, "antiAirOperEffect", "loseTotal"]
    return set_json_with_keylist(json_config, key_list, value)


def get_lose_total(json_config):
    """ 获取综合损失 """
    key_list = ["antiAirPlan", 0, "antiAirOperEffect", "loseTotal"]
    return get_json_with_keylist(json_config, key_list)


def get_branchs(json_config):
    return json_config["antiAirPlan"][0]["branchs"]["content"]


def get_branch_answer_dict(json_config):
    """
    获取json文件内的分支点以及对应解决办法的list

    return [
        ['trigger1',[answer1,answer2]],
        ['trigger2',[answer3,answer4]]
    ]
    """
    _json_config_branch = get_branchs(json_config)
    result_dict = dict()
    t = 0
    trigger_num = 1
    for k, v in _json_config_branch.items():
        if k == 'branch_2':
            continue
        answer_list = ['answer' + str(i + t) for i in range(1, len(v.get('answers').get('content')) + 1)]
        t += len(answer_list)
        result_dict['trigger' + str(trigger_num)] = answer_list
        trigger_num += 1
    return result_dict


def get_triger_content(json_config, triger_name):
    """
        根据分支查找对应的分支点实体名称（105、35、KE-600_001）
    """
    branch_data = get_branchs(json_config)
    for cur_branch in branch_data.values():
        if triger_name == cur_branch['triger']['name']:
            return cur_branch['triger']['content']
    return None


def get_answer_content(json_config, triger_name, trimmed=False):
    branch_data = get_branchs(json_config)
    if trimmed:
        branch_data = naive(branch_data)
    for cur_branch in branch_data.values():
        if triger_name == cur_branch["triger"]["name"]:
            return cur_branch["answers"]["content"]
    return None


def get_branch_setting(json_config):
    branch_data = naive(get_branchs(json_config))
    branch_dict = dict()
    for k, v in branch_data.items():
        if v.get('triger') != None:
            answers_dict = {'triger': True, 'answer': 0, 'name': v.get('triger').get('name')}
            branch_dict[k] = answers_dict
        else:
            raise ValueError('当前分支没有triger')
    return branch_dict


def get_branch_answer(json_config, branch_name, answer_name):
    
    answers = json_config["antiAirPlan"][0]["branchs"]["content"][branch_name]["answers"]["content"]
    for answer in answers:
        if answer["name"] == answer_name:
            return answer


def get_branchs_effects(json_config):
    key_list = ["antiAirPlan", 0, "branchs", "effect"]
    return get_json_with_keylist(json_config, key_list)


def get_patrol_area(yhgk_json_dct, air_wait_patrol=None):
    if air_wait_patrol is None:
        patrol_area_list = yhgk_json_dct['antiAirPlan'][0]['antiAirScheme']['airWaitPatrol']  
    else:
        patrol_area_list = air_wait_patrol
    res = []
    for patrol_area in patrol_area_list:
        dic = {}
        plane_list = []
        for plane_dic in patrol_area['patrolForce']:
            plane_name = get_plane_name(yhgk_json_dct, plane_dic['forceId'])
            plane_list.append(plane_name)
        temp_points = []
        for point_dic in patrol_area['areaData']:
            points = [point_dic['longitude'], point_dic['latitude']]
            temp_points.append(points)
        lons, lats = zip(*temp_points)
        center_point_lonlat_x = np.mean(lons)
        center_point_lonlat_y = np.mean(lats)
        
        center_point_lonlat = [center_point_lonlat_x, center_point_lonlat_y]
        
        dic['plane_list'] = plane_list
        
        dic['center_point_lonlat'] = center_point_lonlat
        
        entry_time, out_time = get_json_value(patrol_area, "entryTime"), get_json_value(patrol_area, "outTime")
        
        if entry_time and out_time:
            patrol_time = int(out_time) - int(entry_time)
        else:
            patrol_time = 7000
        dic['patrol_time'] = patrol_time
        res.append(dic)
    return res


def get_json_value(json_dict, key, trimmed=True):
    return json_dict[key] if trimmed else json_dict[key]["value"]


def is_enemy(platform_info: dict) -> bool:
    """
        根据平台信息的敌我属性判断是否是敌方数据
    Args:
        platform_info: 平台信息
    Returns:
        判断结果：是敌方返回True，是我方返回False
    """
    return ENEMY_PROPERTY_E in platform_info["enemyProperty"]


def is_mine(platform_info: dict) -> bool:
    """
        根据平台信息的敌我属性判断是否是我方数据
    Args:
        platform_info: 平台信息
    Returns:
        判断结果：是我方返回True，是敌方返回False
    """
    return ENEMY_PROPERTY_M in platform_info["enemyProperty"]


def get_nested_dict(dct, nested_key, v1=0, local=False):
    """
        根据嵌套键值从字典中获取数据
    Args:
        dct: 字典数据
        nested_key: 键值列表，例如：taskData.operUnit.warship.[shipGlobalId=].platformAttach
        v1: 查找的value值
        local: 是否在原字典上直接修改
    Returns:
        字典数据
    """
    if not local:
        tmp_dict = deepcopy(dct)
    else:
        tmp_dict = dct
    keys = nested_key.split(".")
    tmp = tmp_dict
    assert "[" not in keys[-1], "最后一个标识必须为字典的一个键"
    for key in keys[:-1]:
        if "[" not in key:
            assert isinstance(tmp, dict)
            if key not in tmp:
                raise RuntimeError("字典中未找到对应的键")
            tmp = tmp[key]
        elif "=" not in key:
            
            idx = int(key[1:-1])
            assert isinstance(tmp, list)
            if idx < 0 or idx > (len(tmp) - 1):
                raise RuntimeError("下标超过列表的长度")
            tmp = tmp[idx]
        else:
            
            _key, _value = key[1:-1].split("=")
            if _value == "":  
                _value = v1
            else:
                _value = eval(_value)  
                
            assert isinstance(tmp, list)
            res = None
            for _tmp in tmp:
                if (_key in _tmp) and _tmp[_key] == _value:
                    res = _tmp
                    break
            if res is not None:
                tmp = res
            else:
                raise RuntimeError("列表中未找到对应的键和值")
                
    return tmp[keys[-1]]


if __name__ == '__main__':
    json_path = "./scheme_file/YHGK20230315_DK.json"
    out_path = "./testout.json"
    json_config = load_yhgk_json(json_path, trim=True)
    
    red_ship_id = "26fe3e2f-bd1b-411a-8163-4d1154177128"
    red_plane_id = "KE600_001"
    blue_ship_id = "26fe3e2f-bd1b-411a-8163-4d1154177138"
    blue_plane_id = "F/A-18E/F_001"
    
    red_ship = get_war_ship(json_config, red_ship_id)
    print(red_ship)

    key_list = ["taskData", "operUnit", "warship", 0, "course"]
    warships = get_json_with_keylist(json_config, key_list)
    print(warships)

    anti_targets = [
        {
            "attackTargetId": {
                "name": "打击目标ID",
                "value": "26fe3e2f-bd1b-411a-8163-4d1154177138"
            }
        },
        {
            "attackTargetId": {
                "name": "打击目标ID",
                "value": "26fe3e2f-bd1b-411a-8163-4d1154177139"
            }
        },
        {
            "attackTargetId": {
                "name": "打击目标ID",
                "value": "26fe3e2f-bd1b-411a-8163-4d1154177147"
            }
        }]
    print(naive(anti_targets))

    blue_battle_planes = get_blue_battle_planes(json_config, trimmed=True)
    print(blue_battle_planes)
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    

    
    
    
    
    
    
    

    
    
    
    
    
    
    
    
