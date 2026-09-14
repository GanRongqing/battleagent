import time
import numpy as np
from enum import Enum
import collections
from matplotlib.path import Path
from dataclasses import dataclass

from .. import algorithm as alg
from simulation.core import entity, CLASS


def color2rgb(color, alpha):
    if color == "red":
        rgb = [255, 0, 0]
    elif color == "blue":
        rgb = [0, 0, 255]
    else:
        rgb = [255, 255, 0]
    out = rgb + [int(255*alpha)]
    return out


@dataclass
class SpecialEffectData:
    name: str
    class_: str
    isactive: bool = True
    hidden: bool = False
    render_event: dict = None # 向庚图推送的最新的事件

class SpecialEffect(entity.Router):
    """ 特效基类 """
    @classmethod
    def gen(cls, engine, name):
        """ 子类必须使用该函数，因为有锁 """
        # assert name not in engine.render_data
        if name in engine.render_data:
            # 生成的名字不应该存在
            import pdb; pdb.set_trace()
        if cls.__name__ not in CLASS:
            CLASS[cls.__name__] = cls
        engine.lock.acquire()
        engine.render_data[name] = eval(cls.__name__+"Data")(name=name, class_=cls.__name__)
        engine.lock.release()
        return engine.render_data[name]

    @classmethod
    def kill(cls, engine, name):
        """ 子类必须使用该函数，因为有锁 """
        data = engine.render_data[name]
        data.isactive = False
        engine.lock.acquire()
        engine.render_data.pop(name)
        engine.lock.release()
        return data 

    @classmethod
    def update(cls, engine, name, *args, **kwargs):
        data = engine.render_data[name]
        for k, v in kwargs.items():
            setattr(data, k, v)
            
    @classmethod
    def _draw(cls, engine, name, ax=None, mode="draw"):
        return []

    @classmethod
    def draw(cls, engine, name, ax):
        if name not in engine.render_data or (not engine.render_data[name].isactive):
            return
        cls._draw(engine, name, ax, mode="draw")

    @classmethod
    def drawSymbol(cls, engine, name):
        if name not in engine.render_data or (not engine.render_data[name].isactive):
            return []
        return cls._draw(engine, name, ax=None, mode="symbol")


@dataclass
class EntityEffectData(SpecialEffectData): # unit的军标符号
    entity: str = "" # unit的名字
    entity_id: str = ""
    push_time: float = 0
    title: str = "" # 平台在地图上显示的名字

class EntityEffect(SpecialEffect):
    @classmethod
    def gen(cls, engine, entity): # entity和name是同一个名字
        if entity in engine.render_data:
            # 如果已经存在，不重复生成
            return
        data = super().gen(engine, entity) # entity和name是同一个名字
        data.entity = entity
        
        unit = engine.unit_by_name(entity)
        if isinstance(unit, (CLASS["Munition"], CLASS["ChildPlatform"])) or unit.symbol_id == 33:
            title = ''
        else:
            title = entity
        data.title = title
        engine.render_index += 1
        data.entity_id = entity + "_index_" + str(engine.render_index)
        data.push_time = time.time()
        if engine.is_redis_used or engine.is_redis_log:
            base = engine.get_unit_base(unit) # 如果unit是附属平台，则找到其母平台
            lng, lat = engine.xy2lnglat(base.coords[0], base.coords[1])
            h = base.coords[2]
            event = {'time': time.time(), 'target_type': 'entity', "event_type":"create",
                    'event_property':{"id": data.entity_id, "time": engine.ymdhms,
                    "name": title, "symbol": unit.symbol_id, "group": unit.group,
                    "location":[lng, lat, h], "head":base.course, "pitch":0, "roll":0, "speed": base.speed, "title": title,
                    "rock_angle":0, "rock_cycle":0}}
            engine.push_render_event(event)
            data.render_event = event

    @classmethod
    def update(cls, engine, entity):
        data = engine.render_data[entity]
        unit = engine.unit_by_name(entity)
        # assert not unit.is_at_home # 更新的平台一定不是附属平台
        if engine.is_redis_used or engine.is_redis_log:
            is_push_flag = False
            interval = (time.time() - data.push_time)
            if interval >= engine.render_config["redis_move_update_interval"]:
                is_push_flag = True
            elif unit.motor.mode in ["turn", "Turn", "Hover"] and interval >= engine.render_config["redis_turn_update_interval"]:
                is_push_flag = True
            if is_push_flag:
                lng, lat = engine.xy2lnglat(unit.coords[0], unit.coords[1])
                h = unit.coords[2]
                event = data.render_event
                event["event_property"].update({"time": engine.ymdhms, "location":[lng, lat, h], "head":unit.course, "speed": unit.speed})
                event.update({'time': time.time(), "event_type":"update"})
                engine.push_render_event(event)
                data.push_time = time.time()
                data.render_event = event
                # import pdb; pdb.set_trace()

    @classmethod
    def _draw(cls, engine, name, ax=None, mode="draw"):
        data = engine.render_data[name]
        if data.hidden: # 隐藏则不显示
            return []
        if mode == "draw":
            pass # 该模式下的军标绘制由各个对象的draw函数实现
        else:
            u = engine.unit_by_name(name) # name和entity是一个名字
            if isinstance(u, CLASS["Plane"]):
                pos_type = 'air'
            elif isinstance(u, CLASS["Ship"]):
                pos_type = 'surface'
            else:
                pos_type = 'land'
            #print(f"名称：{name}，类型：{u.ptype}，国家：{u.country}")
            # symbol = alg.shape.Symbol(mode="Flag", type_=u.__class__.__name__, group=u.group, name=u.name, text=data.title, # name作为目标的唯一标识要传递，text作为显示的标签，可以为空
            symbol = alg.shape.Symbol(mode="Flag", type_=u.__class__.__name__, group=u.group, name=data.title,
                x=u.coords[0],y=u.coords[1],z=u.coords[2],az=u.course, symbol_id=u.symbol_id, speed=u.speed, pos_type=pos_type,
                model=u.ptype, country=u.country, batch_no=data.name, pmodel=u.model, pitch=u.pitch)
            return [symbol]

    @classmethod
    def hide(cls, engine, entity): 
        data = engine.render_data[entity]
        if data.hidden: # 已经是隐藏状态，则忽略
            return
        data.hidden = True
        if engine.is_redis_used or engine.is_redis_log:
            event = data.render_event
            event["event_property"].update({"time": engine.ymdhms})
            event.update({'time': time.time(), "event_type":"hide"})
            engine.push_render_event(event)
            data.push_time = time.time()
            data.render_event = event

    @classmethod
    def show(cls, engine, entity): 
        data = engine.render_data[entity]
        if not data.hidden: # 已经是显示状态，则忽略
            return
        data.hidden = False
        if engine.is_redis_used or engine.is_redis_log:
            event = data.render_event
            event["event_property"].update({"time": engine.ymdhms})
            event.update({'time': time.time(), "event_type":"show"})
            engine.push_render_event(event)
            data.push_time = time.time()
            data.render_event = event

    @classmethod
    def kill(cls, engine, entity): 
        if entity in engine.render_data: 
            # 如果不存在，则不杀死。
            # 可能先调用unit.motor.set_ref_unit导致不存在
            data = engine.render_data[entity]
            if engine.is_redis_used or engine.is_redis_log:
                event = data.render_event
                event["event_property"].update({"time": engine.ymdhms})
                event.update({'time': time.time(), "event_type":"destroy"})
                engine.push_render_event(event)
                data.push_time = time.time()
                data.render_event = event
            super().kill(engine, entity)


