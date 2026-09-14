import numpy as np
import copy
import collections






from simulation.core cimport entity, base, message
from simulation.core import CLASS, special_effect
from simulation import algorithm as alg

cdef class Attribute(Node):
    """ 目标属性类 
        为了实现 engine 的 save 功能, 包含 __getattr__ 方法的类都需要实现 __getstate__ 方法
    """


    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = copy.deepcopy(db)
        
        self._parent = parent
    
    
    


    property parent:
        def __get__(self):
            return self._parent
    
    def update(self, **kwargs):
        """更新装备性能数据
        """
        
        self.db.update(kwargs)
        
        
        
        
        

    def __getitem__(self, key):
        
        return self.db[key]

    def __getattr__(self, attr):
        return self.db[attr]

    def __setattr__(self, key, value):
        self.db[key] = value

    cpdef bint has_attr(self, str attr):
        return attr in self.db

    def __getstate__(self):
        return {
            'db': self.db,
            '_parent': self._parent
        }
    
    def __setstate__(self, state):
        self.db = state['db']
        self._parent = state['_parent']


cdef class Unit(entity.Router):
    """
    Unit是下面组件类及其继承类的对象的容器
    因用到消息转发，因此继承Router，但不继承转态机
    """

    def __init__(self, engine):
        super().__init__(engine, engine)
        self.engine.units_add(self) 
        
        self._components = base.Bag() 
        self._name_comps = {}
        self._model_comps = collections.defaultdict(list)
        self._is_assembled = False
        self._is_implemented = False
        self._is_checked = False
    
    cpdef employ(self, component):
        """ 添加一个组件到Unit
        """
        self._components.add(component)
        assert "." not in component.name, "名字中不能包含'.'"
        self._name_comps[component.name] = component
        assert "." not in component.model, "类别中不能包含'.'"
        assert "[" not in component.model and "]" not in component.model, "类别中不能包含'['和']',以区分类别和名字"
        self._model_comps[component.model].append(component)

    cpdef component(self, id):
        """ 根据id查询unit上指定的组件

        复杂度: O(log(n))
        Returns:
            component or None
        """
        return self._components.find(id)

    cpdef comp_by_name(self, str name):
        return self._name_comps[name]

    cpdef comps_by_model(self, str model):
        return self._model_comps[model]

    cpdef list components(self, fun=None):
        """ 查询unit上指定的组件

        返回符合指定过滤函数filtering function的组件列表或[].
        复杂度: O(n)
        """
        return list(filter(fun, self._components))
        
        
        
        
        
        

    cpdef message_handle(self, message.MESSAGE msg):
        """ 处理消息
        """
        if not self.isactive:
            self.engine.log_debug("Inactive %s cannot handle message %s" % (self, msg))
            return
        name = msg.body.content.__class__.__name__

        if name not in self._message_handlers:
            
            raise RuntimeError("%s cannot handle message %s" % (self, name))
        self.engine.log_debug("MessageHandle %s handle message[%s]", self, name)
        self._message_handlers[name](msg.body)

        
        
        
        
        
        

        
        
        
        
        
        
        
        
        
    cpdef _send_event(self, dst, content, delay=0):
        """ Unit仅可以发送事件，消息和指令不能发送，因只是一个容器 """
        assert content.__class__.__name__[:5] == "Event"
        body = message.Event(self, dst, self.engine.time, content)
        if dst is None:
            import pdb; pdb.set_trace()
        self._notify(dst, body, delay=None, delay_ms=int(delay*1000)) 
        self.engine.events.append(body)

    cpdef _add_handler(self, name, handler):
        """ Unit仅可以处理事件，消息和指令不能处理，因只是一个容器 """
        if name[:5] == "Event":
            self._message_handlers[name] = handler
        else:
            raise RuntimeError("the name must start with Event!")

    cpdef assemble(self):
        """ 配置属性参数等 """
        self._is_assembled = True
        for component in self._components:
            component.assemble()

    cpdef implement(self):
        """ 添加状态、消息处理等 """
        assert self._is_assembled, "%s先执行assemble或直接执行activate" % self
        self._is_implemented = True
        for component in self._components:
            component.implement()

    cpdef check(self):
        """ 检查配置 """
        assert self._is_implemented, "先执行implement或直接执行activate"
        self._is_checked = True
        for component in self._components:
            
            component.check()

    cpdef start(self):
        """ 启动 """
        
        assert self._is_checked, "先执行check或直接执行activate"
        
        entity.Router.start(self)
        for component in self._components:
            component.start()
           
    cpdef kill(self):
        """ Turn off the unit and make it inactive. """
        for component in self._components:
            component.kill()
        
        
        entity.Router.kill(self)

    cpdef draw(self, ax):
        if (self.engine.render_config["components_render"] == "all" or
            self.name in self.engine.render_config["components_render"]):
            for component in self._components:
                if component.isactive:
                    component.draw(ax) 

    cpdef draw3D(self, ax):
        if (self.engine.render_config["components_render"] == "all" or
            self.name in self.engine.render_config["components_render"]):
            for component in self._components:
                if component.isactive:
                    component.draw3D(ax)

    cpdef drawXz(self, ax):
        if (self.engine.render_config["components_render"] == "all" or
            self.name in self.engine.render_config["components_render"]):
            for component in self._components:
                if component.isactive:
                    component.drawXz(ax)
            
    cpdef list drawSymbol(self):
        items = []
        if (self.engine.render_config["components_render"] == "all" or
            self.name in self.engine.render_config["components_render"]):
            for component in self._components:
                if component.isactive:
                    q = component.drawSymbol()
                    if q:
                        items.extend(q)
        return items

    cpdef list drawSymbol3D(self):
        items = []
        if (self.engine.render_config["components_render"] == "all" or
            self.name in self.engine.render_config["components_render"]):
            for component in self._components:
                if component.isactive:
                    q = component.drawSymbol3D()
                    if q:
                        items.extend(q)
        return items
    
