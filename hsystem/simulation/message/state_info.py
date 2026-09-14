import dataclasses
from typing import Sequence, Dict, List


# 上报的武器状态信息记录结构体
@dataclasses.dataclass
class EmitterStateInfo:
    p_name: str
    c_name: str
    model: str
    emit_time: float # 在cal_time时计算的发射时间
    cal_time: float
    modify_time: float # 复现发射时间的计算修正量，具体含义见emitter.py中的_send_emitter_info函数注释
    interval: float
    m_model_remain: Dict[str, int]

@dataclasses.dataclass
class GuiderStateInfo:
    p_name: str
    c_name: str
    model: str
    remain: int
    is_on: bool

@dataclasses.dataclass
class SAWeaponSystemStateInfo:
    p_name: str
    c_name: str
    model: str
    is_guided: bool
    is_on: bool
    munition: str
    fire_num: int
    decision_delay: int
    guider_models: Sequence[str]
    guider_names: Sequence[str]
    emitter_models: Sequence[str]
    emitter_names: Sequence[str]
    is_crossplatform_guided: bool
    cross_platform_guide_models: List[str]
    position: List[float]
    task_area: Dict
    other_task_areas: List[Dict]

@dataclasses.dataclass
class PlatformAirDevicesStateInfo:
    send_p_name: str # 向上级上报该平台信息的平台名字，和该平台可能不是同一平台
    p_name: str
    weaponsystems: Dict[str, SAWeaponSystemStateInfo]
    emitters: Dict[str, EmitterStateInfo]
    guiders: Dict[str, GuiderStateInfo]

class PlatformsInfo(object):
    def __init__(self):
        self.ps_info = {} # {p_name: PlatformAirDevicesStateInfo}

    def get_p_info(self, p_name):
        return self.ps_info.get(p_name, None)

    def get_ws_info(self, p_name, c_name):
        p_info = self.get_p_info(p_name)
        if p_info is None:
            return None
        return p_info.weaponsystems.get(c_name, None)

    def get_emitter_info(self, p_name, c_name):
        p_info = self.get_p_info(p_name)
        if p_info is None:
            return None
        return p_info.emitters.get(c_name, None)

    def get_guider_info(self, p_name, c_name):
        p_info = self.get_p_info(p_name)
        if p_info is None:
            return None
        return p_info.guiders.get(c_name, None)

    def get_guiders_info_by_model(self, model, exclude=None):
        gs_info = []
        if exclude is None:
            ps = self.ps_info.values()
        else:
            # 排除的平台名字列表
            assert isinstance(exclude, list)
            ps = [p_info for p_name, p_info in self.ps_info.items() if p_name not in exclude]
        for p_info in ps:
            for _, g_info in p_info.guiders.items():
                if g_info.model == model:
                    gs_info.append(g_info)
        return gs_info

    def update_state_info(self, state_info, send_p_name):
        p_name = state_info.p_name
        c_name = state_info.c_name
        if p_name not in self.ps_info:
            self.ps_info[p_name] = PlatformAirDevicesStateInfo(send_p_name=send_p_name, p_name=p_name, 
                    weaponsystems={}, emitters={}, guiders={})

        cls_name = state_info.__class__.__name__
        if cls_name == "SAWeaponSystemStateInfo":
            self.ps_info[p_name].weaponsystems[c_name] = state_info
        elif cls_name == "EmitterStateInfo":
            self.ps_info[p_name].emitters[c_name] = state_info
        elif cls_name == "GuiderStateInfo":
            self.ps_info[p_name].guiders[c_name] = state_info
        else:
            raise RuntimeError("未知类型")


        