@dataclass
class ExplodeEffectData(SpecialEffectData):
    entity: str = ""
    blast_id: str = ""

class ExplodeEffect(SpecialEffect):
    @classmethod
    def gen(cls, engine, entity): # entity和name是同一个名字
        name = entity + "_explode_" + str(engine.tick) 
        while name in engine.render_data:
            name = name + "_" + str(np.random.randint(0, 1000)) # 爆炸有可能容易出现重名， 因此改名
        data = super().gen(engine, name)
        data.entity = entity

        engine.render_index += 1
        data.blast_id = name + "_index_" + str(engine.render_index)
        if entity in engine.render_data:
            entity_id = engine.render_data[entity].entity_id
            if engine.is_redis_used or engine.is_redis_log:
                event = {'time': time.time(), 'target_type': 'blast', "event_type": "create",
                        'event_property': {"blast_id": data.blast_id, "entity_id": entity_id,
                                            "count" : 1, "time": engine.ymdhms}}
                engine.push_render_event(event)
                data.render_event = event
            engine.next_render_fun(name, "kill", delay=engine.render_config["explode_duration"]*engine.ratio)


@dataclass
class HighlightEffectData(SpecialEffectData):
    entity: str = ""
    highlight_id: str = ""
    highlight_vertices: np.dtype = np.array([0.0, 0.0, 0.0])

class HighlightEffect(SpecialEffect):
    @classmethod
    def gen(cls, engine, entity): # entity和name是同一个名字
        name = entity + "_highlight_" + str(engine.tick) 
        while name in engine.render_data:
            name = name + "_" + str(np.random.randint(0, 1000)) # 高亮容易出现重名， 因此改名
        data = super().gen(engine, name)
        data.entity = entity
        engine.render_index += 1
        data.highlight_id = name + "_index_" + str(engine.render_index)
        entity_id = engine.render_data[entity].entity_id
        data.highlight_vertices = 10*np.array([[-0.5, 0.5], [0.5, 0.5], [0.5, -0.5], [-0.5, -0.5],[-0.5, 0.5]])

        if engine.is_redis_used or engine.is_redis_log:
            event = {'time': time.time(), 'target_type': 'highlight', "event_type": "create",
                     'event_property': {"highlight_id": data.highlight_id, "entity_id": entity_id,
                                        "count" : 1, "time": engine.ymdhms}}
            engine.push_render_event(event)
            data.render_event = event
        engine.next_render_fun(name, "kill", delay=engine.render_config["highlight_duration"]*engine.ratio)

    @classmethod
    def _draw(cls, engine, name, ax=None, mode="draw"):
        if mode == "draw":
            data = engine.render_data[name]
            u = engine.unit_by_name(data.entity)
            ax.scatter(u.coords[0], u.coords[1], marker=Path(data.highlight_vertices), c="purple", s=200, alpha=0.1)
        else:
            return []

@dataclass 
class ActionEffectData(SpecialEffectData):
    entity: str = ''
    action_id: str = ''

class ActionEffect(SpecialEffect):
    '''
    针对特定动作的特效, 当前用于三维显示
    '''
    @classmethod
    def gen(cls, engine, entity, action_name, **kwargs): # entity和name是同一个名字
        name = entity + f"_action-{action_name}_" + str(engine.tick) 
        while name in engine.render_data:
            name = name + "_" + str(np.random.randint(0, 1000)) # 爆炸有可能容易出现重名， 因此改名
        data = super().gen(engine, name)
        data.entity = entity

        engine.render_index += 1
        data.action_id = name + "_index_" + str(engine.render_index)
        entity_id = engine.render_data[entity].entity_id
        if engine.is_redis_used or engine.is_redis_log:
            event = {'time': time.time(), 'target_type': 'entity', "event_type": "action",
                     'event_property': {"id": data.action_id, "entity_id": entity_id,
                                        "action_name": action_name, "time": engine.ymdhms}}
            for k, v in kwargs.items():
                event['event_property'][k] = v
            engine.push_render_event(event)
            data.render_event = event
        engine.next_render_fun(name, "kill", delay=1)# kill 函数不会控制显示, 只是为了和其他特效保持一致

@dataclass 
class OpenHatchActionEffectData(ActionEffectData):
    pass

class OpenHatchActionEffect(ActionEffect):
    '''
    跨域无人艇弹舱开盖动作
    '''
    @classmethod
    def gen(cls, engine, entity, emitter_name): 
        super().gen(engine, entity, 'openhatch', emitter_name=emitter_name)

@dataclass 
class CloseHatchActionEffectData(ActionEffectData):
    pass

class CloseHatchActionEffect(ActionEffect):
    '''
    跨域无人艇弹舱关盖动作
    '''
    @classmethod
    def gen(cls, engine, entity, emitter_name): 
        super().gen(engine, entity, 'closehatch', emitter_name=emitter_name)

@dataclass 
class FireMissileActionEffectData(ActionEffectData):
    pass

class FireMissileActionEffect(ActionEffect):
    '''
    跨域无人艇弹舱发弹动作
    '''
    @classmethod
    def gen(cls, engine, entity, emitter_name, missile_name): 
        missile_id = engine.render_data[missile_name].entity_id
        super().gen(engine, entity, 'firemissile', emitter_name=emitter_name, missile_name=missile_id)


@dataclass 
class SubmarineRiseStartActionEffectData(ActionEffectData):
    pass

class SubmarineRiseStartActionEffect(ActionEffect):
    '''
    跨域无人艇上浮开始动作
    '''
    @classmethod
    def gen(cls, engine, entity): 
        super().gen(engine, entity, 'submarine-rise-start')


@dataclass 
class SubmarineRiseEndActionEffectData(ActionEffectData):
    pass

class SubmarineRiseEndActionEffect(ActionEffect):
    '''
    跨域无人艇上浮结束动作
    '''
    @classmethod
    def gen(cls, engine, entity): 
        super().gen(engine, entity, 'submarine-rise-end')

@dataclass 
class SubmarineDiveStartActionEffectData(ActionEffectData):
    pass

class SubmarineDiveStartActionEffect(ActionEffect):
    '''
    跨域无人艇下潜开始动作
    '''
    @classmethod
    def gen(cls, engine, entity): 
        super().gen(engine, entity, 'submarine-dive-start')


@dataclass 
class SubmarineDiveEndActionEffectData(ActionEffectData):
    pass