cdef class Platform(Unit):
    """ 平台Unit """
    
    
    single_attrs = ["characteristics", "vitalities", "comdev", "motor", "intelligence"]
    multi_attrs = ["radars", "sonars", "jammers", "emitters", "guiders", "weaponsystems"]
    def __init__(self, engine, name, model, group, ptype=None, country=None):
        super().__init__(engine)
        self.attr = Attribute(self, self.engine.db.get(model, unit_name=name, unit_model=model)) 
        assert self.__class__.__name__ == self.attr["class"], "%s != %s" % (self.__class__.__name__, self.attr["class"])
        self.name = name
        assert "." not in self.name, "名字中不能包含'.'"
        assert name not in self.engine._name_units, "名字%s已被其它单元使用"%name
        self.engine._name_units[name] = self
        self.model = model
        self.group = group.upper()
        self.ptype = ptype
        self.country = country
        self.isdetectable = True 
        
        self.home_unit = None 
        self.is_at_home = False 
        self._children = base.Bag() 
        self._munitions = base.Bag() 
        
        self.symbol_id = self.engine.get_entity_symbol_id(self)
        
        self._gen_components()

    def __str__(self):
        return "%s.%s.%s.%s" % (self.group, self.__class__.__name__, self.model, self.name) 

    def __repr__(self):
        if self.coords is None:
            return str(self) + " (nan,nan,nan)"
        return str(self) + " (%.3f,%0.3f,%0.3f)" % tuple(self.coords)

    
    
    

    cpdef _gen_components(self, home_unit=None):
        """ 生成平台上所有组件并挂载到平台上 """
        for attr in self.single_attrs: 
            if self.attr.has_attr(attr) and self.attr[attr]:
                if isinstance(self.attr[attr], str):
                    model = self.attr[attr]
                    obj = self._gen_component(model, home_unit=home_unit)
                else:
                    
                    assert isinstance(self.attr[attr], list)
                    model, pd, paz, ph, *sector = self.attr[attr]
                    obj = self._gen_component(model, home_unit=home_unit)
                    obj.set_pdah(pd, paz, ph)
                    assert len(sector) in [0, 2]
                    if sector:
                        obj.set_sector(sector)
                setattr(self, attr, obj)
            else:
                
                setattr(self, attr, None)
        for attr in self.multi_attrs:
            setattr(self, attr, [])
            if self.attr.has_attr(attr) and self.attr[attr]:
                for e in self.attr[attr]:
                    if isinstance(e, str):
                        model = e
                        obj = self._gen_component(model, home_unit=home_unit)
                    else:
                        
                        assert isinstance(e, list), e
                        model, pd, paz, ph, *sector = e
                        obj = self._gen_component(model, home_unit=home_unit)
                        obj.set_pdah(pd, paz, ph)
                        assert len(sector) in [0, 2]
                        if sector:
                            obj.set_sector(sector)
                    getattr(self, attr).append(obj)

    cpdef _gen_component(self, comp_model, home_unit=None):
        """ 生成平台上的指定组件 """
        if home_unit is None:
            model_dct = self.engine.db.get(comp_model, unit_name=self.name, unit_model=self.model)
        else:
            model_dct = self.engine.db.get(comp_model, unit_name=home_unit.name, unit_model=home_unit.model)
        if model_dct is None:
            raise RuntimeError("Platform._gen_component错误: 数据库中未查找到", comp_model, "其中home_unit:", home_unit)
        
        
        cls_ = CLASS[model_dct["class"]]
        obj = cls_(self, comp_model)
        return obj

    cpdef add_child(self, child, bint detectable=False):
        child.home_unit = self
        child.is_at_home = True
        child.isdetectable = detectable
        self._children.add(child)

    cpdef remove_child(self, child):
        child.home_unit = None
        child.is_at_home = False
        self._children.add(child)

    property munitions:
        def __get__(self):
            return self._munitions

    cpdef add_munition(self, munition, bint detectable=False):
        munition.home_unit = self
        munition.is_at_home = True
        munition.isdetectable = detectable
        self._munitions.add(munition)

    cpdef set_move_param(self, coords, velocity, coordinate_system="Cartesian"):
        """ 设置运动参数

        Args:
            coords: 位置参数，如果coordinate_system="Cartesian"，代表x, y, z
                             如果coordinate_system="Geodetic", 代表经度、纬度、高度(m)
                             如果coords[0]是tuple或，表示度、分、秒，否则表示浮点度
            velocity: 速度矢量，坐标系始终为"Cartesian"
        """
        if self.coords is not None:
            self.engine.log_warning("运动参数已经设置，重复设置会清除之前的设置")

        assert coordinate_system in ["Cartesian", "Geodetic"]

        if coordinate_system == "Cartesian":
            _coords = coords
        elif coordinate_system == "Geodetic":
            if isinstance(coords[0], (tuple, list)):
                lng = coords[0][0] + coords[0][1]/60.0 + coords[0][2]/3600.0
            else:
                lng = coords[0]
            if isinstance(coords[1], (tuple, list)):
                lat = coords[1][0] + coords[1][1]/60.0 + coords[1][2]/3600.0
            else:
                lat = coords[1]
            x, y = self.engine.lnglat2xy(lng, lat)
            _coords = np.array([x, y, coords[2]])
        else:
            _coords = coords
            self.engine.log_warning("坐标系设置不正确，默认使用Cartesian坐标系")

        self.motor.set_motivate_param(_coords, velocity)

    property coords:
        """ 空间位置坐标 """
        def __get__(self):
            return self.motor.coords

    property lnglat:
        """ 经纬度 """
        def __get__(self):
            return self.motor.lnglat

    property velocity:
        def __get__(self):
            return self.motor.velocity

    property acce:
        def __get__(self):
            return self.motor.acce

    property speed:
        def __get__(self):
            return self.motor.speed

    property course:
        """ 速度平面方向 """
        def __get__(self):
            return self.motor.course

    property pitch:
        def __get__(self):
            return self.motor.pitch

    property heading:
        def __get__(self):
            return self.course

    cpdef _hit_handler(self, event):
        """
        判断击中次数是否达到阈值，如达到则自毁
        """
        if not self.isactive:
            return
        attacker = event.src
        self.engine.log_info("BeHit %s %s %s %s",
            self, "(%.2f,%.2f,%.2f)" % tuple(self.coords),
            attacker,  "(%.2f,%.2f,%.2f)" % tuple(attacker.coords))
        
        if isinstance(self.vitalities.threshold.damage, int):
            self.vitalities.current.damage += 1
            if self.vitalities.current.damage >= self.vitalities.threshold.damage:
                self.kill()
        elif isinstance(self.vitalities.threshold.damage, dict):
            src_model = event.src.model
            self.vitalities.current.damage += self.vitalities.threshold.damage.get(src_model, 0)
            if self.vitalities.current.damage >= self.vitalities.threshold.damage['THRESHOLD']:
                self.kill()
                self.engine.log_physics("BeKilled %s %s",
                    self, "(%.2f,%.2f,%.2f)" % tuple(self.coords))
    
    cpdef set_damage_threshold(self, damage):
        self.vitalities.threshold.damage = damage

    cpdef kill(self):
        """ Turn off the unit and make it inactive. """
        assert self.isactive
        for munition in self._munitions:
            if munition.isactive:
                if munition.is_at_home:
                    munition.kill()
                elif munition.is_killed_with_home:
                    munition.kill()
        for child in self._children:
            if child.isactive:
                if child.is_at_home:
                    child.kill()
        
        Unit.kill(self)
        special_effect.EntityEffect.kill(self.engine, self.name)
        self.engine.log_physics("BeKilled %s %s",
            self, "(%.2f,%.2f,%.2f)" % tuple(self.coords))

    cpdef implement(self):
        
        Unit.implement(self)
        self._add_handler("EventHit", self._hit_handler)

    cpdef draw(self, ax):
        if self.engine.render_config["component_render_units"] == "all" or self.name in self.engine.render_config["component_render_units"]:
            for component in self._components:
                    if component.isactive:
                        component.draw(ax) 

    cpdef draw3D(self, ax):
        if self.engine.render_config["component_render_units"] == "all" or self.name in self.engine.render_config["component_render_units"]:
            for component in self._components:
                if component.isactive:
                    component.draw3D(ax)

    cpdef drawXz(self, ax):
        if self.engine.render_config["component_render_units"] == "all" or self.name in self.engine.render_config["component_render_units"]:
            for component in self._components:
                if component.isactive:
                    component.drawXz(ax)
            
    cpdef list drawSymbol(self):
        items = []
        if self.engine.render_config["component_render_units"] == "all" or self.name in self.engine.render_config["component_render_units"]:
            for component in self._components:
                if component.isactive:
                    q = component.drawSymbol()
                    if q:
                        items.extend(q)
        return items

    cpdef list drawSymbol3D(self):
        items = []
        if self.engine.render_config["component_render_units"] == "all" or self.name in self.engine.render_config["component_render_units"]:
            for component in self._components:
                if component.isactive:
                    q = component.drawSymbol3D()
                    if q:
                        items.extend(q)
        return items