class SubmarineDiveEndActionEffect(ActionEffect):
    '''
    跨域无人艇下潜结束动作
    '''
    @classmethod
    def gen(cls, engine, entity): 
        super().gen(engine, entity, 'submarine-dive-end')


@dataclass
class SonicWaveEffectData(SpecialEffectData):
    tick: int = 0
    coords: np.dtype = np.array([0.0, 0.0, 0.0])
    is_echo: bool = False
    duration: float = 0
    az1: float = 0
    az2: float = 0
    pitch1: float = 0
    pitch2: float = 0
    transperancy: float = 0
    alpha: float = 0
    dst: str = ""
    is_wave_created: bool = False
    entity_id: str = ""
    wave_id: str = ""
    render_entity_event: dict = None

class SonicWaveEffect(SpecialEffect):
    @classmethod
    def gen(cls, engine, src:str, duration:float, angle1:float=0, angle2:float=0, dst:str=""):
        name = src + "_wave_" + dst + str(engine.tick) 
        while name in engine.render_data:
            name = name + "_" + str(np.random.randint(0, 1000)) # 声波容易出现重名， 因此改名
        data = super().gen(engine, name)
        data.tick = engine.tick
        data.coords = engine.unit_by_name(src).coords.copy()
        data.is_echo = False # 是否是回波
        data.duration =duration

        if dst is None or dst == "":
            # 声波
            data.is_echo = False
            data.az1 = angle1
            data.az2 = angle2
            data.pitch1 = -90
            data.pitch2 = 90
            data.transperancy = 50
            data.alpha = 0.3
            data.dst = ""
        else:
            # 回波
            data.is_echo = True
            data.dst = dst
            dst_coords = engine.unit_by_name(dst).coords
            azimuth = alg.geometry.azimuth(data.coords, dst_coords)
            pitch = alg.geometry.pitch(data.coords, dst_coords)
            data.az1 = azimuth - 5
            data.az2 = azimuth + 5
            data.pitch1 = pitch - 5
            data.pitch2 = pitch + 5
            data.transperancy = 255
            data.alpha = 0.7

        data.is_wave_created = False
        engine.render_index += 1
        data.entity_id = name + '_entity_' + str(engine.render_index)
        data.wave_id = name + '_wave_' + str(engine.render_index)
        
        if engine.is_redis_used or engine.is_redis_log:
            lng, lat = engine.xy2lnglat(data.coords[0], data.coords[1])
            event = {'time': time.time(), 'target_type': 'entity', "event_type":"create",
                    'event_property':{"id": data.entity_id, "time": engine.ymdhms,
                    "name": data.entity_id, "symbol": 33, "group": '',
                    "location": [lng, lat, data.coords[2]], "head":0, "pitch":0, "roll":0, "speed": 0}}
            engine.push_render_event(event)
            data.render_entity_event = event
            data.push_time = time.time()
            engine.next_render_fun(name, "push_render_event", delay=0.05*engine.ratio) # 每个0.05s（现实时间）推一次

        if data.is_echo:
            # 回波
            engine.next_render_fun(name, "kill", delay=duration)
        else:
            # 声波
            engine.next_render_fun(name, "kill", delay=2*duration)

    @classmethod
    def kill(cls, engine, name): 
        data = super().kill(engine, name)
        if engine.is_redis_used or engine.is_redis_log:
            event = data.render_entity_event
            event["event_property"].update({"time": engine.ymdhms})
            event.update({'time': time.time(), "event_type":"destroy"})
            engine.push_render_event(event)
            data.push_time = time.time()
            data.render_event = event

    @classmethod
    def push_render_event(cls, engine, name):
        data = engine.render_data[name]
        if not data.isactive:
            return
        else:
            t = (engine.tick - data.tick) / 1000.0
            if data.is_echo:
                # 回波
                r = engine.env.sonic_speed * t
            else:
                # 声波
                if t <= data.duration:
                    r = engine.env.sonic_speed * t
                else:
                    r = engine.env.sonic_speed * (2*data.duration - t)
            if r <= 0:
                return
            if not data.is_wave_created:
                flag = "create"
                data.is_wave_created = True
            else:
                flag = "update"
            event = {'time': time.time(), 'target_type': 'wave', "event_type": flag,
                    'event_property': {"wave_id": data.wave_id, "entity_id": data.entity_id,
                                        "begin_angle": data.az1%360, "sweep_angle": (data.az2-data.az1)%360, "radius": r,
                                        "elevation_high": data.pitch2, "elevation_low": data.pitch1,
                                        "color": [255, 255, 255, data.transperancy], "colorA": [255, 255, 0, data.transperancy],
                                        "colorB": [0, 0, 255, data.transperancy],
                                        "wave_length": 10000, "wave_speed": 5000, "wave_cycle": 10,
                                        "time": engine.ymdhms}}
            engine.push_render_event(event)
            data.push_time = time.time()
            data.render_event = event
            engine.next_render_fun(name, "push_render_event", delay=0.05*engine.ratio) # 每个0.05s（现实时间）推一次

    @classmethod
    def _draw(cls, engine, name, ax=None, mode="draw"):
        data = engine.render_data[name]
        items = []
        t = (engine.tick - data.tick) / 1000.0
        if data.is_echo:
            # 回波
            r = engine.env.sonic_speed * t
        else:
            # 声波
            if t <= data.duration:
                r = engine.env.sonic_speed * t
            else:
                r = engine.env.sonic_speed * (2*data.duration - t)
        if r > 0:
            sector = alg.shape.Sector(data.coords, r, data.az1, data.az2)
            if mode == "draw":
                sector.fill(ax, c="green", alpha=data.alpha)
            else:
                item = sector.fillSymbol(color="green", fill_color="green", fill_alpha=data.alpha)
                items.append(item)
        return items


@dataclass
class StaticRectangleEffectData(SpecialEffectData):
    coords: np.dtype = np.array([0.0, 0.0, 0.0])
    length: float = 0
    width: float = 0
    az: float = 0
    color: str = "red"
    alpha: float = 1.0
    fill_alpha: float = 0.0
    duration: float = -1 # 表示永远
    entity_id: str = ""
    rectangle_id: str = ""
    render_entity_event: dict = None