cdef class Characteristics(entity.Entity):
    """ 目标特性类 
    类似Unit的组件，但和组件有所不同
    不需要状态机和消息转发机制，因此继承Entity
    """

    def __init__(self, unit, model):
        super().__init__(unit)
        self.unit = unit
        self.engine = unit.engine
        
        self.db = copy.deepcopy(self.engine.db.get(model, unit_name=unit.name, unit_model=unit.model))
        self.model = model

    def update(self, **kwargs):
        """更新目标特性数据
        """
        self.db.update(kwargs)

    def __getitem__(self, key):
        return self.db[key]

    def __getattr__(self, attr):
        return self.db[attr]

    def __getstate__(self):
        return (self.unit, self.engine, self.db, self.model)

    def __setstate__(self, state):
        unit, engine, db, model = state
        self.unit = unit
        self.engine = engine
        self.db = db
        self.model = model

cdef class Vitalities(entity.Entity):
    """ 生命力类 
    类似Unit的组件，但和组件有所不同
    不需要状态机和消息转发机制，因此继承Entity
    描述的是Unit的生存能力相关的参数，与Xsim的资源属性类似
    """

    def __init__(self, unit, model):
        super().__init__(unit)
        self.unit = unit
        self.engine = unit.engine
        
        self.threshold = Attribute(self, self.engine.db.get(model, unit_name=unit.name, unit_model=unit.model)) 
        self.model = model
        db = copy.deepcopy(self.engine.db.get(model, unit_name=unit.name, unit_model=unit.model))
        db = { key: 0 for key, value in db.items() }
        self.current = Attribute(self, db) 

cdef class Network(entity.FSM):
    """ 全联通通信网络 """ 
    def __init__(self, engine, model):
        super().__init__(engine, engine)
        
        self.engine.networks().append(self)
        
        
        self.attr = Attribute(self, engine.db[model])
        self.model = model
        assert self.__class__.__name__ == self.attr["class"]
        self._comdevs = set() 
        self._comdevs_linked = {} 
        
        
        key = self.model 
        if key not in self.engine.ids:            
            idd = 1
            self.engine.ids[key].append(idd)
        else:
            idd = self.engine.ids[key][-1] + 1
            self.engine.ids[key].append(idd)
        self.name = '%s[%d]' % (self.model, idd) 
        
        self._comdevs_send_time = {} 
        
    
    def __str__(self):
        return "%s.%s" % (self.__class__.__name__, self.name)

    def set_communication_distance(self, dis):
        assert dis >= 0
        self.attr.dis = dis

    cpdef add_comdev(self, comdev):
        """ 添加通信设备 """
        if self._comdevs:
            for dev0 in self._comdevs:
                self._comdevs_linked[(dev0, comdev)] = False
                special_effect.LinkEffect.gen(self.engine, dev0.unit.name, comdev.unit.name)
        self._comdevs.add(comdev)
        comdev.add_network(self)

    cpdef bint check_isin_net(self, comdev1, comdev2):
        """ 判断两个通信设备是否在该网络内
        """
        if (comdev1, comdev2) in self._comdevs_linked or  (comdev2, comdev1) in self._comdevs_linked:
            return True
        return False

    cpdef check_connect(self, comdev1, comdev2):
        """ 判断两个通信设备是否可通过该链路联通

        Returns:
            1. 如果不联通，返回-1; 如果联通，返回一个非负数，表示通信时延(s),可以为0
            2. 如果不联通，返回[]; 如果联通，返回使用的通信链路(通信设备)列表
        """
        if (comdev1, comdev2) in self._comdevs_linked and  self._comdevs_linked[(comdev1, comdev2)]:
            return self.attr.delay, [[comdev1, comdev2]]
        elif (comdev2, comdev1) in self._comdevs_linked and  self._comdevs_linked[(comdev2, comdev1)]:
            return self.attr.delay, [[comdev2, comdev1]]
        else:
            return -1, []

    cpdef _check_linked(self):
        for comdev1, comdev2 in self._comdevs_linked.keys():
            if alg.geo.distance(comdev1.coords, comdev2.coords) < self.attr.dis:
                if not self._comdevs_linked[(comdev1, comdev2)]:
                    special_effect.LinkEffect.update(self.engine, entity1=comdev1.unit.name, entity2=comdev2.unit.name,
                        linkstate=special_effect.LinkState.CONNECT)
                    self._comdevs_linked[(comdev1, comdev2)] = True
            else:
                if self._comdevs_linked[(comdev1, comdev2)]:
                    special_effect.LinkEffect.update(self.engine, entity1=comdev1.unit.name, entity2=comdev2.unit.name,
                        linkstate=special_effect.LinkState.DISCONNECT)
                    self._comdevs_linked[(comdev1, comdev2)] = False

    cpdef check(self):
        """ 查看通信距离与通信时延 """
        assert hasattr(self.attr, "dis") 
        assert hasattr(self.attr, "delay") 

    def implement(self):
        self._add_state("CHECK", self._check_linked, repeat=1, right_now=True)
        self._add_state("DEAD", lambda: None, repeat_ms=0)
        self._add_transfer("UNIFINED", "CHECK",lambda: True)

def lambda_None():
    return None
    
def lambda_True():
    return True