class StaticRectangleEffect(SpecialEffect):
    """  绘制静态矩形 """
    @classmethod
    def gen(cls, engine, name, coords, length, width, az, color="red", alpha=1.0, fill_alpha=0, duration=-1):
        data = super().gen(engine, name)
        data.coords = np.array(coords, dtype=np.float64)
        data.length = length
        data.width = width
        data.az = az # 长边的指向角
        data.color = color
        data.alpha = alpha
        data.fill_alpha = fill_alpha
        data.duration = duration
        if duration > 0:
            engine.next_render_fun(name, "kill", delay=duration)

        engine.render_index += 1
        data.entity_id = name + '_entity_' + str(engine.render_index)
        data.rectangle_id = name + '_rectangle_' + str(engine.render_index)

        if engine.is_redis_used or engine.is_redis_log:
            # 生成实体
            lng, lat = engine.xy2lnglat(data.coords[0], data.coords[1])
            event = {'time': time.time(), 'target_type': 'entity', "event_type":"create",
                    'event_property':{"id": data.entity_id, "time": engine.ymdhms,
                    "name": data.entity_id, "symbol": 33, "group": '',
                    "location": [lng, lat, data.coords[2]], "head":0, "pitch":0, "roll":0, "speed": 0}}
            engine.push_render_event(event)
            data.render_entity_event = event
            data.push_time = time.time()

            # 生成矩形
            ang = np.rad2deg(np.arctan2(length, width))
            dis = 0.5*np.sqrt(length**2+width**2)
            event = {'time': time.time(),
                    "target_type":  "range",
                    "event_type": "create",
                    "event_property": {
                            "entity_id": data.entity_id,
                            "range_id": data.rectangle_id,
                            "range_type": "polygon",
                            "angle_array": np.array([az+90-ang, az+90+ang, az+270-ang, az+270+ang])%360, 
                            "distance_array": [dis, dis, dis, dis],
                            "border_color": color2rgb(color, alpha), # 颜色0~255只能是整数
                            "fill_color": color2rgb(color, fill_alpha), # 颜色0~255只能是整数
                            "time": engine.ymdhms
                        }
                    } 
            engine.push_render_event(event)
            data.render_event = event
            data.push_time = time.time()

    @classmethod
    def _draw(cls, engine, name, ax=None, mode="draw"):
        data = engine.render_data[name]
        items = []
        x0 = data.coords[0]
        y0 = data.coords[1]
        rectangle = alg.shape.Rectangle.gen_center_rect([x0, y0], data.length, data.width, data.az)
        if mode == "draw":
            rectangle.fill(ax, c=data.color, alpha=data.fill_alpha)
        else:
            item = rectangle.fillSymbol(color=data.color, fill_color=data.color, fill_alpha=data.fill_alpha)
            items.append(item)
        return items

    @classmethod
    def kill(cls, engine, name): 
        data = super().kill(engine, name)
        if engine.is_redis_used or engine.is_redis_log:
            event = data.render_entity_event
            event["event_property"].update({"time": engine.ymdhms})
            event.update({'time': time.time(), "event_type":"destroy"})
            engine.push_render_event(event)
            data.push_time = time.time()
            data.render_event = event


@dataclass
class StaticPolygonEffectData(SpecialEffectData):
    points: np.dtype = None
    color: str = "red"
    alpha: float = 1.0
    fill_alpha: float = 0.0
    duration: float = -1 # 表示永远
    entity_id: str = ""
    polygon_id: str = ""
    render_entity_event: dict = None


class StaticPolygonEffect(SpecialEffect):
    """  绘制静态多边形 """
    @classmethod
    def gen(cls, engine, name, points, color="red", alpha=1.0, fill_alpha=0, duration=-1, coordinate_system="Cartesian"):
        data = super().gen(engine, name)
        if coordinate_system == "Cartesian":
            data.points = np.array(points, dtype=float)
        else: # 经纬度
            _points = np.array(points, dtype=float)
            x, y = engine.lnglat2xy(_points[:,0], _points[:,1])
            data.points = np.c_[x, y]
        data.center = np.mean(data.points, axis=0)
        data.color = color
        data.alpha = alpha
        data.fill_alpha = fill_alpha
        data.duration = duration
        if duration > 0:
            engine.next_render_fun(name, "kill", delay=duration)

        engine.render_index += 1
        data.entity_id = name + '_entity_' + str(engine.render_index)
        data.polygon_id = name + '_polygon_' + str(engine.render_index)

        if engine.is_redis_used or engine.is_redis_log:
            # 生成实体
            lng, lat = engine.xy2lnglat(data.center[0], data.center[1])
            event = {'time': time.time(), 'target_type': 'entity', "event_type":"create",
                    'event_property':{"id": data.entity_id, "time": engine.ymdhms,
                    "name": data.entity_id, "symbol": 33, "group": '',
                    "location": [lng, lat, 0], "head":0, "pitch":0, "roll":0, "speed": 0}}
            engine.push_render_event(event)
            data.render_entity_event = event
            data.push_time = time.time()

            # 生成多边形
            az_lst = []
            dis_lst = []
            for i in range(len(data.points)):
                az = alg.geo.azimuth(data.center, data.points[i,:])
                dis = alg.geo.distance(data.center, data.points[i,:])
                az_lst.append(az)
                dis_lst.append(dis)
            event = {'time': time.time(),
                    "target_type":  "range",
                    "event_type": "create",
                    "event_property": {
                            "entity_id": data.entity_id,
                            "range_id": data.polygon_id,
                            "range_type": "polygon",
                            "angle_array": az_lst, 
                            "distance_array": dis_lst,
                            "border_color": color2rgb(color, alpha), # 颜色0~255只能是整数
                            "fill_color": color2rgb(color, fill_alpha), # 颜色0~255只能是整数
                            "time": engine.ymdhms
                        }
                    } 
            # engine.push_render_event(event)
            data.render_event = event
            data.push_time = time.time()

    @classmethod
    def _draw(cls, engine, name, ax=None, mode="draw"):
        data = engine.render_data[name]
        items = []
        shp = alg.shape.PolygonShape(data.points)
        if mode == "draw":
            shp.fill(ax, c=data.color, alpha=data.fill_alpha)
        else:
            item = shp.fillSymbol(color=data.color, fill_color=data.color, fill_alpha=data.fill_alpha)
            items.append(item)
        return items

    @classmethod
    def kill(cls, engine, name): 
        data = super().kill(engine, name)
        if engine.is_redis_used or engine.is_redis_log:
            event = data.render_entity_event
            event["event_property"].update({"time": engine.ymdhms})
            event.update({'time': time.time(), "event_type":"destroy"})
            engine.push_render_event(event)
            data.push_time = time.time()
            data.render_event = event


@dataclass
class DynamicRectangleEffectData(SpecialEffectData):
    entity: str = ""
    length: float = 0
    width: float = 0
    az: float = 0
    color: str = "red"
    alpha: float = 1.0
    fill_alpha: float = 0.0
    rectangle_id: str = ""

class DynamicRectangleEffect(SpecialEffect):
    """ 绘制动态矩形，即与实体绑定"""
    @classmethod
    def gen(cls, engine, name, entity, length, width, az, color="red", alpha=1.0, fill_alpha=0):
        data = super().gen(engine, name)
        data.entity = entity
        data.length = length
        data.width = width
        data.az = az # 长边的指向角
        data.color = color
        data.alpha = alpha
        data.fill_alpha = fill_alpha

        engine.render_index += 1
        data.rectangle_id = name + "_rect_" + str(engine.render_index)

        if engine.is_redis_used or engine.is_redis_log:
            # 生成矩形
            ang = np.rad2deg(np.arctan2(length, width))
            dis = 0.5*np.sqrt(length**2+width**2)
            entity_id = engine.render_data[entity].entity_id
            event = {'time': time.time(),
                    "target_type":  "range",
                    "event_type": "create",
                    "event_property": {
                            "entity_id": entity_id,
                            "range_id": data.rectangle_id,
                            "range_type": "polygon",
                            "angle_array": np.array([az+90-ang, az+90+ang, az+270-ang, az+270+ang])%360, 
                            "distance_array": [dis, dis, dis, dis],
                            "border_color": color2rgb(color, alpha), # 颜色0~255只能是整数
                            "fill_color": color2rgb(color, fill_alpha), # 颜色0~255只能是整数
                            "time": engine.ymdhms
                        }
                    } 
            engine.push_render_event(event)
            data.render_event = event
            data.push_time = time.time()

    @classmethod
    def update(cls, engine, name, *args, **kwargs):
        # import pdb; pdb.set_trace()
        if name not in engine.render_data:
            # 如果未生成，则直接按生成处理
            cls.gen(engine, name, *args, **kwargs)
            return
        data = engine.render_data[name]
        for k, v in kwargs.items():
            setattr(data, k, v)
        if engine.is_redis_used or engine.is_redis_log:
            entity_id = engine.render_data[data.entity].entity_id
            ang = np.rad2deg(np.arctan2(data.length, data.width))
            dis = 0.5*np.sqrt(data.length**2+data.width**2)
            az = data.az
            event = {'time': time.time(),
                    "target_type":  "range",
                    "event_type": "update",
                    "event_property": {
                            # "entity_id": entity_id, # 如果有entity_id，则会重复创建
                            "range_id": data.rectangle_id,
                            "range_type": "polygon",
                            "angle_array": np.array([az+90-ang, az+90+ang, az+270-ang, az+270+ang])%360, 
                            "distance_array": [dis, dis, dis, dis],
                            "border_color": color2rgb(data.color, data.alpha), # 颜色0~255只能是整数
                            "fill_color": color2rgb(data.color, data.fill_alpha), # 颜色0~255只能是整数
                            "time": engine.ymdhms
                        }
                    } 
            engine.push_render_event(event)
            data.render_event = event
            data.push_time = time.time()

    @classmethod
    def _draw(cls, engine, name, ax=None, mode="draw"):
        data = engine.render_data[name]
        items = []
        u = engine.unit_by_name(data.entity)
        x0 = u.coords[0]
        y0 = u.coords[1]
        rectangle = alg.shape.Rectangle.gen_center_rect([x0, y0], data.length, data.width, data.az)
        if mode == "draw":
            rectangle.plot(ax, c=data.color, alpha=data.alpha, linewidth=1)
            if data.fill_alpha > 0:
                rectangle.fill(ax, c=data.color, alpha=data.fill_alpha)
        else:
            item = rectangle.fillSymbol(color=data.color, fill_color=data.color, fill_alpha=data.fill_alpha)
            items.append(item)
        return items

    @classmethod
    def kill(cls, engine, name):
        if name not in engine.render_data:
            return # 不存在则不杀死
        data = super().kill(engine, name)
        if engine.is_redis_used or engine.is_redis_log:
            event = data.render_event
            event["event_property"].update({"time": engine.ymdhms})
            event.update({'time': time.time(), "event_type":"destroy"})
            engine.push_render_event(event)
            data.push_time = time.time()
            data.render_event = event


@dataclass
class DynamicRangeEffectData(SpecialEffectData):
    """ 圆、扇形、圆环、扇环 """
    entity: str = ""
    r1: float = 0
    r2: float = 0
    az1: float = 0
    az2: float = 360
    color: str = "red"
    alpha: float = 1.0
    fill_alpha: float = 0.0
    range_id: str = ""
    type_: str = ""
    group: str = ""

class DynamicRangeEffect(SpecialEffect):
    """ 绘制动态圆、扇形、圆环、扇环，即与实体绑定 """
    @classmethod
    def gen(cls, engine, name, entity, r1=0, r2=0, az1=0, az2=360, color="red", alpha=1.0, fill_alpha=0, type_="", group=None):
        """ 
        说明： az1和az2是相对于正北方向的方位角，与平台朝向无关
        """
        data = super().gen(engine, name)
        data.entity = entity
        data.r1 = r1
        data.r2 = r2
        data.az1 = az1
        data.az2 = az2
        data.color = color
        data.alpha = alpha
        data.fill_alpha = fill_alpha
        data.type_ = type_ # web可视化使用
        if group is None:
            data.group = color.upper() # web可视化使用
        engine.render_index += 1
        data.range_id = name + "_range_" + str(engine.render_index)

        if engine.is_redis_used or engine.is_redis_log:
            # 生成圆、扇形、圆环、扇环
            entity_id = engine.render_data[entity].entity_id
            sweep_angle = (az2-az1)%360 # 如果为360时，会变为0
            sweep_angle = 360 if sweep_angle <= 0 else sweep_angle
            event = {'time': time.time(), 'target_type': 'range', "event_type": "create",
                                    'event_property': {"range_type": "sector", "range_id": data.range_id, "entity_id": entity_id,
                                                    "radius": r2, "begin_angle": az1%360, "sweep_angle": sweep_angle,
                                                    "border_color": color2rgb(color, alpha), # 颜色0~255只能是整数
                                                    "inner_radius": r1, 
                                                    "fill_color": color2rgb(color, fill_alpha), # 颜色0~255只能是整数
                                                    "time": engine.ymdhms}}
            engine.push_render_event(event)
            data.render_event = event
            data.push_time = time.time()

            # 判断是否要更新合并项
            merge_name = None
            if engine.render_config["radar_envelope"]:
                merge_name = data.group+"_"+"Radar"
            elif engine.render_config["attack_range_envelope"]:
                merge_name = data.group+"_"+"AttackRange"
            if merge_name is not None:
                if merge_name not in engine.render_data:
                    merge_lst = [data.range_id]
                    EnvelopEffect.gen(engine, merge_name, merge_lst=merge_lst)
                else:
                    merge_data = engine.render_data[merge_name]
                    x = set(merge_data.merge_lst)
                    x.update([data.range_id])
                    EnvelopEffect.update(engine, merge_name, merge_lst=list(x))
            
    @classmethod
    def update(cls, engine, name, *args, **kwargs):
        if name not in engine.render_data:
            # 如果未生成，则直接按生成处理
            cls.gen(engine, name, *args, **kwargs)
            return
        data = engine.render_data[name]
        for k, v in kwargs.items():
            setattr(data, k, v)
        if engine.is_redis_used or engine.is_redis_log:
            entity_id = engine.render_data[data.entity].entity_id
            sweep_angle = (data.az2-data.az1)%360 # 如果未360时，会变为0
            sweep_angle = 360 if sweep_angle <= 0 else sweep_angle
            event = {'time': time.time(), 'target_type': 'range', "event_type": "update",
                                    'event_property': {"range_type": "sector", "range_id": data.range_id, 
                                                    "entity_id": entity_id,
                                                    "radius": data.r2, "begin_angle": data.az1%360, "sweep_angle": sweep_angle,
                                                    "border_color": color2rgb(data.color, data.alpha), # 颜色0~255只能是整数
                                                    "inner_radius": data.r1, 
                                                    "fill_color": color2rgb(data.color, data.fill_alpha), # 颜色0~255只能是整数
                                                    "time": engine.ymdhms}}
            engine.push_render_event(event)
            data.render_event = event
            data.push_time = time.time()

    @classmethod
    def _draw(cls, engine, name, ax=None, mode="draw"):
        data = engine.render_data[name]
        items = []
        u = engine.unit_by_name(data.entity)
        x0 = u.coords[0]
        y0 = u.coords[1]
        if data.r1 <= 0:
            if data.az1 == 0 and data.az2 == 360:
                shp = alg.shape.Circle([x0, y0], data.r2)
            else:
                az1 = data.az1
                az2 = data.az2
                shp = alg.shape.Sector([x0, y0], data.r2, az1, az2)
        else:
            if data.az1 == 0 and data.az2 == 360:
                shp = alg.shape.CircleRing([x0, y0], data.r1, data.r2)
            else:
                az1 = data.az1
                az2 = data.az2
                shp = alg.shape.SectorRing([x0, y0], data.r1, data.r2, az1, az2)
        if mode == "draw":
            shp.plot(ax, c=data.color, alpha=data.alpha, linewidth=1)
            if data.fill_alpha > 0:
                shp.fill(ax, c=data.color, alpha=data.fill_alpha)
        else:
            item = shp.fillSymbol(type_=data.type_, group=data.group, color=data.color, fill_color=data.color,
                                  fill_alpha=data.fill_alpha, batch_no=data.range_id, r1=data.r1, r2=data.r2,
                                  az1=data.az1, az2=data.az2, platform=data.entity, class_=data.class_)
            items.append(item)
        return items

    @classmethod
    def kill(cls, engine, name): 
        if name not in engine.render_data:
            return # 不存在则不杀死
        data = super().kill(engine, name)
        if engine.is_redis_used or engine.is_redis_log:
            event = data.render_event
            event["event_property"].update({"time": engine.ymdhms})
            event.update({'time': time.time(), "event_type":"destroy"})
            engine.push_render_event(event)
            data.push_time = time.time()
            data.render_event = event

            # 判断是否要更新合并项
            merge_name = None
            if engine.render_config["radar_envelope"]:
                merge_name = data.group+"_"+"Radar"
            elif engine.render_config["attack_range_envelope"]:
                merge_name = data.group+"_"+"AttackRange"
            if merge_name is not None:
                if merge_name not in engine.render_data:
                    pass
                else:
                    merge_data = engine.render_data[merge_name]
                    x = set(merge_data.merge_lst)
                    x.remove(data.range_id)
                    if x:
                        EnvelopEffect.update(engine, merge_name, merge_lst=list(x))
                    else:
                        EnvelopEffect.kill(engine, merge_name)