cdef class Component(FSM):
    """ 组件类

    继承消息机制以及状态机，并对消息机制改写
    实现对一般消息Msg、指令/命令Cmd、事件Event的发送接口、处理接口和处理
    实现对任务Task的处理，但屏蔽了对任务Task的发送接口和处理接口，只在Commander放开
    Componet以及其继承类中，不使用_notify发送信息
    必须使用_send_msg、_send_event、_send_cmd、_send_task发送
    """
    def __init__(self, unit, model):
        super().__init__(unit, unit.engine)
        self.unit = unit
        self.attr = Attribute(self, self.engine.db.get(model, unit_name=unit.name, unit_model=unit.model))
        self.model = model
        
        
        
        
        key = self.unit.name + "." + self.model 
        if key not in self.engine.ids:            
            idd = 1
            self.engine.ids[key].append(idd)
        else:
            idd = self.engine.ids[key][-1]+ 1
            self.engine.ids[key].append(idd) 
        self.name = '%s[%d]' % (self.model, idd)    
        self.unit.employ(self) 
        
        
        self._add_state("FREE", lambda_None, repeat_ms=0)
        self._add_state("DEAD", lambda_None, repeat_ms=0)
        self._add_transfer("UNIFINED", "FREE", lambda_True)
        
        self._controller = None 
        self._message_handlers = {} 

        self._paz = 0 
        self._pd = 0  
        self._ph = 0  
        self._sector = None 

        self._redis_links = {} 

    def __str__(self):
        return str(self.unit) + '.' + self.__class__.__name__ + "." + self.name

    def __repr__(self):
        if self.coords is None:
            return str(self) + " (nan,nan,nan)"
        return str(self) + " (%.3f,%0.3f,%0.3f)" % tuple(self.coords)

    property ucname:
        
        def __get__(self):
            return self.unit.name + "." + self.name

    cpdef set_pxyz(self, float px=0, float py=0, float pz=0):
        """ 设置组件相对于平台的坐标
        
        平台中轴线方向指向y轴(北)，x轴指向东
        """
        self._pd = np.sqrt(px**2+py**2)
        self._paz = np.rad2deg(np.arctan(px, py))
        self._ph = pz

    cpdef set_pdah(self, float pd=0, float paz=0, float ph=0):
        self._pd = pd
        self._paz = paz
        self._ph = ph

    cpdef set_sector(self, list sector):
        """ 设置组件的作用扇面
        """
        self._sector = np.array(sector)

    cpdef kill(self):
        self._change_state("DEAD")
        
        entity.FSM.kill(self)

    property group:
        def __get__(self):
            return self.unit.group

    property pxyz:
        """ 返回组件相对于平台的坐标
        
        平台中轴线方向指向y轴(北)，x轴指向东
        """
        def __get__(self):
            if self._pd == 0:
                return np.array([0 ,0, self._ph])
            rad = np.deg2rad(self._paz)
            return np.array([self._pd*np.sin(rad), self._pd*np.cos(rad), self._ph])


    property pdah:
        def __get__(self):
            return self._pd, self._paz, self._ph

    property sector:
        def __get__(self):
            return self._sector

    property coords:
        """ 空间位置坐标 """
        def __get__(self):
            if self._pd == 0:
                offset = np.array([0, 0, self._ph])
            else:
                rad = np.deg2rad(self._paz+self.unit.heading)
                offset = np.array([self._pd*np.sin(rad), self._pd*np.cos(rad), self._ph])
            return self.unit.coords + offset

    property velocity:
        def __get__(self):
            return self.unit.velocity

    property acce:
        def __get__(self):
            return self.unit.acce

    property speed:
        def __get__(self):
            return self.unit.speed

    property course:
        """ 速度平面方向 """
        def __get__(self):
            return self.unit.course
    
    property pitch:
        def __get__(self):
            return self.motor.pitch

    cpdef message_handle(self, message.MESSAGE msg):
        """ 处理消息
        """
        if not self.isactive:
            self.engine.log_debug("Inactive %s cannot handle message %s" % (self, msg))
            return
        name = msg.body.content.__class__.__name__

        if name not in self._message_handlers:
            
            raise RuntimeError("%s cannot handle message %s" % (self, name))
            
        self.engine.log_debug("MessageHandle %s handle message[%s]", self, name)
        self._message_handlers[name](msg.body)
        
        
        
        
        
        
        
        
        
        
        
        

    
    
    
    
    
    
    
    
    
    

    
    
    
    
    
    
    

    cpdef __send_message_body(self, dst, body):
        """ _send_msg、_send_cmd、_send_task的共用函数部分，统一写 

        因后续不独立使用,故用私有表示(双下划线)
        """
        if self.engine.sim_config["ignore_com"]:
            
            self._notify(dst, body, delay=None, delay_ms=0)
        elif self.unit is dst.unit:
            
            self._notify(dst, body, delay=None, delay_ms=0)
        elif self.unit.home_unit is dst.unit and self.unit.is_at_home:
            
            self._notify(dst, body, delay=None, delay_ms=0)
        elif dst.unit.home_unit is self.unit and dst.unit.is_at_home:
            
            self._notify(dst, body, delay=None, delay_ms=0)
        else:
            
            self._notify(self.unit.comdev, body, delay=None, delay_ms=0)
           
        if self.engine.sim_config["ignore_com"]:
            if self.unit is dst.unit:
                pass
            elif self.unit.home_unit is dst.unit and self.unit.is_at_home:
                pass
            elif dst.unit.home_unit is self.unit and dst.unit.is_at_home:
                pass
            else:
                special_effect.LinkEffect.update(self.engine, entity1=self.unit.name, entity2=dst.unit.name,
                        linkstate=special_effect.LinkState.COMMUNICATION)

    cpdef _send_msg(self, dst, content, bint isignored=True):
        """ 组件发送消息接口

        Args:
            dst:消息接收者
            content:发送的消息内容，是一个类对象
            isignored:如果通信条件不满足，消息是否直接忽略
        """
        assert content.__class__.__name__[:3] == "Msg"
        body = message.Msg(self, dst, self.engine.time, isignored, content)
        self.__send_message_body(dst, body)

    cpdef _send_cmd(self, dst, content, bint isignored=False):
        """ 组件发送指令接口

        指令通过改变组件的属性参数或者状态来实现特定的目的。
        指令的划分是一门艺术。
        任务与指令的区别是任务相对指令更复杂
        """
        assert content.__class__.__name__[:3] == "Cmd"
        body = message.Cmd(self, dst, self.engine.time, isignored, content)
        self.__send_message_body(dst, body)

    cpdef _send_event(self, dst, content, delay=0):
        if dst is None:
            import pdb; pdb.set_trace()
        assert content.__class__.__name__[:5] == "Event"
        body = message.Event(self, dst, self.engine.time, content)
        self._notify(dst, body, delay=None, delay_ms=int(delay*1000)) 
        self.engine.events.append(body)

    cpdef _add_handler(self, name, handler):
        if name[:3] == "Msg":
            self._message_handlers[name] = handler
        elif name[:3] == "Cmd":
            self._message_handlers[name] = handler
        elif name[:5] == "Event":
            self._message_handlers[name] = handler
        else:
            raise RuntimeError("the name must start with Msg or Cmd or Event!")

    cpdef list _draw(self, ax=None, str mode="draw"):
        """ 统一绘制tkinter界面和web地图界面的函数

        具体类中重写
        """
        items = []
        return items

    cpdef draw(self, ax):
        self._draw(ax, mode="draw")

    cpdef list drawSymbol(self):
        return self._draw(mode="symbol")

cdef class Motor(Component):
    """ 机动组件 """
    def __init__(self, unit, model):
        super().__init__(unit, model)
        self.distance = 0
        self._coords = None
        self._velocity = None
        self._acce = None
        self._prev_coords = None
        self._prev_course = 0 
        self._history_points = collections.deque(maxlen=self.engine.render_config["history_points_len"]) 
        self._ref_unit = None 
        self._redis_push_time = None 
        self._prev_pitch = 0 
        self._lnglath = None
        self._ecef_coords = None
        self._ecef_velocity = None
        self._ecef_acce = None

    property is_free:
        """ 判断是否是自由状态
        
        只有自由状态下才可以直接改变速度等属性
        在WaypointsMotor和ManeuverMotor中会重新定义is_free的判断条件
        """
        def __get__(self):
            if self._ref_unit is None:
                return True
            else:
                return False

    cpdef set_pxyz(self, float px=0, float py=0, float pz=0):
        raise RuntimeError("不能使用此方法") 

    cpdef set_pdah(self, float pd=0, float paz=0, float ph=0):
        raise RuntimeError("不能使用此方法") 

    cpdef set_sector(self, list sector):
        raise RuntimeError("不能使用此方法") 

    cpdef set_motivate_param(self, coords, velocity=[0, 0, 0]):
        """ 设置机动参数
        """
        self._coords = np.array(coords, dtype=float)
        self._velocity = np.array(velocity, dtype=float)
        self._acce = np.array([0.0, 0.0, 0.0], dtype=float)
        self._prev_coords = self._coords.copy()
        self._ref_unit = None
        self._last_course = self.course
        assert(self._coords.shape == self._velocity.shape)
        special_effect.EntityEffect.gen(self.engine, self.unit.name)
        special_effect.EntityEffect.show(self.engine, self.unit.name)
        lng, lat = self.engine.xy2lnglat(self._coords[0], self._coords[1])
        self._lnglath = np.array([lng, lat, self._coords[2]], dtype=np.float64)

    cpdef set_ref_unit(self, unit):
        self._ref_unit = unit
        self._coords = None
        self._velocity = None
        self._acce = None
        self._prev_coords = None
        if self.unit.coords is not None:
            special_effect.EntityEffect.gen(self.engine, self.unit.name)
            special_effect.EntityEffect.hide(self.engine, self.unit.name)

    property coords:
        def __get__(self):
            """ 空间位置坐标 """
            if self._ref_unit:
                return self._ref_unit.coords
            else:
                return self._coords

    property lnglat:
        def __get__(self):
            """ 经纬度 """
            if self._lnglath is not None:
                return self._lnglath[0], self._lnglath[1]
            x, y, z = self.coords
            lng, lat = self.engine.xy2lnglat(x, y)
            return lng, lat

    
    property velocity:
        def __get__(self):
            if self._ref_unit:
                return self._ref_unit.velocity
            else:
                return self._velocity

    property acce:
        def __get__(self):
            if self._ref_unit:
                return self._ref_unit.acce
            else:
                return self._acce

    
    property speed:
        def __get__(self):
            if self._ref_unit:
                return self._ref_unit.speed
            else:
                
                return alg.geo.norm3d(self._velocity)

    property course:
        def __get__(self):
            """ 速度平面方向 """
            if self._ref_unit:
                return self._ref_unit.course
                
            if self.speed == 0:
                return self._prev_course
            else:
                
                self._prev_course = alg.geo.azimuth(self._coords, self._coords + self._velocity)
                return self._prev_course
    
    property pitch:
        def __get__(self):
            """ 俯仰角 """
            if self._ref_unit:
                return self._ref_unit.pitch

            if self.speed == 0 or alg.geo.norm3d(self._velocity) == 0:
                return self._prev_pitch
            else:
                try:
                    
                    self._prev_pitch = alg.geo.pitch(self._coords, self._coords + self._velocity)
                except:
                    self._prev_pitch = 0
                return self._prev_pitch

    property mode:
        def __get__(self):
            """ 模式，默认为None
            """
            return None

    property ecef_coords:
        def __get__(self):
            """ 地心地固系下的坐标值
            """
            return self._ecef_coords

    property ecef_velocity:
        def __get__(self):
            """ 地心地固系下的速度值
            """
            return self._ecef_velocity

    property ecef_acce:
        def __get__(self):
            """ 地心地固系下的加速度值
            """
            return self._ecef_acce

    cpdef _move(self):
        """匀速/加速运动仿真模块
        """
        cdef double [:] _prev_coords_mv = self._prev_coords
        cdef double [:] _coords_mv = self._coords
        cdef double [:] _velocity_mv = self.velocity
        cdef double [:] _lnglath_mv = self._lnglath
        cdef double [:] _acce_mv = self._acce
        if self._ref_unit:
            pass
        else:
            if self.engine.render_config["history_points_units"] == "all" or self.unit.name in self.engine.render_config["history_points_units"]:
                if not self._history_points or self.course != self._last_course:
                    self._history_points.append([self.engine.time, self.coords[0], self.coords[1], self.coords[2]])
                else:
                    self._history_points[-1] = [self.engine.time, self.coords[0], self.coords[1], self.coords[2]]
                    
            period = self._state_period
            _prev_coords_mv[:] = _coords_mv[:]
            _coords_mv[0] += _velocity_mv[0] * period + 0.5 * _acce_mv[0] * period ** 2
            _coords_mv[1] += _velocity_mv[1] * period + 0.5 * _acce_mv[1] * period ** 2
            _coords_mv[2] += _velocity_mv[2] * period + 0.5 * _acce_mv[2] * period ** 2
            _velocity_mv[0] += _acce_mv[0] * period
            _velocity_mv[1] += _acce_mv[1] * period
            _velocity_mv[2] += _acce_mv[2] * period


            
            lng, lat = self.engine.xy2lnglat(_coords_mv[0], _coords_mv[1])
            _lnglath_mv[0] = lng
            _lnglath_mv[1] = lat
            _lnglath_mv[2] = _coords_mv[2]
            self.engine.log_debug("move")
            self.distance += alg.geo.distance(self._coords, self._prev_coords) 
            self._last_course = self.course
            special_effect.EntityEffect.update(self.engine, self.unit.name)

    cpdef _move_ecef(self):
        """按照地心地固系更新位置
        """
        cdef double [:] _ecef_coords_mv = self._ecef_coords
        cdef double [:] _ecef_velocity_mv = self._ecef_velocity
        cdef double [:] _ecef_acce_mv = self._ecef_acce

        cdef double [:] _prev_coords_mv = self._prev_coords
        cdef double [:] _coords_mv = self._coords
        cdef double [:] _velocity_mv = self.velocity
        cdef double [:] _lnglath_mv = self._lnglath
        cdef double [:] _acce_mv = self._acce

        if self._ref_unit:
            pass
        else:
            if self.engine.render_config["history_points_units"] == "all" or self.unit.name in self.engine.render_config["history_points_units"]:
                if not self._history_points or self.course != self._last_course:
                    self._history_points.append([self.engine.time, self.coords[0], self.coords[1], self.coords[2]])
                else:
                    self._history_points[-1] = [self.engine.time, self.coords[0], self.coords[1], self.coords[2]]
            
            period = self._state_period
            _ecef_coords_mv[0] += _ecef_velocity_mv[0] * period + 0.5 * _ecef_acce_mv[0] * period ** 2
            _ecef_coords_mv[1] += _ecef_velocity_mv[1] * period + 0.5 * _ecef_acce_mv[1] * period ** 2
            _ecef_coords_mv[2] += _ecef_velocity_mv[2] * period + 0.5 * _ecef_acce_mv[2] * period ** 2
            _ecef_velocity_mv[0] += _ecef_acce_mv[0] * period
            _ecef_velocity_mv[1] += _ecef_acce_mv[1] * period
            _ecef_velocity_mv[2] += _ecef_acce_mv[2] * period

            _prev_coords_mv[:] = _coords_mv[:]
            _lnglath_mv[0],  _lnglath_mv[1], _lnglath_mv[2] = alg.trf.ecef2geodetic(_ecef_coords_mv[0],  _ecef_coords_mv[1], _ecef_coords_mv[2])
            _coords_mv[0],  _coords_mv[1] = self.engine.lnglat2xy(_lnglath_mv[0],  _lnglath_mv[1])
            _velocity_mv[0], _velocity_mv[1], _velocity_mv[2] = alg.trf.ecef2enu_v(_ecef_velocity_mv[0], _ecef_velocity_mv[1], _ecef_velocity_mv[2], _lnglath_mv[0], _lnglath_mv[1])
            _acce_mv[0], _acce_mv[1], _acce_mv[2] = alg.trf.ecef2enu_v(_ecef_acce_mv[0], _ecef_acce_mv[1], _ecef_acce_mv[2], _lnglath_mv[0], _lnglath_mv[1])
            
            self.engine.log_debug("move")
            self.distance += alg.geo.distance(self._coords, self._prev_coords) 
            self._last_course = self.course
            special_effect.EntityEffect.update(self.engine, self.unit.name)
        

    def _send_msg(self, *args, **kwargs):
        raise RuntimeError("Motor can not send message")

    def _send_cmd(self, *args, **kwargs):
        raise RuntimeError("Motor can not send command")

    cpdef _change_speed(self, message.Cmd cmd):
        """ 改变速度大小
        """
        speed = cmd.content.speed
        self.change_speed(speed)

    cpdef _change_course(self, message.Cmd cmd):
        """ 改变速度水平方向
        """
        az = cmd.content.az
        self.change_course(az)

    cpdef _change_height(self, message.Cmd cmd):
        """ 直接改变高度, 慎用
        """
        height = cmd.content.height
        self.change_height(height)

    cpdef _change_velocity(self, message.Cmd cmd):
        """ 直接改变速度
        """
        v = cmd.content.velocity
        self.change_velocity(v)

    
    
    cpdef change_speed(self, float speed, bint ignore=False):
        """ 改变速度大小

        Args:
            ignore: 是否忽略is_free状态检查
        """
        if not ignore:
            assert self.is_free, "%s非自由状态下不能改变速度大小, 除非明确知道这样做没问题，可以将ignore设置为True" % self
        if self.speed > 0:
            self._velocity = speed / self.speed * self._velocity
        else:
            vx = speed * np.sin(self.course / 180 * np.pi)
            vy = speed * np.cos(self.course / 180 * np.pi)
            self._velocity = np.array([vx, vy, 0], dtype=float)

    cpdef change_course(self, float az, bint ignore=False):
        """ 改变速度水平方向,即航向

        Args:
            ignore: 是否忽略is_free状态检查
        """
        if not ignore:
            
            
            assert self.is_free, "%s非自由状态下不能改变航向, 除非明确知道这样做没问题，可以将ignore设置为True" % self
        az_rad = az * np.pi / 180
        vxy = np.sqrt(self._velocity[0]**2 + self._velocity[1]**2)
        vx = vxy * np.sin(az_rad)
        vy = vxy * np.cos(az_rad)
        self._velocity[0] = vx
        self._velocity[1] = vy

    cpdef change_height(self, float height, bint ignore=False):
        """ 直接改变高度, 慎用
        """
        if not ignore:
            assert self.is_free, "%s非自由状态下不能改变高度, 除非明确知道这样做没问题，可以将ignore设置为True" % self
        self._coords[2] = height
        self._lnglath[2] = height

    cpdef change_velocity(self, v, bint ignore=False):
        """ 直接改变速度
        """
        if not ignore:
            assert self.is_free, "%s非自由状态下不能改变速度, 除非明确知道这样做没问题，可以将ignore设置为True" % self
        self._velocity = np.array(v, dtype=float)

    cpdef change_acce(self, acce, bint ignore=False):
        """ 直接改变加速度
        """
        if not ignore:
            assert self.is_free, "%s非自由状态下不能改变加速度, 除非明确知道这样做没问题，可以将ignore设置为True" % self
        self._acce = np.array(acce, dtype=float)
    
 
    def implement(self):
        """Add transfer and handler"""
        self._add_state("MOVE", self._move, repeat=self.attr.period)
        self._add_transfer("FREE", "MOVE", lambda: True)
        self._add_handler("CmdMotorChangeSpeed", self._change_speed)
        self._add_handler("CmdMotorChangeVelocity", self._change_velocity)
        self._add_handler("CmdMotorChangeCourse", self._change_course)
        self._add_handler("CmdMotorChangeHeight", self._change_height)

    cpdef check(self):
        self.attr.has_attr("period")
        if self._ref_unit is None and self._coords is None:
            raise RuntimeError("机动组件[%s]未配置位置参数" % self)

    cpdef kill(self):
        
        Component.kill(self)

    cpdef draw(self, ax):
        
        Component.draw(self, ax)
        
        if self.engine.render_config["history_points_units"] == "all" or self.unit.name in self.engine.render_config["history_points_units"]:
            if self._history_points:
                t, x, y, z = list(zip(*self._history_points))
                ax.plot(x, y, "-", c=self.group, linewidth=1)
        

    cpdef draw3D(self, ax):
        
        if self.engine.render_config["history_points_units"] == "all" or self.unit.name in self.engine.render_config["history_points_units"]:
            if self._history_points:
                t, x, y, z = list(zip(*self._history_points))
                ax.plot(x, y, z, "-", c=self.group, linewidth=1)

    cpdef drawXz(self, ax):
        
        if self.engine.render_config["history_points_units"] == "all" or self.unit.name in self.engine.render_config["history_points_units"]:
            if self._history_points:
                t, x, y, z = list(zip(*self._history_points))
                ax.plot(x, z, "-", c=self.group, linewidth=1)

    cpdef list drawSymbol(self):
        
        items = Component.drawSymbol(self)
        
        if self.engine.render_config["history_points_units"] == "all" or self.unit.name in self.engine.render_config["history_points_units"]:
            if self._history_points:
                t, x, y, z = list(zip(*self._history_points))
                symbol = alg.shape.Symbol(mode="Line", type_="MotorTrack", group=self.group, name=self.name,
                                    x=x, y=y, color=self.group)
                items.append(symbol)
        return items