@dataclass
class DynamicPolygonEffectData(SpecialEffectData):
    """ 动态多边形 """
    entity: str = ""
    az_array: np.dtype = None
    dis_array: np.dtype = None
    color: str = "red"
    alpha: float = 1.0
    fill_alpha: float = 0.0
    range_id: str = ""
    type_: str = ""
    group: str = ""

class DynamicPolygonEffect(SpecialEffect):
    """ 绘制动态多边形，即与实体绑定 """
    @classmethod
    def gen(cls, engine, name, entity, az_array=None, dis_array=None, color="red", alpha=1.0, fill_alpha=0, type_="", group=None):
        """ 
        说明： az_array是相对于正北方向的方位角列表，与平台朝向无关
        """
        data = super().gen(engine, name)
        data.entity = entity
        data.az_array = np.array(az_array, dtype=np.float64)
        data.dis_array = np.array(dis_array, dtype=np.float64)
        data.color = color
        data.alpha = alpha
        data.fill_alpha = fill_alpha
        data.type_ = type_ # web可视化使用
        if group is None:
            data.group = color.upper() # web可视化使用
        engine.render_index += 1
        data.polygon_id = name + "_polygon_" + str(engine.render_index)

        if engine.is_redis_used or engine.is_redis_log:
            # 生成动态多边形
            entity_id = engine.render_data[entity].entity_id
            event = {
                    'time': time.time(), 
                    'target_type': 'range', 
                    "event_type": "create",
                    'event_property': {
                        "range_type": "polygon", 
                        "range_id": data.polygon_id, 
                        "entity_id": entity_id,
                        "angle_array": data.az_array%360, 
                        "distance_array": data.dis_array,
                        "border_color": color2rgb(color, alpha), # 颜色0~255只能是整数
                        "fill_color": color2rgb(color, fill_alpha), # 颜色0~255只能是整数
                        "time": engine.ymdhms
                        }
                    }
            engine.push_render_event(event)
            data.render_event = event
            data.push_time = time.time()

    @classmethod
    def update(cls, engine, name, *args, **kwargs):
        if name not in engine.render_data:
            # 如果未生成，则直接按生成处理
            cls.gen(engine, name, *args, **kwargs)
            return
        data = engine.render_data[name]
        for k, v in kwargs.items():
            setattr(data, k, v)
        if engine.is_redis_used or engine.is_redis_log:
            entity_id = engine.render_data[data.entity].entity_id
            event = {'time': time.time(),
                    "target_type":  "range",
                    "event_type": "update",
                    "event_property": {
                            # "entity_id": entity_id, # 如果有entity_id，则会重复创建
                            "range_id": data.polygon_id,
                            "range_type": "polygon",
                            "angle_array": np.array(data.az_array, dtype=np.float64)%360, 
                            "distance_array": data.dis_array,
                            "border_color": color2rgb(data.color, data.alpha), # 颜色0~255只能是整数
                            "fill_color": color2rgb(data.color, data.fill_alpha), # 颜色0~255只能是整数
                            "time": engine.ymdhms
                        }
                    } 
            engine.push_render_event(event)
            data.render_event = event
            data.push_time = time.time()

    @classmethod
    def _draw(cls, engine, name, ax=None, mode="draw"):
        data = engine.render_data[name]
        items = []
        u = engine.unit_by_name(data.entity)
        x0 = u.coords[0]
        y0 = u.coords[1]
        x = data.dis_array * np.sin(np.deg2rad(data.az_array)) + x0
        y = data.dis_array * np.cos(np.deg2rad(data.az_array)) + y0

        if mode == "draw":
            ax.plot(x, y, c=data.color, alpha=data.alpha, linewidth=1)
            if data.fill_alpha > 0:
                ax.fill(x, y, c=data.color, alpha=data.fill_alpha)
        else:
            item = alg.shape.Symbol(mode="Polygon", x=x.tolist(), y=y.tolist(), type_=data.type_, group=data.group, color=data.color, fill_color=data.color, fill_alpha=data.fill_alpha)
            items.append(item)
        return items

    @classmethod
    def kill(cls, engine, name):
        if name not in engine.render_data:
            return # 不存在则不杀死
        data = super().kill(engine, name)
        if engine.is_redis_used or engine.is_redis_log:
            event = data.render_event
            event["event_property"].update({"time": engine.ymdhms})
            event.update({'time': time.time(), "event_type":"destroy"})
            engine.push_render_event(event)
            data.push_time = time.time()
            data.render_event = event