cdef class Comdev(Component):
    """ 通信设备组件 """
    def __init__(self, unit, model):
        super().__init__(unit, model)
        self._networks = set()
        self.__msgs = [] 

    cpdef add_network(self, network):
        self._networks.add(network)

    cpdef remove_network(self, network):
        if network in self._networks:
            self._networks.remove(network)
        else:
            self.engine.log_warning("移除未建立连接的网络")

    cpdef _check_connect(self, comdev):
        """ 判断两个通信设备之间通过通信网络是否连通
        
        Returns:
            delay: -1,不联通; 或者非负数表示时延(s)
        """
        for network in self._networks:
            delay, links = network.check_connect(self, comdev)
            if delay >= 0:
                return delay, links
        return -1, []

    cpdef message_handle(self, message.MESSAGE msg):
        """ 重写处理消息方法，因通信设备比较特殊
        """
        if not self.isactive:
            self.engine.log_debug("Inactive %s cannot handle message %s" % (self, msg))
            return    
        
        name = msg.body.content.__class__.__name__
        if msg.body.dst is self:
            
            if name not in self._message_handlers:
                
                raise RuntimeError("%s cannot handle message %s" % (self, name))
            self.engine.log_debug("MessageHandle %s handle message[%s]", self, name)
            self._message_handlers[name](msg.body)
        else:
            
            
            
            
                
                
                    
                    
                
            
            if msg.body.dst.unit is self.unit:
                
                self._notify(msg.body.dst, msg.body, delay=None, delay_ms=0)
                self.engine.log_info("%s Transfer message[%s] to self unit component %s", self, name, msg.body.dst)
            else:
                
                delay, links = self._check_connect(msg.body.dst.unit.comdev)
                if delay >= 0:
                    self._notify(msg.body.dst.unit.comdev, msg.body, delay=delay, delay_ms=None)
                    for dev1, dev2 in links:
                        special_effect.LinkEffect.update(self.engine, entity1=dev1.unit.name, entity2=dev2.unit.name, linkstate=special_effect.LinkState.COMMUNICATION)
                    self.engine.log_info("%s Transfer message[%s] to other unit comdev %s", self, name, msg.body.dst.unit.comdev)
                elif msg.body.isignored:
                    self.engine.log_info("%s Ignore message[%s]", self, name)
                else:
                    self.__msgs.append(msg.body)

    def _send_msg(self, *args, **kwargs):
        raise RuntimeError("Comdev can not send message")

    def _send_cmd(self, *args, **kwargs):
        raise RuntimeError("Comdev can not send command")

    
    
    
    
    
    
    
    
    

    cpdef _work(self):
        idx = []
        for i, msg in enumerate(self.__msgs):
            delay, links = self._check_connect(msg.dst.unit.comdev)
            if delay >= 0:
                self._notify(msg.dst.unit.comdev, msg, delay=delay)
                for dev1, dev2 in links:
                    special_effect.LinkEffect.update(self.engine, entity1=dev1.unit.name, entity2=dev2.unit.name, linkstate=special_effect.LinkState.COMMUNICATION)
                name = msg.content.__class__.__name__
                self.engine.log_info("%s Transfer message[%s] to other unit comdev %s", self, name, msg.dst.unit.comdev)
                idx.append(i)
        for i in idx[::-1]:
            self.__msgs.pop(i)

    def implement(self):
        self._add_state("WORK", self._work, repeat=self.attr.period)
        self._add_transfer("FREE",  "WORK", lambda: True)

    cpdef check(self):
        assert hasattr(self.attr, "period")

    cpdef kill(self):
        special_effect.LinkEffect.kill_link(self.engine, self.unit.name)
        Component.kill(self)


cdef class Driver(Component):
    """驾驶员组件
    """
    def __init__(self, unit, model):
        super().__init__(unit, model)
        self._motor = self.unit.motor
        '''设置driver之间的关系：
        driver之间只有两级上下级关系（即不存在上级的上级或下级的下级）
        因此有三种角色：
        leader:领导者
        subordinate：从属者
        ordinary：二者皆不是
        '''
        self._role = "ordinary"
        self._leader = None 
        self._subordinates = set() 
        self._companions = set() 

    property role:
        def __get__(self):
            return self._role

    '''
    下述五个处理关系的函数set_leader、_add_subordinate、_remove_subordinate、_update_subordinates_companions、_update_companions
    其中set_leader是入口函数
    leader如果没有下属的driver会自动降级为ordinary,然后如果需要可以为其设置leader
    在设置关系的过程中没有通过消息机制，因此未考虑跨平台的通信的影响，后续如果需要，可以加上
    '''
    cpdef set_leader(self, driver):
        if self._role == "ordinary":
            assert self._leader is None
            assert not self._subordinates
            assert not self._companions
            self._role = "subordinate"
            self._leader = driver
            driver._add_subordinate(self)
        elif self._role == "subordinate":
            assert not self._subordinates
            assert not self._companions
            if self._leader is not driver:
                self._leader._remove_subordinate(self)
                driver._add_subordinate(self)
                self._leader = driver
        elif self._role == "leader":
            raise RuntimeError("cannot set leader for a leader role")
            
    cpdef _add_subordinate(self, driver):
        if self._role == "ordinary":
            assert self._leader is None
            assert not self._subordinates
            assert not self._companions
            self._role = "leader"
            self._subordinates.add(driver)
        elif self._role == "subordinate":
            assert self._leader is not None
            assert not self._subordinates
            
            self._leader._remove_subordinate(self)
            self._leader = None
            self._role = "leader"
            self._subordinates.add(driver)
        elif self._role == "leader":
            assert self._leader is None
            assert self._subordinates
            assert not self._companions
            self._subordinates.add(driver)
        self._update_subordinates_companions()

    cpdef _remove_subordinate(self, driver):
        assert self._role == "leader"
        assert self._leader is None
        assert self._subordinates
        assert not self._companions
        self._subordinates.remove(driver)
        self._update_subordinates_companions()
        if not self._subordinates:
            self._role = "ordinary"

    cpdef _update_subordinates_companions(self):
        assert self._role == "leader"
        assert self._leader is None
        assert self._subordinates
        assert not self._companions
        for sub in self._subordinates:
            sub._role == "subordinate"
            sub._companions = self._subordinates-set([sub])

    cpdef _work(self):
        pass

    def implement(self):
        self._add_state("WORK", self._work, repeat=self.attr.period)
        self._add_transfer("FREE",  "WORK", lambda: True)
        return self

cdef class Commander(Component):
    """指挥员组件
    """
    def __init__(self, unit, model):
        super().__init__(unit, model)
        self._superior_commander = None 
        self._junior_commanders = set() 
        self._intel = None

    cpdef add_junior_commander(self, commander):
        """ 设置上下级指挥关系的入口函数 
        
        在添加本级的下属指挥所时，会自动将下属的上级设置为本级
        """
        assert commander is not self
        assert isinstance(commander, Commander)
        assert commander._superior_commander is None
        self._junior_commanders.add(commander)
        commander._superior_commander = self

    cpdef _send_task(self, dst, content, bint isignored=False):
        """ 组件发送任务接口
        只有Commander才可以发送和处理任务

        Args:
            dst:消息接收者
            content:发送的消息内容，是一个类对象
            isignored:如果通信条件不满足，消息是否直接忽略
        """
        assert content.__class__.__name__[:4] == "Task"
        assert isinstance(dst, Commander), "目的地必须也是Commander"
        assert self.unit is not dst.unit, "不能是同一个Unit"
        body = message.Task(self, dst, self.engine.time, isignored, content)
        self._Component__send_message_body(dst, body)

    cpdef _add_handler(self, name, handler):
        """ 对Component的进行重写，以增加对Task的处理
        """
        if name[:3] == "Msg":
            self._message_handlers[name] = handler
        elif name[:3] == "Cmd":
            self._message_handlers[name] = handler
        elif name[:5] == "Event":
            self._message_handlers[name] = handler
        elif name[:4] == "Task":
            self._message_handlers[name] = handler
        else:
            raise RuntimeError("the name must start with Msg or Cmd or Event or Task!")

    cpdef _command(self):
        pass

    cpdef assemble(self):
        self._intel = self.unit.intelligence

    def implement(self):
        self._add_state("COMMAND", self._command, repeat=self.attr.period)
        self._add_transfer("FREE",  "COMMAND", lambda: True)
        self._add_handler("MsgStateInfo", lambda msg:None)
        

    cpdef check(self):
        self.attr.has_attr("period")