def dynamic_shape_kill(engine, name):
    """ 对矩形、圆、环、多边形等动态图形的统一清除接口 """
    if name not in engine.render_data:
        return # 不存在则不杀死
    data = engine.render_data[name]
    data.isactive = False
    engine.lock.acquire()
    engine.render_data.pop(name)
    engine.lock.release()
    if engine.is_redis_used or engine.is_redis_log:
        event = data.render_event
        event["event_property"].update({"time": engine.ymdhms})
        event.update({'time': time.time(), "event_type":"destroy"})
        engine.push_render_event(event)
        data.push_time = time.time()
        data.render_event = event


@dataclass
class EnvelopEffectData(SpecialEffectData):
    """ 图形合并 """
    merge_lst: list = None # 需要合并的id列表
    merge_id: str = ""


class EnvelopEffect(SpecialEffect):
    @classmethod
    def gen(cls, engine, name, merge_lst):
        assert name in ["RED_Radar", "BLUE_Radar", "RED_AttackRange", "BLUE_AttackRange"]
        data = super().gen(engine, name)
        data.merge_lst = merge_lst
        engine.render_index += 1
        data.merge_id = name + "_merge_" + str(engine.render_index)

        if engine.is_redis_used or engine.is_redis_log:
            event =  {
            "target_type" :  "range_merge",
            "event_type" : "create",
            "event_property" : {
                    "range_merge_id" : data.merge_id,
                    "range_id_array" : data.merge_lst
                }
            }
            engine.push_render_event(event)
            data.render_event = event
            data.push_time = time.time()

    @classmethod
    def update(cls, engine, name, *args, **kwargs):
        # if name not in engine.render_data:
        #     # 如果未生成，则直接按生成处理
        #     cls.gen(engine, name, *args, **kwargs)
        #     return
        data = engine.render_data[name]
        for k, v in kwargs.items():
            setattr(data, k, v)
        if engine.is_redis_used or engine.is_redis_log:
            # if not data.merge_lst: # 如果合并项为空，则杀死
            #     cls.kill(engine, name)
            # else:
            event =  {
            "target_type" :  "range_merge",
            "event_type" : "update",
            "event_property" : {
                    "range_merge_id" : data.merge_id,
                    "range_id_array" : data.merge_lst
                }
            }
            engine.push_render_event(event)
            data.render_event = event
            data.push_time = time.time()

    @classmethod
    def kill(cls, engine, name):
        if name not in engine.render_data:
            return # 不存在则不杀死
        data = super().kill(engine, name)
        if engine.is_redis_used or engine.is_redis_log:
            event =  {
            "target_type" :  "range_merge",
            "event_type" : "destroy",
            "event_property" : {
                    "range_merge_id" : data.merge_id
                }
            }
            engine.push_render_event(event)
            data.push_time = time.time()
            data.render_event = event    


class LinkState(Enum):
    DISCONNECT = 0
    CONNECT = 1
    COMMUNICATION = 2
    NOTLINK = 3

@dataclass
class LinkEffectData(SpecialEffectData):
    entity1: str = ""
    entity2: str = ""
    link_id: str = ""
    link_state: LinkState = LinkState.NOTLINK
    push_time: float = 0

class LinkEffect(SpecialEffect):
    @classmethod
    def gen(cls, engine, entity1, entity2):
        unit1 = engine.get_unit_base(entity1)
        unit2 = engine.get_unit_base(entity2)
        entity1 = unit1.name
        entity2 = unit2.name
        entity1id = engine.render_data[entity1].entity_id
        entity2id = engine.render_data[entity2].entity_id
        if entity1 == entity2: # 同一个平台之间的通信不连线
            # print(f"同一个平台{entity1}之间的通信不连线")
            return
        name = entity1id + "_link_" + entity2id
        data = super().gen(engine, name)
        data.entity1 = entity1
        data.entity2 = entity2

        engine.render_index += 1
        data.link_id = name + "_index_" + str(engine.render_index)
        if (engine.is_redis_used or engine.is_redis_log) and engine.render_config["network_link"]:
            # 因该对象与其他特效对象不同，是持续存在的，故在此处判断是否显示
            # 而其他非持续存在的对象，则在生成的地方判断是否显示
            if unit1.symbol_id == 33 or unit2.symbol_id == 33:
                pass # 不显示的实体也不显示通信连接线
            else:
                cls._push_event(engine, name, "create", LinkState.DISCONNECT)
    
    @classmethod
    def kill(cls, engine, entity1_id, entity2_id):
        # unit1 = engine.get_unit_base(entity1)
        # unit2 = engine.get_unit_base(entity2)
        # entity1 = unit1.name
        # entity2 = unit2.name
        # entity1_id = engine.render_data[entity1].entity_id
        # entity2_id = engine.render_data[entity2].entity_id
        name = entity1_id + "_link_" + entity2_id
        if name not in engine.render_data:
            return # 不存在则不杀死
        data = engine.render_data[name]
        if engine.is_redis_used or engine.is_redis_log:
            event = data.render_event
            event["event_property"].update({"time": engine.ymdhms})
            event.update({'time': time.time(), "event_type":"destroy"})
            engine.push_render_event(event)
            data.push_time = time.time()
            data.render_event = event
        super().kill(engine, name)

    @classmethod
    def _push_event(cls, engine, name, event_type, link_state):
        data = engine.render_data[name]
        if (data.entity1 not in engine.render_data) or (data.entity2 not in engine.render_data):
            return
        entity1_id = engine.render_data[data.entity1].entity_id
        entity2_id = engine.render_data[data.entity2].entity_id
        if link_state == LinkState.DISCONNECT:
            link_color = [100, 100, 100, 255]
            link_dynamic_color = [100, 100, 100, 255]
        elif link_state == LinkState.CONNECT:
            link_color = [0, 255, 0, 255]
            link_dynamic_color = [0, 255, 0, 255]
        elif link_state == LinkState.COMMUNICATION:
            link_color = [255, 255, 0, 255]
            link_dynamic_color = [255, 255, 0, 255]
        elif link_state == LinkState.NOTLINK:
            link_color = [100, 100, 100, 255]
            link_dynamic_color = [100, 100, 100, 255]
        else:
            raise RuntimeError("不合法的枚举值")
        event = {
                "target_type": "link",
                "event_type": event_type,
                "event_property": {
                    "link_id": data.link_id,
                    "entity_id1": entity1_id,
                    "entity_id2": entity2_id,
                    "link_width": 1,
                    "link_color": link_color,
                    "link_dynamic_color": link_dynamic_color,
                    "wave_length": 200,
                    "wave_speed": 5000
                }
            }
        if (engine.is_redis_used or engine.is_redis_log):
            engine.push_render_event(event)
        data.link_state = link_state
        data.render_event = event
        data.push_time = engine.tick

    @classmethod
    def kill_link(cls, engine, entity):
        unit1 =  engine.get_unit_base(entity)
        entity = unit1.name
        # entity1 所在的 link 优先删除, 再删除 entity1 本身的 effect
        # data = engine.render_data[entity]
        render_data = list(engine.render_data.keys())
        for name in render_data:
            entity_list = name.split("_link_")
            if len(entity_list) < 2:
                continue
            cls.kill(engine, entity_list[0], entity_list[1])
            cls.kill(engine, entity_list[1], entity_list[0])
                    
    @classmethod
    def update(cls, engine, name="", entity1="", entity2="", linkstate=None): # name只是占位符，以满足使用next_render_fun的格式要求，并无意义
        unit1 = engine.get_unit_base(entity1)
        unit2 = engine.get_unit_base(entity2)
        entity1 = unit1.name
        entity2 = unit2.name
        # 可能出现目标被击毁情况
        if entity1 in engine.render_data and entity2 in engine.render_data:
            entity1id = engine.render_data[entity1].entity_id
            entity2id = engine.render_data[entity2].entity_id
            name1 = entity1id + "_link_" + entity2id
            name2 = entity2id + "_link_" + entity1id
            if entity1 == entity2: # 同一个平台之间的通信不连线
                # print(f"同一个平台{name1}之间的通信不连线")
                return
            if not (unit1.isactive and unit2.isactive):
                if name1 in engine.render_data or name2 in engine.render_data:
                    cls.kill(engine, entity1,  entity2)
                    # print(unit1, unit2, name1)
                return
            if engine.sim_config["ignore_com"]:
                if linkstate == LinkState.COMMUNICATION:
                    if (name1 not in engine.render_data) and (name2 not in engine.render_data):
                        cls.gen(engine, entity1, entity2) # 先生成通信链路
                        return
                # 如果销毁，则生成时需要重新命名，故不销毁
                # elif linkstate == LinkState.NOTLINK:
                #     import pdb; pdb.set_trace()
                #     if (link_id in self._links) or (link_id2 in self._links):
                #         if link_id2 in self._links:
                #             link_id = link_id2
                #         event = self.gen_event(link_id, "destroy", linkstate) # 先删除显示.
                #         self.engine.push_render_event(event)
                #         return

            if name1 in engine.render_data:
                name = name1
            else:
                name = name2

        # 在忽略通信的情况下只有正在通信和不连接两种状态， 故注释掉
        # if self.engine.sim_config["ignore_com"]:
        #     if link_id not in self._links:
        #         self.engine.lock.acquire()
        #         self._links[link_id] = [LinkState.CONNECT, time.time(), unit1, unit2] 
        #         self.engine.lock.release() 
        if name not in engine.render_data:
            return 
        data = engine.render_data[name]
        old_state = data.link_state
        t = data.push_time

        if linkstate == LinkState.COMMUNICATION:
            if old_state == LinkState.COMMUNICATION and time.time() - t < engine.render_config["link_com_duration"]: # 间隔以内不更新
                return
            else:
                if not engine.sim_config["ignore_com"]:
                    engine.next_render_fun(name, "update", args=(entity1, entity2, LinkState.CONNECT), 
                        delay=engine.render_config["link_com_duration"]*engine.ratio)
                else:
                    # 在忽略通信的情况下只有正在通信和不连接两种状态
                    engine.next_render_fun(name, "update", args=(entity1, entity2, LinkState.NOTLINK), 
                        delay=engine.render_config["link_com_duration"]*engine.ratio)
        if engine.render_config["network_link"]:
            # 因该对象与其他特效对象不同，是持续存在的，故在此处判断是否显示
            # 而其他非持续存在的对象，则在生成的地方判断是否显示
            if unit1.symbol_id == 33 or unit2.symbol_id == 33:
                pass # 不显示的实体也不显示通信连接线
            else:
                cls._push_event(engine, name, "update", linkstate)

    @classmethod
    def gen_event(cls, link_id, event_type, link_state):
        entity1_id, entity2_id = link_id.split("_link_")
        if link_state == LinkState.DISCONNECT:
            link_color = [100, 100, 100, 255]
            link_dynamic_color = [100, 100, 100, 255]
        elif link_state == LinkState.CONNECT:
            link_color = [0, 255, 0, 255]
            link_dynamic_color = [0, 255, 0, 255]
        elif link_state == LinkState.COMMUNICATION:
            link_color = [255, 255, 0, 255]
            link_dynamic_color = [255, 255, 0, 255]
        elif link_state == LinkState.NOTLINK:
            link_color = [100, 100, 100, 255]
            link_dynamic_color = [100, 100, 100, 255]
        else:
            raise RuntimeError("不合法的枚举值")
        event = {
                "target_type": "link",
                "event_type": event_type,
                "event_property": {
                    "link_id": link_id,
                    "entity_id1": entity1_id,
                    "entity_id2": entity2_id,
                    "link_width": 1,
                    "link_color": link_color,
                    "link_dynamic_color": link_dynamic_color,
                    "wave_length": 200,
                    "wave_speed": 5000
                }
            }
        return event  

    @classmethod
    def _draw(cls, engine, name, ax=None, mode="draw"):
        items = []
        if engine.render_config["network_link"]:
            # 因该对象与其他特效对象不同，是持续存在的，故在此处判断是否显示
            # 而其他非持续存在的对象，则在生成的地方判断是否显示
            data = engine.render_data[name]
            unit1 = engine.get_unit_base(data.entity1)
            unit2 = engine.get_unit_base(data.entity2)
            linkstate = data.link_state
            if unit1.symbol_id == 33 or unit2.symbol_id == 33:
                return items # 不显示的实体也不显示通信连接线 
            x1, y1, _ = unit1.coords
            x2, y2, _ = unit2.coords
            if mode == "draw":
                if linkstate == LinkState.COMMUNICATION:
                    ax.plot([x1, x2], [y1, y2], "r--")
                elif linkstate == LinkState.CONNECT:
                    ax.plot([x1, x2], [y1, y2], "g--")
                elif linkstate == LinkState.DISCONNECT:
                    ax.plot([x1, x2], [y1, y2], "k--")
            else:
                if linkstate == LinkState.COMMUNICATION:
                    symbol = alg.shape.Symbol(mode="Line", type_="Link", x=[x1, x2], y=[y1, y2], color="red")
                elif linkstate == LinkState.CONNECT:
                    symbol = alg.shape.Symbol(mode="Line", type_="Link", x=[x1, x2], y=[y1, y2], color="green") 
                elif linkstate == LinkState.DISCONNECT:
                    symbol = alg.shape.Symbol(mode="Line", type_="Link", x=[x1, x2], y=[y1, y2], color="black")
                else:
                    # 如果NOTLINK，则不画
                    return items                       
                items.append(symbol)
        return items