cdef class Sensor(Component):
    """传感器组件
    """
    def __init__(self, unit, model):
        super().__init__(unit, model)
        self._processors = set()  
        self._is_on = False 

    property is_on:
        def __get__(self):
            return self._is_on

    cpdef add_processor(self, processor):
        self.engine.log_warning("该方法已弃用, 请使用 add_consumer")
        self._processors.add(processor)

    cpdef add_consumer(self, processor):
        self._processors.add(processor)

    cpdef remove_intel(self, intel):
        self._processors.remove(intel)

    cpdef turn_on(self):
        """开机"""
        assert not self._is_on, self
        self._is_on = True
        self._change_state("WORK") 

    cpdef turn_off(self):
        """关机"""
        assert self._is_on
        self._is_on = False
        self._change_state("FREE") 

    cpdef _detect(self):
        raise RuntimeError("须在子类中定义")

    cpdef _send_track(self, track):
        
        content = message.MsgTrack(track)
        for intel in self._processors:
            self._send_msg(intel, content)

    cpdef _turn_on(self, cmd):
        """开机"""
        self.turn_on()

    cpdef _turn_off(self, cmd):
        """关机"""
        self.turn_off()

    cpdef assemble(self):
        if hasattr(self.unit, "intelligence") and self.unit.intelligence is not None:
            self._processors.add(self.unit.intelligence)

    cpdef implement(self):
        self._add_state("WORK", self._detect, self.attr.period) 
        self._add_handler("CmdSensorTurnOn", self._turn_on)
        self._add_handler("CmdSensorTurnOff", self._turn_off)

    cpdef check(self):
        assert self.attr.has_attr("period")

cdef class Munition(Platform):
    """ 弹药平台
    """
    multi_attrs = []
    single_attrs = ["characteristics", "vitalities", "lethality", "seeker", "motor", "monitor"]
    def __init__(self, home_unit, model):
        super().__init__(home_unit.engine, str(self.id), model, home_unit.group, ptype=model)
        home_unit.add_munition(self, detectable=False) 
        self.is_killed_with_home = False 
        
        
        key = home_unit.name + "_" + model
        if key not in self.engine.ids:            
            idd = 1
            self.engine.ids[key].append(idd)
        else:
            idd = self.engine.ids[key][-1]+ 1
            self.engine.ids[key].append(idd)
        self.name = '%s_%s[%d]' % (home_unit.name, model, idd) 
        self._str_name = '%s[%d]' % (model, idd)
        assert "." not in self.name, "名字中不能包含'.'"
        assert self.name not in self.engine._name_units
        self.engine._name_units[self.name] = self
        self.engine._name_units.pop(str(self.id))
        
        
        
        if hasattr(self, 'motor'):
            self.motor.set_ref_unit(home_unit) 
        else:
            self.set_ref_unit(home_unit)
        self.foe = None
        self.strike_chain = None
        
    def __str__(self):
        return str(self.home_unit) + '.' + self.__class__.__name__ + "." + self._str_name

    def set_move_param(self, coords, velocity):
        raise RuntimeError("Munition cannot use set_move_param, should use emit")

    cpdef emit(self):
        self.is_at_home = False
        raise RuntimeError("须在子类中实现该方法")

    cpdef draw(self, ax):
        
        Platform.draw(self, ax)
        try:
            x, y, _ = self.coords 
        except:
            return
        ax.scatter(x, y, c=self.group, 
            marker=(3, 0, self.course), s=20, alpha=0.5)

    cpdef draw3D(self, ax):
        
        Platform.draw3D(self, ax)
        x, y, z = self.coords
        ax.scatter(x, y, z, c=self.group, marker="o")
    
cdef class Lethality(Component):
    """ 弹药的杀伤能力类/战斗部类
    """
    def __init__(self, unit, model):
        assert isinstance(unit, Munition)
        super().__init__(unit, model)

    cpdef is_lethal(self, foe):
        assert RuntimeError("子类中实现该方法")

cdef class ChildPlatform(Platform):
    """ 子平台，可从母平台脱离
    """
    multi_attrs = []
    single_attrs = ["characteristics", "vitalities", "motor"]
    def __init__(self, home_unit, model):
        super().__init__(home_unit.engine, str(self.id), model, home_unit.group)
        home_unit.add_child(self, detectable=False) 
        self.is_killed_with_home = False 
        
        
        key = home_unit.name + "_" + model
        if key not in self.engine.ids:            
            idd = 1
            self.engine.ids[key].append(idd)
        else:
            idd = self.engine.ids[key][-1]+ 1
            self.engine.ids[key].append(idd)
        self.name = '%s_%s[%d]' % (home_unit.name, model, idd) 
        self._str_name = '%s[%d]' % (model, idd)
        assert "." not in self.name, "名字中不能包含'.'"
        assert self.name not in self.engine._name_units
        self.engine._name_units[self.name] = self
        self.engine._name_units.pop(str(self.id))
        
        
        
        self.motor.set_ref_unit(home_unit) 
        
    def __str__(self):
        return str(self.home_unit) + '.' + self.__class__.__name__ + "." + self._str_name

    def set_move_param(self, coords, velocity):
        raise RuntimeError("Munition cannot use set_move_param, should use emit")

    cpdef release(self):
        self.is_at_home = False
        raise RuntimeError("须在子类中实现该方法")

    cpdef draw(self, ax):
        
        Platform.draw(self, ax)
        try:
            x, y, _ = self.coords 
        except:
            return
        ax.scatter(x, y, c=self.group, 
            marker=(3, 0, self.course), s=20, alpha=0.5)

    cpdef draw3D(self, ax):
        
        Platform.draw3D(self, ax)
        x, y, z = self.coords
        ax.scatter(x, y, z, c=self.group, marker="o")

cdef class DependentPlatform(ChildPlatform):
    """ 依附平台
        该平台只能依附于某个具体的平台，不能独立移动
        该平台主要是起到一个Unit的作用,挂载指挥机构等。
    """
    single_attrs = ["characteristics", "vitalities", "comdev", "motor", "intelligence", "commander"]
    
    multi_attrs = []

    def __init__(self, home_unit, model):
        super().__init__(home_unit, model)
        

    def set_move_param(self, coords, velocity):
        
        raise RuntimeError("DependentPlatform cannot use set_move_param")

    cpdef release(self):
        
        raise RuntimeError("DependentPlatform cannot use release")

cdef class FixedPlatform(Platform):
    cpdef check(self):
        
        Platform.check(self)
        assert self.motor.model == "FixedMotor", self
        
    cpdef draw(self, ax):
        
        Platform.draw(self, ax)
        x, y, _ = self.coords
        ax.scatter(x, y, c=self.group, marker=alg.marker.IconMarker("Base", self.course), s=150)
        if self.engine.render_config["name"]:
            ax.text(x, y, self.name, fontsize=6)

    cpdef drawXz(self, ax):
        
        Platform.drawXz(self, ax)
        x, _, z = self.coords
        ax.scatter(x, z, c=self.group, marker="D", s=150)
        if self.engine.render_config["name"]:
            ax.text(x, z, self.name, fontsize=6)

    cpdef draw3D(self, ax):
        
        Platform.draw3D(self, ax)
        x, y, z = self.coords
        ax.scatter(x, y, z, c=self.group, marker="D")
        if self.engine.render_config["name"]:
            ax.text(x, y, z, self.name, fontsize=6)