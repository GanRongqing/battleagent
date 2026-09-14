from copy import deepcopy
from logging.handlers import QueueHandler
import pdb
import os
import time
import grpc
import json
import dill
import math
import redis
import random
import socket
import pyproj
import logging
import datetime
import requests
import threading
import traceback
import collections
from queue import Queue
import struct
import numpy as np
from threading import Lock
from gettext import lngettext
from collections import defaultdict
from shapely.ops import unary_union
from shapely import geometry
from shapely.geometry import MultiPolygon
from collections import defaultdict, OrderedDict
from dataclasses import dataclass
from functools import reduce
from simulation.algorithm.drive import velocity
from simulation.utilities.grpc_utils import GRPC_OPTIONS
import simulation.arsenal as asn
from simulation import algorithm as alg
# from .. import core

from simulation.core cimport base, entity, arch
from simulation.core cimport message as cmsg
from simulation.core import log, enums, special_effect, CLASS
from simulation import database
from simulation import simserver_pb2_grpc, simserver_pb2
from simulation.utilities.branch_deduce import BranchTriggerHandler
import asyncio
import nats

dill.settings.update({'byref': True, 'recurse': True})  # byref 记录引用 recurse 允许查找全局变量

DIR = os.path.dirname(os.path.abspath(__file__))


class SimStop(Exception):
    """ Simulation Stop Signal """


def strpms(epoch):
    fmt = "%Y-%m-%d %H:%M:%S"
    sec = time.mktime(time.strptime(epoch, fmt)) if epoch else time.time()
    return sec


def _manipulator(engine, interval, manipulator):
    manipulator(engine)
    engine._next(_manipulator, args=(engine, interval, manipulator,), delay_ms=int(interval * 1000))


cdef class DispatchEngine(entity.Router):
    """ 基础仿真引擎

    提供基础通用的仿真调度功能
    """

    def __init__(self, name="engine", epoch=None, flag=log.INFO, terminal=True, logpath=None, db=None,
                 raise_error=enums.RaiseErrorFlag.DEBUG):
        super().__init__(parent=None, engine=self)
        if name is None:
            name = "engine"
        assert isinstance(name, str), "expect str, got %s" % type(name)
        if epoch is not None:
            assert isinstance(epoch, str), "expect str, got %s" % type(epoch)
        assert isinstance(flag, int), "expect int, got %s" % type(flag)
        if logpath is not None:
            assert os.path.isabs(logpath)
        if db is not None:
            assert isinstance(db, database.DataBase)

        self.name = name
        self.db = db
        assert isinstance(raise_error, enums.RaiseErrorFlag)
        self._raise_error_flag = raise_error
        self._is_activated = False
        self._epoch = strpms(epoch)  # 开始仿真时间, s
        self._tick = 0  # 当前时刻, 等价于毫秒(ms)
        self._cron = base.Heap()  # 引擎的事件调度队列
        self._tracer = log.get_tracer(self, flag, terminal, logpath)
        self._begin_real_tick = time.time() * 1000.0  # 记录上一次改变仿真速度时的真实时刻
        self._begin_sim_tick = self._tick  # 记录上一次改变仿真速度时的仿真时刻
        self._upper_tick = np.inf  # 在本次加速仿真内的仿真时间上限
        self._ratio_assess_real_tick = time.time() * 1000.0  # 为评估真实的仿真速率而记录每个评估周期的开始时间
        self._ratio_assess_sim_tick = self._tick  # 为评估真实的仿真速率而记录每个评估周期的开始tick
        self._ratio_assess = 10  # 评估真实的仿真速率，仿真速率始终不能为0，包括初始值
        self._is_pause = False  # 仿真是否暂停标志
        self._is_terminated = False  # 仿真是否结束
        self._is_probe = False  # 仿真是否暂停并进行干预
        self._ratio = "SYSTEM"  # 仿真比率
        self._step_end_tick = np.inf  # 记录该步结束时刻
        self._end_tick = np.inf  # 仿真结束时刻
        self._starter = None  # 启动后更新前的初始化函数
        self._terminater = None  # 仿真结束前执行的函数
        self._manipulators = []  # 第三方操作手列表
        self.cache = {}  # 存储临时变量列表，方便操作手函数使用
        self._threads = []  # 子线程列表

    cpdef set_start_epoch(self, str start_epoch):
        """ Set start_epoch 开始新的局
        """
        self._epoch = strpms(start_epoch)

    property tick:
        """ Time elapsed since the simulation started to run (millisecond).
            自模拟以来运行时间
        Returns
        -------
        tick : int
        """
        def __get__(self):
            return self._tick

    property time:
        """ Time elapsed since the simulation started to run (second).
            当前仿真时间
        Returns
        -------
        tick : int
        """
        def __get__(self):
            return self._tick * 1e-3

    property time2:
        """ 仿真时间 """
        def __get__(self):
            t = self._tick * 1e-3 + self._epoch
            return t

    property ymdhms:
        """ 仿真时间
        """
        def __get__(self):
            ymdhms = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime((self._tick * 1e-3 + self._epoch)))
            return ymdhms

        
    # cdef不支持**kwargs的关键字输入
    def log_critical(self, msg, *args, **kwargs):
        """ CRITICAL级别的日志记录接口 """
        # 50
        self._tracer.critical(msg, *args, **kwargs)
        if self._raise_error_flag is enums.RaiseErrorFlag.TERMINATE:
            print("程序发生严重错误， 直接结束")
            self.terminate()
        elif self._raise_error_flag is enums.RaiseErrorFlag.RAISE:
            print("程序发生严重错误， 抛出错误")
            raise RuntimeError("程序发生严重错误")
        else:  # enums.RaiseErrorFlag.DEBUG:
            print("程序发生错误， 进入调试模式，按w快捷键回退发生错误的位置")
            import pdb;
            pdb.set_trace()

    def log_error(self, msg, *args, **kwargs):
        """ ERROR级别的日志记录接口 """
        # 40
        self._tracer.error(msg, *args, **kwargs)
        if self._raise_error_flag is enums.RaiseErrorFlag.TERMINATE:
            print("程序发生错误， 直接结束")
            self.terminate()
        elif self._raise_error_flag is enums.RaiseErrorFlag.RAISE:
            print("程序发生错误， 抛出错误")
            raise RuntimeError("程序发生严重错误")
        else:  # enums.RaiseErrorFlag.DEBUG:
            print("程序发生错误， 进入调试模式，按w快捷键回退发生错误的位置")
            import pdb;
            pdb.set_trace()

    def log_warning(self, msg, *args, **kwargs):
        """ WARNING级别的日志记录接口 """
        # 30
        self._tracer.warning(msg, *args, **kwargs)

    def log_info(self, msg, *args, **kwargs):
        """ INFO级别的日志记录接口 """
        # 20
        self._tracer.info(msg, *args, **kwargs)

    def log_debug(self, msg, *args, **kwargs):
        """ DEBUG级别的日志记录接口 """
        # 10
        if logging.DEBUG >= self._tracer.logger.level:
            self._tracer.debug(msg, *args, **kwargs)

    property ratio:
        """
        仿真速率
        Returns:

        """
        def __get__(self):
            return self._ratio_assess

    cpdef set_ratio(self, ratio):
        """
        调节仿真速率
        Args:
            ratio: 仿真速率

        Returns:

        """
        self._ratio = ratio
        self._begin_real_tick = time.time() * 1000.0
        self._begin_sim_tick = self._tick

    cpdef set_ratio_inf(self):
        """以最大倍率运行仿真
        """
        self._ratio = "SYSTEM"  # 仿真比率
        self._begin_real_tick = time.time() * 1000.0
        self._begin_sim_tick = self._tick

    property end_time:
        """
        结束仿真时间
        Returns:仿真结束时刻

        """
        def __get__(self):
            return self._end_tick / 1000.0

    cpdef set_end_time(self, float time):
        """
        设置仿真结束时间
        Args:
            time: 时间

        Returns:

        """
        self._end_tick = time * 1000

    cpdef pause_continue(self):
        # 引擎暂停启动状态切换
        self._is_pause = not self._is_pause

    cpdef set_probe(self):
        """
        设置探针以暂停并干预
        Returns:

        """

        self._is_probe = True

    cpdef set_starter(self, starter):
        """ 设置仿真开始前执行的函数
        
        starter作为函数只有一个参数，参数为engine
        """
        self._starter = starter

    cpdef set_terminater(self, terminater):
        """ 设置仿真结束前执行的函数
        
        terminater作为函数只有一个参数，参数为engine
        """
        self._terminater = terminater

    def add_manipulator(self, manipulator, float interval=1):
        """
        Args:
            manipulator: 函数对象，只能以engine作为唯一的参数
        """
        # 这个函数现在在 engine 外层
        # def _manipulator():
        #     manipulator(self)
        #     self._next(_manipulator, delay_ms=int(interval*1000))

        self._manipulators.append([_manipulator, [self, interval, manipulator]])
        if self._is_activated:  # 如果引擎已启动，则手动激活
            _manipulator(self, interval, manipulator)

    cpdef add_threading(self, thread, args=(), bint deamon=True):
        """
        Args:
            thread: 以独立线程执行的函数对象，默认以engine作为第一个参数
        """
        t = threading.Thread(target=thread, args=(self,) + args, daemon=deamon)
        self._threads.append(t)
        if self._is_activated:  # 如果引擎已启动，则手动激活
            t.start()

    def start(self):
        """ 启动引擎开始仿真.
        """
        entity.Router.start(self)
        if self._starter is not None:
            self._starter(self)
        self.add_manipulator(lambda engine: self._update_cmds(), interval=1)
        for f, args in self._manipulators:
            f(*args)
        for t in self._threads:
            t.start()

    cpdef activate(self):
        """
        激活仿真
        Returns:

        """
        entity.Router.activate(self)
        self._is_activated = True

    cpdef terminate(self):
        """
        仿真结束控制器
        Returns:

        """
        self._is_terminated = True

    cpdef update(self, int delta=-1):
        # 子类重写
        pass

    cpdef activate_board(self, bint console=False, bint log=False):
        """ 激活基于tkinter库的仿真可视化界面

        Args:
            console: 是否只显示仿真控制界面
            log: 是否现实日志窗口
        """
        if self._is_activated:
            self.log_warning("引擎已启动，activate_board命令无效")
            return
        import simulation.render.board as board
        self.add_threading(board.draw, args=(console, log))


def merge_range_data(range_data):
    """ 合并范围形成包络，针对web绘图数据 """
    radar_polygons = []
    for symbol in range_data:
        assert symbol["mode"] == "Polygon"
        radar_polygons.append(geometry.Polygon(zip(symbol["x"], symbol["y"])))
    result = []
    if radar_polygons:
        polygons = unary_union(radar_polygons)
        # print(type(polygons))
        if isinstance(polygons, geometry.Polygon):
            x, y = polygons.exterior.xy
            _symbol = alg.shape.Symbol()
            _symbol["type_"] = symbol["type_"]
            _symbol["group"] = symbol["group"]
            _symbol["color"] = symbol["color"]
            _symbol["mode"] = "Polygon"
            _symbol["x"] = list(x)
            _symbol["y"] = list(y)
            result.append(_symbol)
        else:
            # xx = []
            # yy = []
            for poly in polygons:
                x, y = poly.exterior.xy
                _symbol = alg.shape.Symbol()
                _symbol["type_"] = symbol["type_"]
                _symbol["group"] = symbol["group"]
                _symbol["color"] = symbol["color"]
                _symbol["mode"] = "Polygon"
                _symbol["x"] = list(x)
                _symbol["y"] = list(y)
                result.append(_symbol)
    return result

class MyJsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return super(MyJsonEncoder, self).default(obj)


class CmdData(base.Node):
    idx = 0

    def __init__(self, engine:BaseEngine, cmd_type: str, cmd_label: str, create_time:float,
            cmd_res_name: str=None):
        CmdData.idx += 1
        self.engine = engine
        self.cmd_name = cmd_type + "_" + str(CmdData.idx)
        self.cmd_type = cmd_type
        self.cmd_label = cmd_label
        self.create_time = create_time # 生成指令时间
        self.plan_begin_time = None # 计划开始时间
        self.plan_end_time = None # 计划结束时间
        self.begin_time = None # 实际开始时间
        self.end_time = None # 实际结束时间
        self._res = None # 指令执行结果
        self.res2 = None  # 额外的反馈信息，自定义结构
        # 该指令结束时根据该名字让engine调用执行下一个指令
        self.cmd_res_name = cmd_res_name
        # 将指令加入到engine列表中
        self.engine.cmd_collections[self.cmd_name] = self 

    @property
    def res(self):
        return self._res
    
    @res.setter
    def res(self, value):
        self._res = value
        if self.cmd_res_name is not None:
            func, args = self.engine.cmd_res_name_next_fun_dct[self.cmd_res_name]
            self.engine._next(func, args=args, delay=0.001) # 延迟一个较小的时间执行，避免立即执行而陷入死循环

    def __repr__(self) -> str:
        return f"{self.cmd_name}:{self.cmd_type}:{self.cmd_label}:{self.begin_time}:{self.end_time}:{self.res}"


cdef class BaseEngine(DispatchEngine):
    """
    """

    def __init__(self, name="engine", epoch=None, flag=log.INFO, terminal=True, logtag=None, logpath=None,
                 db=None, cache=True, raise_error=enums.RaiseErrorFlag.DEBUG, redis_ip=None, redis_log=False,
                 render_config=None, checkbox_dict=None, web_ip=None, user_name='test',
                 new_thread=True, simserver=None, udp_ip=None, nats_ip=None):
        """ Simulation Engine class.

        Parameters
        ----------
        name : str
            Engine name, used as the prefix for simulation output files.
        epoch : str
            Simulation epoch (%Y-%m-%d %H:%M:%S, e.g. 2019-07-20 08:00:00).
        logtag : str
            日志路径标记，具体含义见代码
        cache: bool
            是否直接读取缓存的数据库，默认在获取db时是直接读取缓存的，因此此变量无效，暂时留着
        web_ip : str
            是否推送到web地图以及web数据面板
            可以为ip，默认端口号为50051; 也可以为ip+端口号
            如'192.168.240.12'或'192.168.240.12:50051'
        redis_ip : str
            是否推送到庚图地图, 对应于仿真脚本中的gengtu_ip
            可以为ip，默认端口号为6380; 也可以为ip+端口号
            如'192.9.200.5'或'192.9.200.5:6380'
        """
        # 生成日志存储路径
        # 如果未设置logpath路径(如果设置，必须为绝对路径)，
        # 则根据name和logtag生成日志路径，并强制要求日志路径在Mwork下(如果有日志的话)
        self.dir_path = os.path.dirname(os.path.abspath(__file__))
        self.root_path = os.path.dirname(os.path.dirname(self.dir_path))
        if logpath is None:
            time_tag = time.strftime("%Y-%m-%d-%H-%M-%S") + "-" + str(np.random.randint(10000, 99999))
            if isinstance(name, str) and ("@" in name) and len(name.split("@")) == 4:
                # 大样本仿真 engine_name 命名规则暂定如下 {token}@{sim_mode}@{该模式参数信息}@{time_tag}
                # logpath = os.path.join(os.path.dirname(self.root_path), "Mwork", name, "数据", "log", logtag, time_tag)
                # 暂不产生日志路径
                pass
            elif name == "engine":
                pass
            elif logtag is not None:
                # 正常生成日志路径
                assert name  # 必不为空字符串
                assert isinstance(logtag, str)
                time_tag = time.strftime("%Y-%m-%d-%H-%M-%S") + "-" + str(np.random.randint(10000, 99999))
                logpath = os.path.join(os.path.dirname(self.root_path), "Mwork", name, "数据", "log", logtag, time_tag)

        if db is None:
            db = database.DataBase()  # 在database中已经根据缓存方式获取了数据库，如果需要用新的数据，手动删掉xx.pkl即可

        super().__init__(name, epoch, flag, terminal, logpath, db, raise_error)

        self.sim_config = database.load_sim_config()  # 仿真参数配置字典
        if render_config is None or len(render_config) == 0:
            self.render_config = database.load_render_config()  # 可视化参数配置字典
        else:
            self.render_config = render_config
        self.symbol_dict = database.load_symbol_config()  # 可视化符号配置字典
        if checkbox_dict is None or len(checkbox_dict) == 0:
            self.checkbox_dict = database.load_checkbox_config()  # 控制面板 checkbox配置字典
        else:
            self.checkbox_dict = checkbox_dict

        self._is_started = False
        self._updating = True
        self._register_class()
        self.env_effects = []  # 环境效应，如尾流等
        self._proj = None  # 投影变换句柄
        self.update_proj()  # 更新投影函数
        # self.special_effects = set() #可视化的特效效果，如爆炸等
        self._units = base.Bag()  # 加载到引擎上的units
        self._name_units = {}  # 为避免unit名字重复而寄存的字典，并可基于名字快速查询
        self._networks = []  # 加载到引擎上的  通信链路
        self.ids = defaultdict(list)  # 为避免组件命名重复的寄存变量
        self.lock = Lock()  # 线程锁
        self.redis_conn = None  # Redis接口
        self.is_redis_used = False  # 是否使用redis连接庚图可视化系统
        self.is_redis_log = redis_log  # 是否记录发送到redis的信息记录
        self._redis_created_ids = set()  # 记录所有生成的id, 庚图debug使用
        self._redis_destroyed_ids = set()  # 记录所有销毁的id, 庚图debug使用
        self.first_found_time_dict = dict()  # 记录所有目标被第一次 探测到的时间
        self.strikechain_id_set = set()  # 记录所有已经返回给客户端的打击链ID
        # self.links_effect = special_effect.LinksEffect(self)
        self.post_web_statistic_single_data = None  # 用于web端展示的单次仿真统计数据
        self.web_client = None  # push data to mclient from simmserver
        self.user_name = user_name  # 用户名,主动向web_server推送时用于控制显示在哪个账户下
        self.logpath = logpath      # 日志地址，
        self.web_show = True        # 是否上显， False暂定为黑屏连地图都不显
        self.push_data = {}         # 记录引擎仿真过程中的数据，结束时推送给server_client
        self.terminate_result = None # 记录引擎仿真过程中的数据，结束时推送给server_client
        # ----指令相关----
        self._unexecuted_cmds_lock = Lock() # 执行、更新指令线程使用锁
        self._unexecuted_cmds_id = base.Heap()  # 未执行的指令id队列
        self._unexecuted_id_2_cmd = {}  # 未执行的指令id到指令的映射
        self._cmd_id_name_dct = {}  # 指令id与我方指令的唯一命名的对应关系
        self._exception_event = {}  # 指令执行失败记录
        self.events = [] # 记录所有 _send_event 发送的事件 

        self.shape_marker_data = []
        self.simserver = simserver
        if web_ip:
            assert isinstance(web_ip, str)
            self.use_web = True  # 用于记录状态
            if not ":" in web_ip:
                web_ip = web_ip + ":50051"
            channel = grpc.insecure_channel(web_ip, options=GRPC_OPTIONS)
            self.web_client = simserver_pb2_grpc.GreeterStub(channel=channel)
            self.web_ip = web_ip
            self.new_thread = new_thread
            self._activate_web_render(new_thread=self.new_thread)
        else:
            self.use_web = False
            host_name = socket.gethostname()
            self.web_ip = socket.gethostbyname(host_name)

        if redis_ip:
            assert isinstance(redis_ip, str)
            if ":" in redis_ip:
                host, port = redis_ip.split(":")
            else:
                host, port = redis_ip, "6380"
            self.activate_redis(host=host, port=int(port))
        if udp_ip:
            assert isinstance(udp_ip, str)
            if ":" in udp_ip:
                host, port = udp_ip.split(":")
            else:
                host, port = udp_ip, "20840"
            # 定义信息单元序号，0~255循环使用
            self.sequence_number = 0
            # 定义实体code 及 实体与ID的映射关系
            self.entity_code = 1
            self.entity_name_to_code_dict = dict()
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.bind(("172.16.1.2", 20840))
            ttl = struct.pack('b', 16)
            self.udp_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
            # self.udp_socket.connect(("8.8.8.8", 80))
            self.udp_src_ip = self.udp_socket.getsockname()[0]
            self.udp_dst_ip = host
            self.activate_udp(host=host, port=int(port))

        #### 新版render需要用的的属性
        self.render_data = {}
        self.render_index = 0  # 为支持庚图生成唯一的id
        self.cmd_collections = OrderedDict()
        self.cmd_res_name_next_fun_dct = OrderedDict() # 用以注册指令结束时对应执行的事件
        self._command_msg_list = list()  # 用于 web 端事件显示

        # 分支推演使用
        self._trigger_handler_init()

        if nats_ip:
            assert isinstance(nats_ip, str), f"参数nats_ip格式只能是字符串，{type(nats_ip)}"
            # 记录Nats配置
            self.nats_ip = nats_ip
            if ":" in nats_ip:
                host, port = nats_ip.split(":")
            else:
                host, port = nats_ip, "4222"
            self.nats_client = None
            self.activate_nats(host=host, port=int(port))
            self.constellations = {}

    # 保存
    def __getstate__(self):
        state = {
            'name': self.name,
            '_is_started': self._is_started,
            '_is_activated': self._is_activated,
            '_cron': self._cron,  #
            '_ratio': self._ratio,
            '_epoch': self._epoch,
            '_terminater': self._terminater,
            'user_name': self.user_name,
            '_ratio_assess': self._ratio_assess,
            '_ratio_assess_real_tick': self._ratio_assess_real_tick,
            '_ratio_assess_sim_tick': self._ratio_assess_sim_tick,
            '_is_pause': self._is_pause,
            '_is_terminated': self._is_terminated,
            '_is_probe': self._is_probe,
            '_step_end_tick': self._step_end_tick,
            '_end_tick': self._end_tick,
            '_units': self._units,
            '_name_units': self._name_units,
            '_networks': self._networks,
            '_tick': self._tick,
            '_begin_sim_tick': self._begin_sim_tick,
            '_begin_real_tick': self._begin_real_tick,
            '_tracer': self._tracer,
            'sim_config': self.sim_config,
            'env': self.env,
            'render_data': self.render_data,
            'render_index': self.render_index,
            'cmd_collections': self.cmd_collections,
            'render_config': self.render_config,
            'is_redis_used': self.is_redis_used,
            'is_redis_log': self.is_redis_log,
            '_isactive': self._isactive,
            'engine': self.engine,
            '_message_handlers': self._message_handlers,
            'use_web': self.use_web,
            'web_ip': self.web_ip,
            'web_show': self.web_show,
            'lock': self.lock,
            '_proj': self._proj,
            'strikechain_list': self.strikechain_list,
            'strikechain_id_set': self.strikechain_id_set,
            'first_found_time_dict': self.first_found_time_dict,
            'db': self.db,
            'symbol_dict': self.symbol_dict,
            'ids': self.ids,
            'shape_marker_data': self.shape_marker_data,
            '_branch_trigger_handler': self._branch_trigger_handler,
            '_branch_answer_dict': self._branch_answer_dict,
            '_branch_trigger_dict': self._branch_trigger_dict,
            'terminate_result': self.terminate_result,
            'post_web_statistic_single_data': self.post_web_statistic_single_data,
            'cache': self.cache,
            'push_data': self.push_data,
            '_command_msg_list': self._command_msg_list,
            '_updating': self._updating,
            '_unexecuted_cmds_id': self._unexecuted_cmds_id,
            'weights_map': self.weights_map,
            '_exception_event': self._exception_event,
            '_unexecuted_id_2_cmd': self._unexecuted_id_2_cmd,
            '_cmd_id_name_dct': self._cmd_id_name_dct,
            '_manipulators': self._manipulators,
            '_build_times': self._build_times
        }
        if self.use_web:
            state.update({
                # 'web_client': self.web_client,
                'new_thread': self.new_thread
            })
        return state

    # 加载
    def __setstate__(self, state):
        self.name = state['name']
        self._is_started = state['_is_started']
        self._is_activated = state['_is_activated']
        self._cron = state['_cron']
        self._ratio = state['_ratio']
        self._epoch = state['_epoch']
        self._terminater = state['_terminater']
        self.user_name = state['user_name']
        self._ratio_assess = state['_ratio_assess']
        self._ratio_assess_real_tick = state['_ratio_assess_real_tick']
        self._ratio_assess_sim_tick = state['_ratio_assess_sim_tick']
        self._is_pause = state['_is_pause']
        self._is_terminated = state['_is_terminated']
        self._is_probe = state['_is_probe']
        self._step_end_tick = state['_step_end_tick']
        self._end_tick = state['_end_tick']
        self._units = state['_units']
        self._name_units = state['_name_units']
        self._networks = state['_networks']
        self._tick = state['_tick']
        self._begin_sim_tick = state['_begin_sim_tick']
        self._begin_real_tick = state['_begin_real_tick']
        self._tracer = state['_tracer']
        self.sim_config = state['sim_config']
        self.env = state['env']
        self.render_data = state['render_data']
        self.render_index = state['render_index']
        self.cmd_collections = state['cmd_collections']
        self.cmd_res_name_next_fun_dct = state['cmd_res_name_next_fun_dct']
        self.render_config = state['render_config']
        self.is_redis_used = state['is_redis_used']
        self.is_redis_log = state['is_redis_log']
        self._isactive = state['_isactive']
        self.engine = state['engine']
        self._message_handlers = state['_message_handlers']
        self.use_web = state['use_web']
        self.web_ip = state['web_ip']
        self.web_show = state['web_show']
        self.lock = state['lock']
        self._proj = state['_proj']
        self.strikechain_list = state['strikechain_list']
        self.strikechain_id_set = state['strikechain_id_set']
        self.first_found_time_dict = state['first_found_time_dict']
        self.db = state['db']
        self.symbol_dict = state['symbol_dict']
        self.ids = state['ids']
        self.shape_marker_data = state['shape_marker_data']
        self._branch_trigger_handler = state['_branch_trigger_handler']
        self._branch_answer_dict = state['_branch_answer_dict']
        self._branch_trigger_dict = state['_branch_trigger_dict']
        self.terminate_result = state['terminate_result']
        self.post_web_statistic_single_data = state['post_web_statistic_single_data']
        self.cache = state['cache']
        self.push_data = state['push_data']
        self._command_msg_list = state['_command_msg_list']
        self._updating = state['_updating']
        self._unexecuted_cmds_id = state['_unexecuted_cmds_id']
        self.weights_map = state['weights_map']
        self._exception_event = state['_exception_event']
        self._unexecuted_id_2_cmd = state['_unexecuted_id_2_cmd']
        self._cmd_id_name_dct = state['_cmd_id_name_dct']
        self._manipulators = state['_manipulators']
        self._build_times = state['_build_times']
        # self._manipulators = []
        # print('load', self.time)
        self.set_ratio(self._ratio)
        if self.use_web:
            self._threads = []  # 当前 _threads 中只有推送 web 信息一个线程，使用直接初始化的方式，如果有其他线程此处会报错
            self.new_thread = state['new_thread']
            channel = grpc.insecure_channel(self.web_ip, options=GRPC_OPTIONS)
            self.web_client = simserver_pb2_grpc.GreeterStub(channel=channel)
            self._activate_web_render(new_thread=self.new_thread)

    cpdef _register_class(self):
        root = base.Node
        q = Queue()
        q.put(root)
        
        while not q.empty():
            node = q.get()
            CLASS[node.__name__] = node
            for child in node.__subclasses__():
                q.put(child)

    cpdef _clear_class(self):
        CLASS.clear()

    cpdef save(self, str path=None):
        '''
        load 用法
        import dill
        engine = dill.loads(checkpoint_bytes)
        engine...

        注: dill.load_module 会读取预先保存的内存中解释器的状态，故可以不初始化直接使用 engine 变量，但也会读取其他出现的变量
        '''
        global simserver_pb2, simserver_pb2_grpc
        del simserver_pb2, simserver_pb2_grpc
        checkpoint_bytes = dill.dumps(self)
        import simserver_pb2, simserver_pb2_grpc
        if path:
            if os.path.exists(path):
                with open(path, 'wb') as f:
                    f.write(self.checkpoint_bytes)
            else:
                self.log_warning(f'engine 保存路径 {path} 不存在')
        print(f'引擎 {self.name} 保存成功')
        return checkpoint_bytes
 
    cpdef list actives(self):
        """

        Returns:加载到UNIT上的所有组件

        """
        return [u for u in self._units if u.isactive]

    cpdef list networks(self):
        """

        Returns:加载导引擎上的  链路

        """
        return self._networks

    cpdef unit(self, int id):
        """ 根据id查找engine上指定的unit

        复杂度: O(log(n))

        Returns:
            unit or None
        """
        return self._units.find(id)

    cpdef list units(self, fun=None):
        """ 查询engine上指定的unit

        返回符合指定过滤函数filtering function的unit列表或[].
        复杂度: O(n)
        """
        return list(filter(fun, self._units))
        # if fun is None:
        #     return self._units.tolist()
        # if hasattr(fun, "__call__"):
        #     res = [e for e in self._units if fun(e)]
        #     return res
        # assert False, "invalid fun for units search"

    cpdef units_add(self, unit):
        """
        添加组件
        Args:
            unit: 组件

        Returns:

        """
        self._units.add(unit)

    cpdef update_proj(self):
        """ 生成/更新投影变换句柄 """
        if self._is_activated:
            self.log_warning("引擎激活后不能更新投影变化句柄；忽略")
            return
        lon = self.sim_config["lon"]
        lat = self.sim_config["lat"]
        self._proj = pyproj.Proj(proj='tmerc', lon_0=lon, lat_0=lat, preserve_units=False)

    def log_command(self, msg, *args, **kwargs):
        """ 自定义的COMMAND级别的日志记录接口

        记录与指挥关系相关的
        """
        log_data = log.LogData(log.COMMAND, msg, args, kwargs)
        level, msg, args, kwargs = log_data.get_print_param()
        self._tracer.log(level, msg, *args, **kwargs)
        show_msg = log_data.get_msystem_web_show_param()
        self._save_command_msg(show_msg)
        if self.is_redis_used:
            self.push_top_box_msg(show_msg)
            
    def log_physics(self, msg, *args, **kwargs):
        """ 自定义的PHYSICS级别的日志记录接口 """
        self._tracer.log(log.PHYSICS, msg, *args, **kwargs)

    def log_sensor(self, msg, *args, **kwargs):
        """ 自定义的SENSOR级别的日志记录接口 """
        self._tracer.log(log.SENSOR, msg, *args, **kwargs)

    def log_decision(self, msg, *args, **kwargs):
        """ 自定义的DECISION级别的日志记录接口 """
        self._tracer.log(log.DECISION, msg, *args, **kwargs)

    cpdef set_ratio(self, ratio):
        """
        调节倍率
        Args:
            ratio: 倍率值

        Returns:

        """
        DispatchEngine.set_ratio(self, ratio)
        event = {
            "target_type": "sim_rate_set",
            "event_type": "create",
            "event_property": {
                "sim_rate": ratio
            }
        }
        self.push_render_event(event)

    cpdef assemble(self):
        """ 配置Unit以及下属组件的属性参数
        """
        for net in self._networks:
            net.assemble()
        for unit in self._units:
            unit.assemble()
        self.log_debug("engine.assemble")

    cpdef implement(self):
        """ 配置Unit以及下属组件的状态动作、转移条件以及消息处理的
        """
        for net in self._networks:
            net.implement()
        for unit in self._units:
            unit.implement()
        self.log_debug("engine.implement")

    cpdef check(self):
        """ 检查引擎以及所属Units和Components是否配置正常
        """
        for net in self._networks:
            net.check()
        for unit in self._units:
            unit.check()
        self.log_debug("engine.check")

    cpdef start(self):
        """ 启动引擎开始仿真.
        """
        for net in self._networks:
            net.start()
        for unit in self._units:
            unit.start()
        self._is_started = True
        DispatchEngine.start(self)

    cpdef kill(self):
        # 先设置结束时的数据，再结束
        DispatchEngine.kill(self)
        self._clear_class()
        if self.simserver is not None:
            self.simserver.heartbeat()

    cpdef register_statistic_func(self, func):
        if self.web_client is not None:
            self.web_client.control('xxx')

    # 和 pause 区别，会使程序停止，便于单机进行指令控制
    cpdef stop_update(self):
        """
        停止更新
        Returns:

        """
        self._updating = False

    cpdef restart_update(self):
        """
        重新开始更新
        Returns:

        """
        self._updating = True
    
    property updating:
        def __get__(self):
            return self._updating

    cpdef update(self, int delta=-1):
        """ Advance the engine a specified simulation time. 仿真更新函数

        Parameters
        ----------
        delta : int (s)

        Raises
        ------
        RuntimeError
            Unknown message occurs in the engine.
        """
        cdef double when
        cdef cmsg.MESSAGE message
        if delta > 0:
            self._step_end_tick = self._tick + int(delta * 1000)
        else:
            self._step_end_tick = np.inf
        try:
            # import pdb; pdb.set_trace()
            while self._cron:

                # 控制程序停止接收指令
                if not self._updating:
                    break

                # 优先检查触发器
                self._trigger_handler_process()

                when, message = self._cron.peek()
                if self._ratio == "SYSTEM":
                    self._upper_tick = np.inf
                else:
                    self._upper_tick = self._begin_sim_tick + (
                            time.time() * 1000.0 - self._begin_real_tick) * self._ratio
                if when <= self._upper_tick:
                    # 如果不大于在本次加速仿真内的仿真时间上限,则执行
                    # 评估真实的仿真速率
                    if time.time() * 1000.0 - self._ratio_assess_real_tick > 1000:
                        self._ratio_assess = (when - self._ratio_assess_sim_tick) / (
                                time.time() * 1000.0 - self._ratio_assess_real_tick)
                        self._ratio_assess_real_tick = time.time() * 1000.0
                        self._ratio_assess_sim_tick = when
                        # print(f"真实仿真速率估计:{self._ratio_assess:.2f}")

                    # 判断是否结束
                    if self._is_terminated:
                        raise SimStop  # 结束整个仿真

                    # 判断是否暂停
                    while self._is_pause:
                        time.sleep(1)
                        # 暂停时也可判断是否结束
                        if self._is_terminated:
                            raise SimStop  # 结束整个仿真

                    # 判断是否暂停并进行干预
                    if self._is_probe:
                        self._is_probe = False
                        print("开始利用pdb进行干预操作")
                        engine = self
                        import pdb;
                        pdb.set_trace()

                    # 判断是否超出本步更新时间上限
                    if when > self._step_end_tick:
                        self._tick = self._step_end_tick
                        break  # 推进到本步结束时间，并停止本步更新

                    # 判断是否超出仿真时间上限
                    if when > self._end_tick:
                        raise SimStop  # 结束整个仿真

                    # 执行更新
                    when, message = self._cron.pop()
                    if when < self._tick:
                        import pdb;
                        pdb.set_trace()
                    if when > self._tick:
                        self._tick = when
                        # 推送仿真时间
                        if self.is_redis_used or self.is_redis_log:
                            event = {"target_type": "sim_datetime_set", "event_type": "update",
                                     "event_property": {"sim_datetime": self.ymdhms}}
                            self.push_render_event(event)
                    obj = message.head.recv
                    # 判断是何种任务类型：状态更新任务、函数更新任务、消息处理任务
                    if isinstance(message.body, cmsg.STATE):
                        # 执行状态动作并转移转态(可能)
                        # 只有当前状态和消息状态一致，才按消息状态触发状态更新
                        if obj.state == message.body.state:
                            obj.state_update()
                    elif isinstance(message.body, cmsg.FUNC):
                        # 执行指定的函数/shipmotor2_tests.py
                        if not obj.isactive:
                            self.log_debug("Disabled %s will not exec func", self)
                        else:
                            self.log_debug("FuncExec %s exec func[%s]", self, message.body.func.__name__)
                            if message.body.args is None:
                                message.body.func()
                            else:
                                message.body.func(*message.body.args)
                    else:
                        # 处理消息
                        obj.message_handle(message)
                else:
                    # 否则，暂停一会儿
                    time.sleep((when - self._upper_tick) / 1000.0 / self._ratio)
        except SimStop:
            if self._terminater is not None:
                self._terminater(self)  # 在仿真结束前执行该函数
            self.kill()
            print(f"{self.name} simulation end at {self._tick} ticks!")
            # 将庚图的状态重置，然后可以自动接收下一次仿真的信息
            if self.is_redis_used or self.is_redis_log:
                event = {"target_type": "map_control", "event_type": "create",
                         "event_property": {"map_control": "reset"}}
                self.push_render_event(event)
                print("推送庚图状态重置消息")

    # -------------可视化接口----------------
    def _activate_web_render(self, interval=0.2, new_thread=True):
        """ 激活基于百度地图的仿真可视化界面

        Args:
            interval: 推送数据周期
        """
        # 圆、扇形等面状显示元素与兵力实体位置脱节的情况，并且卡顿感严重；如果new_thread为False虽然会放慢仿真速率，脱节和卡顿的情况可以消除。
        if new_thread:
            if self._is_activated:
                self.log_warning("出现该警告可能是引擎启动重复执行激活web推送或者引擎load之后执行激活web推送，当前尚未区分这两种情况")
                # return
            t = threading.Thread(target=self._post_simulation_info, args=(interval,), daemon=True)
            self._threads.append(t)
            if self._is_activated:  # 如果引擎已启动，则手动激活
                t.start()
        # 保存暂不支持该情况
        else:
            # assert False, 'new_thread 参数当前只能为 True'
            # 需要支持new_thread为False的情况，当仿真速度非常大的时候，如果new_thread为True，则可能会出现
            # 圆、扇形等面状显示元素与兵力实体位置脱节的情况，并且卡顿感严重；如果new_thread为False虽然会放慢仿真速率，脱节和卡顿的情况可以消除。
            self.add_manipulator(lambda engine: self._post_simulation_info_single(), interval=10)

    cpdef activate_redis(self, str host='129.0.3.145', int port=6380):
        """ 激活redis客户端以实现与庚图可视化系统的连接
        """
        if len(self._units) > 0:
            assert RuntimeError("引擎中已存在实体，必须在引擎初始化后立即启动")
        self._render_events = []
        if self.redis_conn is not None:
            self.log_warning("redis接口服务已经启动，忽略重复启动")
            return
        self.redis_conn = redis.StrictRedis(host=host, port=port, decode_responses=True)
        try:
            self.redis_conn.get('1')
            self.redis_rc = self.redis_conn.pubsub()
            self.redis_rc.subscribe('redis')
            self.is_redis_used = True
            print(f'与庚图的连接成功')
            # 设置海况
            event = {"target_type": "sea_state", "event_type": "create", "event_property": {"sea_level": 7}}  # 最高七级
            self.push_render_event(event)
            # 推送仿真时间
            event = {"target_type": "sim_datetime_set", "event_type": "create",
                     "event_property": {"sim_datetime": self.ymdhms}}
            self.push_render_event(event)
        except:
            self.is_redis_used = False
            print(f'与庚图的连接失败')

    cpdef activate_udp(self, host, port, float interval=1, bint new_thread=True):
        """
        激活udp客户端以实现与C++系统的连接
        Args:
            host: UPD IP地址
            port: 端口号
            interval: 数据发送周期
            new_thread: 是否开启新线程
        Returns:

        """
        if new_thread:
            if self._is_activated:
                self.log_warning("出现该警告可能是引擎启动重复执行激活CPP推送或者引擎load之后执行激活CPP推送，当前尚未区分这两种情况")
                # return
            t = threading.Thread(target=self._post_simulation_info_to_cpp, args=(host, port, interval,), daemon=True)
            self._threads.append(t)
            if self._is_activated:  # 如果引擎已启动，则手动激活
                t.start()
        # 保存暂不支持该情况
        else:
            assert False, 'new_thread 参数当前只能为 True'

    cpdef activate_nats(self, host, port, bint new_thread=True):
        """
            激活Nats客户端
        Args:
            host: Nats服务器 IP地址
            port: Nats服务器 端口号
            new_thread: 是否开启新线程
        Returns:
        """
        self._gen_nats_client(host, port)

    # def short_to_chinese(self, name, return_None=True):
    #     if return_None:
    #         return self._short_to_chinese_d.get(name, None)
    #     else:
    #         assert name in self._short_to_chinese_d, print(name)
    #         return self._short_to_chinese_d[name]

    cpdef push_render_event(self, event):
        """
        可视化事件推送
        Args:
            event: 时间名称(由dict构成)

        Returns:

        """
        if (not self.is_redis_used) and (not self.is_redis_log): return
        if event["target_type"] not in ["sea_state", "sim_datetime_set", "sim_rate_set", "event", "phase",
                                        "range_merge", "map_control", "highlight"]:
            # 判断推送的id是否正确
            # 即是否存在重复创建id
            # 是否存在更新已删除的id等
            # if event["target_type"] == "wave":
            #     print(event)
            if event["event_type"] == "create":
                if event["target_type"] == "entity":
                    entity_id = event["event_property"]["id"]
                    if entity_id not in self._redis_created_ids:
                        self._redis_created_ids.add(entity_id)
                    else:
                        import pdb;
                        pdb.set_trace()
                else:
                    id_str = event["event_property"][event["target_type"] + "_id"]
                    if id_str not in self._redis_created_ids:
                        self._redis_created_ids.add(id_str)
                    else:
                        import pdb;
                        pdb.set_trace()
                    if event["target_type"] == "link":
                        entity_id1 = event["event_property"]["entity_id1"]
                        if entity_id1 not in self._redis_created_ids:
                            import pdb;
                            pdb.set_trace()
                        entity_id2 = event["event_property"]["entity_id2"]
                        if entity_id2 not in self._redis_created_ids:
                            import pdb;
                            pdb.set_trace()
                    else:
                        entity_id = event["event_property"]["entity_id"]
                        # if entity_id not in self._redis_created_ids:
                        #    import pdb; pdb.set_trace()

            elif event["event_type"] == "destroy":
                if event["target_type"] == "entity":
                    _id = event["event_property"]["id"]
                else:
                    _id = event["event_property"][event["target_type"] + "_id"]
                if _id not in self._redis_created_ids or _id in self._redis_destroyed_ids:
                    import pdb;
                    pdb.set_trace()
                else:
                    self._redis_destroyed_ids.add(_id)

            elif event["event_type"] == "update":
                if event["target_type"] == "entity":
                    _id = event["event_property"]["id"]
                else:
                    _id = event["event_property"][event["target_type"] + "_id"]
                if _id not in self._redis_created_ids or _id in self._redis_destroyed_ids:
                    import pdb;
                    pdb.set_trace()
                else:
                    pass

        msg = json.dumps(event, cls=MyJsonEncoder)
        if self.is_redis_log:
            self._tracer.log(log.REDIS, msg)

        if self.is_redis_used:
            self.redis_conn.publish('entity', msg)
            if event['target_type'] == 'range_merge':
                print(msg)

    cpdef push_render_events(self):
        """
        推送多个事件
        Returns:

        """
        if not self._render_events:
            return
        msg = json.dumps(self._render_events, cls=MyJsonEncoder)
        self._render_events = []
        if self.is_redis_used:
            self.redis_conn.publish('entity', msg)

    cpdef push_top_box_msg(self, str msg):
        """
        推送地图box信息
        Args:
            msg: 信息（str）

        Returns:

        """
        event = {
            "target_type": "event",
            "event_type": "create",
            "event_property": {
                "datetime": self.ymdhms,
                "text": msg
            }
        }
        if self.is_redis_log:
            self._tracer.log(log.REDIS_MSG, self.ymdhms + " " + msg)
        self.push_render_event(event)

    cpdef push_phases_msg(self, str curr_phase, list all_phases):
        """
        推送阶段信息
        Args:
            curr_phase:当前阶段(str)
            all_phases:所有阶段(list)

        Returns:

        """
        assert curr_phase in all_phases, print(f'当前阶段 {curr_phase} 不在预设阶段 {all_phases} 中')
        event = {
            "target_type": "phase",
            "event_type": "create",
            "event_property": {
                "all_phases": all_phases,
                "curr_phase": curr_phase
            }
        }
        if self.is_redis_log:
            self._tracer.log(log.REDIS_MSG, self.ymdhms + " 当前阶段:" + curr_phase)
        self.push_render_event(event)

    cpdef get_entity_symbol_id(self, entity):
        """ 根据unit对象获取庚图显示的符号编号
        """
        if entity.name in self.symbol_dict:
            return self.symbol_dict[entity.name]
        elif f"{entity.group}_{entity.model}" in self.symbol_dict:
            return self.symbol_dict[f"{entity.group}_{entity.model}"]
        elif entity.model in self.symbol_dict:
            return self.symbol_dict[entity.model]
        elif f"{entity.group}_{entity.__class__.__name__}" in self.symbol_dict:
            return self.symbol_dict[f"{entity.group}_{entity.__class__.__name__}"]
        elif entity.__class__.__name__ in self.symbol_dict:
            return self.symbol_dict[entity.__class__.__name__]
        else:
            return -1  # 默认符号

    # -------------分支推演流程----------------
    def _trigger_handler_init(self):
        """初始化分支推演模块"""
        self._branch_trigger_handler = BranchTriggerHandler(self)
        self._branch_answer_dict = {}           # 记录所有分支处理方案
        self._branch_trigger_dict = {}          # 记录所有分支触发器
        self.checkpoint_bytes = b''             # 记录本次结束是因为到分支点结束还是自然结束
        self.triggered_name = ''                # 记录仿真结束时本次触发的 trigger 的函数名

    def _trigger_handler_process(self):
        """分支推演触发器"""
        if self._branch_trigger_handler is None:
            return
        self._branch_trigger_handler.check()

    def reset_trigger_handler(self, engine_name, branch_trigger_names:list=[], branch_answer_name:str=None):
        '''进入下一分支时生成新的推演模块'''
        if self._branch_trigger_handler is not None:    
            self._branch_trigger_handler.clear()
            for trigger_name in branch_trigger_names:
                self._branch_trigger_handler.activate(trigger_name)
        self.checkpoint_bytes = b''
        self.triggered_name = ''
        self.name = engine_name
        self._answer_process(branch_answer_name)

    def add_branch_trigger(self, func):
        """添加分支触发器"""
        assert func.__name__ not in self._branch_trigger_dict, '加载同名分支触发器'
        self._branch_trigger_dict[func.__name__] = func

    def add_branch_triggers(self, funcs: list):
        """添加分支触发器"""
        for func in funcs:
            self.add_branch_trigger(func)

    def add_branch_answer(self, func):
        """添加分支推演方案"""
        assert func.__name__ not in self._branch_answer_dict, '加载同名分支推演方案'
        self._branch_answer_dict[func.__name__] = func

    def add_branch_answers(self, funcs: list):
        """添加分支推演方案"""
        for func in funcs:
            self.add_branch_answer(func)

    def _answer_process(self, branch_answer_name: str):
        """执行分支推演方案"""
        if not branch_answer_name:
            return
        self._branch_answer_dict[branch_answer_name](self)

    def branch_trigger_by_name(self, branch_trigger_name):
        """选择分支触发器"""
        return self._branch_trigger_dict.get(branch_trigger_name, None)

    # -------------通用计算接口----------------
    cpdef xy2lnglat(self, x, y):
        """
        通过x、y计算经纬度
        Args:
            x:
            y:

        Returns:

        """
        lng, lat = self._proj(x, y, inverse=True)
        return lng, lat

    cpdef lnglat2xy(self, lng, lat):
        """
        通过经纬度获取x、y值
        Args:
            lng: 经度
            lat: 纬度

        Returns:

        """
        x, y = self._proj(lng, lat, inverse=False)
        return x, y

    cpdef get_xy(self, a, b, str coordinate_system="Geodetic"):
        """
        获取x、y值
        Args:
            a:
            b:
            coordinate_system: Geodetic为经纬度模式

        Returns: x、y

        """
        assert coordinate_system in ["Cartesian", "Geodetic"]
        if coordinate_system == "Cartesian":
            x, y = a, b
        else:
            if isinstance(a, (tuple, list)):
                lng = a[0] + a[1] / 60.0 + a[2] / 3600.0
            else:
                lng = a
            if isinstance(b, (tuple, list)):
                lat = b[0] + b[1] / 60.0 + b[2] / 3600.0
            else:
                lat = b
            x, y = self.engine.lnglat2xy(lng, lat)
        return x, y

    cpdef get_waypoints(self, list xyz_points=None, list xy_points=None, list lnglat_points=None, height=0):
        """
        获取路径点
        Args:
            xyz_points: xyz的路径点(list)
            xy_points: xy的路径点(list)
            lnglat_points: 路径点(list)
            height: 高度

        Returns: 路径点数组

        """
        if xyz_points is not None:
            return np.array(xyz_points, dtype=float)
        elif xy_points is not None:
            waypoints = []
            for point in xy_points:
                _point = list(point)
                _point.append(height)
                waypoints.append(_point)
            return np.array(waypoints, dtype=float)
        elif lnglat_points is not None:
            waypoints = []
            # lmc新增:height支持传入列表
            for i, point in enumerate(lnglat_points):
                _point = list(point)
                x, y = self.lnglat2xy(*_point)
                if not isinstance(height, (int, float)):
                    height = height[i]
                waypoints.append([x, y, height])
            return np.array(waypoints, dtype=float)
        else:
            return None

    # --------------可视化接口-----------------
    cpdef float sim_interval(self, float real_interval=1):
        """ 返回现实时间间隔对应的仿真时间间隔

        单位均为s
        """
        t = real_interval * self._ratio_assess
        # 原来为 t <= 0， 修改因为会出现相邻的事件真实事件间隔大于1s导致 t>0 且 t < 1e-3
        # 仿真系统的步长最小为1ms

        if t <= 1e-3:
            t = 1
        return t

    cpdef next_render_fun(self, str name, str func, args=None, delay=None, delay_ms=None):
        """
        下一条可视化功能
        Args:
            name: 名称
            func: 功能
            args: 信息
            delay: 推进时间
            delay_ms:

        Returns:

        """
        if delay is not None and delay_ms is not None:
            raise RuntimeError("only delay or delay_ms")
        if delay is None and delay_ms is None:
            raise RuntimeError("only delay or delay_ms")
        if delay is None:
            assert delay_ms >= 0, "negative delay_ms time"
            assert isinstance(delay_ms, int)
        else:
            assert delay >= 0, "negative delay time"
            delay_ms = int(delay * 1000)
        if delay_ms == 0:
            # raise RuntimeError("delay:{} should > 0".format(delay))
            # 如果时延为0，则瞬时立即处理
            f = getattr(CLASS[self.render_data[name].class_], func)
            if args is None:
                f(self, name)
            else:
                f(self, name, *args)
        else:
            head = cmsg.HEAD(self, self, self.tick)
            body = cmsg.EventNextFun(name, func, args)
            message = cmsg.MESSAGE(head, body)
            when = self.tick + delay_ms
            self._cron.push(when, message)
            self.log_debug("FuncDispatch %s will exec func[%s] when: %s",
                self, message.body.func, when)

    cpdef message_handle(self, cmsg.MESSAGE message):
        """ 处理消息
        消息包括消息头、消息体以及消息内容
        """
        if not self.isactive:
            self.engine.log_debug("Inactive %s cannot handle message %s" % (self, message))
            return
        mcls = message.body.__class__.__name__
        assert mcls == "EventNextFun"
        name = message.body.name
        func = message.body.func
        args = message.body.args
        if name not in self.render_data:  # 已经死了且被剔除了
            return
        if not self.render_data[name].isactive:
            return
        f = getattr(CLASS[self.render_data[name].class_], func)
        if args is None:
            f(self, name)
        else:
            f(self, name, *args)

    # -------------触发器接口----------------
    def set_timer_triger(self, func, args=None, time=-1, delay=-1):
        """
        Args:
            func: 函数对象，代表要触发执行的动作
            args: 函数对象的参数列表
            time: 触发动作的时间(s)
            delay: 触发动作时间距设置触发器的延迟时间(s)
            interval: 首次触发之后后续周期性执行的时间间隔(s)
        """
        if time >= 0:
            _delay = time - self._tick / 1000.0
            if _delay >= 0:
                self._next(func, args, delay=_delay)
            else:
                self.log_warning("时间小于当前仿真时间，设置无效")
                return
        elif delay >= 0:
            self._next(func, args, delay=delay)
        else:
            self.log_warning("设置无效")

    def set_cmd_res_triger(self, cmd_res_name:str, func, args=None):
        """
        Args:
            cmd_res_name: 上一个指令的结束标识
            func: 函数对象，代表要触发执行的动作
            args: 函数对象的参数列表
        """
        self.cmd_res_name_next_fun_dct[cmd_res_name] = (func, args)

    #-------------仿真实体生成接口----------------
    def gen_platform(self, name, model, group, pos, speed, course, height=0, coordinate_system="Cartesian", ptype=None, country=None):
        # import pdb;pdb.set_trace()
        try:
            model_dct = self.db[model]
            cls_ = CLASS[model_dct["class"]]
        except:
            import pdb; pdb.set_trace()
        p = cls_(self, name, model, group, ptype, country)
        v = alg.drive.speed2vel(speed, course)
        if isinstance(pos, list):
            coords = pos + [height]
        elif isinstance(pos, np.ndarray):
            coords = np.r_[pos, height]
        else:
            raise RuntimeError(f"pos的类型{type(pos)}不正确")
        p.set_move_param(coords, v, coordinate_system=coordinate_system)
        if self._is_started: # 如果引擎已启动start，则手动激活
            p.activate()
        return p

    def gen_platforms(self, names, models, group, pos, speed, course, height=0, coordinate_system="Cartesian",
                      formation=None):
        """ 按指定队形生成兵力

        Args:
            names (_type_): _description_
            models (_type_): _description_
            group (_type_): _description_
            pos (_type_): _description_
            speed (_type_): _description_
            course (_type_): _description_
            height (int, optional): _description_. Defaults to 0.
            coordinate_system (str, optional): _description_. Defaults to "Cartesian".
            formation (_type_, optional): _description_. Defaults to None.
        """
        assert formation is not None
        if isinstance(models, str):
            models = [models] * len(names)
        points = alg.fmt.gen_fmt_pos(pos, course, formation, coordinate_system)
        for i in range(len(names)):
            self.gen_platform(names[i], models[i], group, points[i], speed, course, height, coordinate_system)

    def gen_satellite(self, name, model, group, ptype=None, country=None, motor_param=None):
        try:
            model_dct = self.db[model]
            cls_ = CLASS[model_dct["class"]]
        except:
            import pdb; pdb.set_trace()
        p = cls_(self, name, model, group, ptype, country)
        p.motor.set_orbit_param(motor_param)
        if self._is_started: # 如果引擎已启动start，则手动激活
            p.activate()
        return p

    def gen_network(self, model, units):
        """
        创建   
        Args:
            model: 群组名称
            units: 平台名称

        Returns:群组实例

        """
        model_dct = self.db[model]
        cls_ = CLASS[model_dct["class"]]
        network = cls_(self, model)
        if self._is_started: # 如果引擎已启动start，则手动激活
            network.activate()
        for obj in units:
            p = self.get_unit(obj)
            assert p.comdev is not None
            network.add_comdev(p.comdev)
        return network

    def gen_munition(self, carrier, model):
        """
        生成弹药组件
        Args:
            carrier: 媒介平台名称
            model: 平台名称

        Returns:

        """
        p = self.get_unit(carrier)
        m = CLASS[self.db[model]["class"]](p, model)
        if self._is_started: # 如果引擎已启动start，则手动激活
            m.activate()
        return m

    def gen_child_platform(self, carrier, model):
        """
        对平台的依附模式进行设置（多用于设置船只上配置飞机）
        Args:
            carrier: 平台名称
            model: 依附平台类名称

        Returns:该平台的实例（obj）

        """
        p = self.get_unit(carrier)
        child = CLASS[self.db[model]["class"]](p, model)
        if self._is_started: # 如果引擎已启动start，则手动激活
            child.activate()
        return child

    def gen_star_network(self, model, center_uname, unames):
        """
           设置
        Args:
            model:    名称
            center_uname: 第一级平台名称
            unames: 第一级平台下的其他平台(list)

        Returns:   实例(obj)

        """
        assert not self.sim_config['ignore_com'], "仅在不忽略通信限制模式下允许建立通信  "
        model_dct = self.db[model]
        cls_ = CLASS[model_dct["class"]]
        network = cls_(self, model)
        if self._is_started: # 如果引擎已启动start，则手动激活
            network.activate()
        c = self.unit_by_name(center_uname)
        assert c.comdev is not None
        network.add_center_comdev(c.comdev)
        for name in unames:
            p = self.unit_by_name(name)
            assert p.comdev is not None
            network.add_comdev(p.comdev)
        # 在 network 初始化时, 已经将 network 添加至 engine 中, 此处注释
        # self._networks.append(network)
        return network

    def delete_star_network(self, network):
        network.kill()
        if network in self._networks:
            self._networks.remove(network)

    # -------------仿真实体查询接口----------------
    def unit_by_name(self, name):
        """
        获取实体名称
        Args:
            name:实体名称

        Returns:实体实例

        """
        return self._name_units[name]

    def unit_by_names(self, names):
        """
        获取多个实体名称
        Args:
            names: 多个实体名称(list)

        Returns:多个实体实例(list)

        """
        return [self._name_units[name] for name in names]

    def comp_by_ucname(self, ucname):
        """
        根据名字查询组件
        Args:
            ucname:名字

        Returns:组件信息

        """
        unit_name, comp_name = ucname.split(".")
        unit = self.unit_by_name(unit_name)
        comp = unit.comp_by_name(comp_name)
        return comp

    def comp_by_uname_cname(self, uname, cname):
        """
        根据多个名字查询组件
        Args:
            uname: 名字1
            cname: 名字2

        Returns:组件信息(obj)

        """
        unit = self.unit_by_name(uname)
        comp = unit.comp_by_name(cname)
        return comp

    def get_unit(self, obj):
        """
        获取实体信息
        Args:
            obj: 实体实例

        Returns:unit信息(obj)

        """
        if isinstance(obj, arch.Unit):
            unit = obj
        elif isinstance(obj, str):
            unit = self.unit_by_name(obj)
        else:
            raise RuntimeError("未知输入类型")
        return unit

    def get_unit_info(self, obj):
        """ 获取单元的信息，用以在服务模式下排查问题 """
        u = self.get_unit(obj)
        x, y, z = u.coords
        lng, lat = self.xy2lnglat(x, y)
        dct = {"velocity": u.velocity.tolist(), "speed": u.speed,
               "coords": [x, y, z], "lnglatheight": [lng, lat, z]}
        return dct

    def get_unit_base(self, obj):
        """
        获取unit的根信息
        Args:
            obj: 实体实例

        Returns:

        """
        unit = self.get_unit(obj)
        while unit.is_at_home:
            unit = unit.home_unit
        return unit

    def get_comp(self, obj):
        """
        获取平台组件
        Args:
            obj:unit实例

        Returns:

        """
        if isinstance(obj, arch.Component):
            comp = obj
        elif isinstance(obj, str) and "." in obj:
            comp = self.comp_by_ucname(obj)
        else:
            raise RuntimeError(f"未知输入类型{obj}")
        return comp

    def get_comdev(self, obj):
        if isinstance(obj, arch.Platform):
            comdev = obj.comdev
        elif isinstance(obj, arch.Comdev):
            comdev = obj
        elif isinstance(obj, str):
            if "." not in obj:
                # uname
                comdev = self.unit_by_name(obj).comdev
            else:
                # ucname
                comdev = self.comp_by_ucname(obj)
        else:
            raise RuntimeError("未知输入类型")
        return comdev

    def get_radars(self, obj):
        """
        获取 信息
        Args:
            obj: 实体实例

        Returns: 信息

        """
        if isinstance(obj, arch.Platform):
            radars = obj.radars
        elif isinstance(obj, CLASS["Radar"]):
            radars = [obj]
        elif isinstance(obj, str):
            if "." not in obj:
                # uname
                radars = self.unit_by_name(obj).radars
            else:
                # ucname
                radars = [self.comp_by_ucname(obj)]
        else:
            raise RuntimeError("未知输入类型")
        return radars

    def get_guiders(self, obj):
        """
        获取制导器信息
        Args:
            obj: 实体实例

        Returns:制导器信息

        """
        if isinstance(obj, arch.Platform):
            guiders = obj.guiders
        elif isinstance(obj, CLASS["RadarWithGuider"]) or isinstance(obj, CLASS["Guider"]):
            guiders = [obj]
        elif isinstance(obj, str):
            if "." not in obj:
                # uname
                guiders = self.unit_by_name(obj).guiders
            else:
                # ucname
                guiders = [self.comp_by_ucname(obj)]
        else:
            raise RuntimeError("未知输入类型")
        return guiders

    def get_intel(self, obj):
        """
        获取 信息
        Args:
            obj: 实体实例

        Returns:实体对应的 信息

        """
        if isinstance(obj, arch.Platform):
            intel = obj.intelligence
        elif isinstance(obj, CLASS["Intelligence"]):
            intel = obj
        elif isinstance(obj, str):
            if "." not in obj:
                # uname
                intel = self.unit_by_name(obj).intelligence
            else:
                # ucname
                intel = self.comp_by_ucname(obj)
        else:
            raise RuntimeError("未知输入类型")
        return intel

    def get_networks(self, obj1, obj2):
        """
        获取平台1与平台2的  通信
        Args:
            obj1: 实体实例1
            obj2: 实体实例2

        Returns:通信信息

        """
        comdev1 = self.get_comdev(obj1)
        comdev2 = self.get_comdev(obj2)
        assert comdev1 is not None
        assert comdev2 is not None
        nets = []
        for net in self._networks:
            res = net.check_isin_net(comdev1, comdev2)
            if res:
                nets.append(net)
        return nets

    def get_units_names(self):
        """
        获取_name_units内的unit名称
        Returns:

        """
        return list(self._name_units.keys())

    # -------------仿真实体指令控制接口----------------
    def add_maneuver_cmd(self, unit, cmd):
        """
        增加机动指令
        Args:
            unit: 实体实例
            cmd: 指令信息

        Returns:

        """
        p = self.get_unit(unit)
        p.motor.add_maneuver_cmd(cmd)

    def insert_maneuver_cmd(self, unit, cmd, rightnow=False):
        """
        插入机动信息
        Args:
            unit: 实体实例
            cmd: 指令信息
            rightnow: 是否现在执行

        Returns:

        """
        p = self.get_unit(unit)
        p.motor.insert_maneuver_cmd(cmd, rightnow)

    def turn_on_sensors(self, sensors):
        """
        多个声呐开机
        Args:
            sensor: 多个声呐实例(list)

        Returns:

        """
        for sensor in sensors:
            self.turn_on(sensor)

    def turn_off_sensors(self, sensors):
        """
        多个声呐关机
        Args:
            sensor: 多个声呐实例(list)

        Returns:

        """
        for sensor in sensors:
            self.turn_off(sensor)

    def turn_on_radars(self, unames=None):
        """ 如果 已死亡或开机，则不重复开机
             开机
        """
        if unames is None:
            for unit in self.units():
                if hasattr(unit, "radars"):
                    for radar in unit.radars:
                        if radar.isactive and (not radar.is_on):
                            radar.turn_on()
        else:
            for name in unames:
                unit = self.unit_by_name(name)
                if hasattr(unit, "radars"):
                    for radar in unit.radars:
                        if radar.isactive and (not radar.is_on):
                            radar.turn_on()

    def turn_off_radars(self, unames=None):
        """ 
        """
        if unames is None:
            for unit in self.units():
                if hasattr(unit, "radars"):
                    for radar in unit.radars:
                        if radar.isactive and radar.is_on:
                            radar.turn_off()
        else:
            for name in unames:
                unit = self.unit_by_name(name)
                if hasattr(unit, "radars"):
                    for radar in unit.radars:
                        if radar.isactive and radar.is_on:
                            radar.turn_off()

    # -------------仿真实体关系设置与检查接口----------------
    def check_isin_network(self, obj1, obj2):
        """
        检查实体1与实体2的  关系有关系为True无关系为Flase
        Args:
            obj1: 实体1实例
            obj2: 实体2实例

        Returns:True、False

        """
        if self.sim_config["ignore_com"]:
            return True
        comdev1 = self.get_comdev(obj1)
        comdev2 = self.get_comdev(obj2)
        assert comdev1 is not None
        assert comdev2 is not None
        for net in self._networks:
            res = net.check_isin_net(comdev1, comdev2)
            if res:
                return res
        return False

    def set_relation_intels(self, superior, juniors):
        superior_intel = self.get_intel(superior)
        assert superior_intel is not None
        for junior in juniors:
            junior_intel = self.get_intel(junior)
            assert junior_intel is not None
            assert self.check_isin_network(superior_intel.unit, junior_intel.unit)
            junior_intel.add_superior_intel(superior_intel)

    def set_relation_intel_comps(self, intel, comps):
        """ 设置 处理设备信息向不同组件分发的关系 """
        intel = self.get_intel(intel)
        assert intel is not None
        for c in comps:
            comp = self.get_comp(c)
            assert self.check_isin_network(intel.unit, comp.unit)
            intel.add_consumer(comp)
            
    def set_relation_intel_sensors(self, intel, sensor_ucnames):
        """ 设置传感器向 处理组件上报探测信息的关系 """
        intel = self.get_intel(intel)
        assert intel is not None
        for name in sensor_ucnames:
            sensor = self.comp_by_ucname(name)
            assert self.check_isin_network(intel.unit, sensor.unit)
            sensor.add_processor(intel)

    def set_target_guider_relations(self, platforms):
        for p1 in platforms:
            for p2 in platforms:
                self.set_crossplatform_guider(p1, p2)
                self.set_crossplatform_guider(p2, p1)

    def set_target_found_relations(self, platforms):
        """
        发现目标的信息共享
        Args:
            platforms: 共享信息的实体实例(list)

        Returns:

        """
        for p1 in platforms:
            for p2 in platforms:
                if isinstance(p1, str):
                    p1 = self.unit_by_name(p1)
                if isinstance(p2, str):
                    p2 = self.unit_by_name(p2)
                if p1 is not p2:
                    for radar in self.get_radars(p1):
                        radar.add_processor(self.get_intel(p2))
                    for radar in self.get_radars(p2):
                        radar.add_processor(self.get_intel(p1))

    # ------------------仿真动作控制接口------------------------
    def ws_air_decision(self, ucname, target_name, num=2):
        """
        飞机决策
        Args:
            ucname: 实体名臣
            target_name: 目标名称
            num: 打击数量

        Returns:

        """
        ws = self.comp_by_ucname(ucname)
        target = self.unit_by_name(target_name)
        ws.ai_decision_api(target, num)

    def modify_database(self, key, value):
        """
        数据库修改
        Args:
            key:键
            value:值

        Returns:

        """
        # 修改数据库
        if len(key) == 1:
            self.db[key[0]] = value
        elif len(key) == 2:
            self.db[key[0]][key[1]] = value
        elif len(key) == 3:
            self.db[key[0]][key[1]][key[2]] = value
        elif len(key) == 4:
            self.db[key[0]][key[1]][key[2]][key[3]] = value

    def get_component_list(self):
        """ 获取本次仿真中的是否绘制组件的字典 """
        data = {}
        for unit in self.units():
            if unit.home_unit is None or isinstance(unit, arch.DependentPlatform):
                if unit.name in self.render_config['component_render_units']:
                    data[unit.name] = True
                else:
                    data[unit.name] = False
        return data

    def get_track_list(self):
        """ 获取本次仿真中是否绘制历史轨迹的字典 """
        data = {}
        for unit in self.units():
            if not unit.is_at_home:
                if unit.name in self.render_config['history_points_units'] or 'all' in self.render_config['history_points_units']:
                    data[unit.name] = True
                else:
                    data[unit.name] = False
        return data

    cpdef _save_command_msg(self, msg):
        self._command_msg_list.append(msg)

    cpdef list _gen_web_event_texts(self):
        cdef list res = self._command_msg_list.copy()
        self._command_msg_list = []
        return res

    cpdef list _gen_web_render_data(self):
        """ 生成二维web绘制数据
        """
        radar_envelope = self.render_config["radar_envelope"]  # 是否显示 探测包络
        attack_range_envelope = self.render_config["attack_range_envelope"]  # 是否显示攻击范围探测包络
        raw_data = []
        data = []
        red_radars = []
        blue_radars = []
        red_attack_ranges = []
        blue_attack_ranges = []

        for network in self.networks():
            pic_data = network.drawSymbol()
            raw_data.extend(pic_data)

        self.lock.acquire()
        # for o in self.special_effects:
        #     if o.isactive:
        #         pic_data = o.drawSymbol()
        #         data.extend(pic_data)
        for name, v in self.engine.render_data.items():
            if v.isactive:
                pic_data = CLASS[v.class_].drawSymbol(self, name)
                raw_data.extend(pic_data)
        self.lock.release()

        for e in self.actives():
            if e.is_at_home: continue
            pic_data = e.drawSymbol()
            raw_data.extend(pic_data)

        for symbol in raw_data:
            if symbol["type_"] == "Radar":
                if radar_envelope:
                    if symbol["group"].upper() == "RED":
                        red_radars.append(symbol)
                    elif symbol["group"].upper() == "BLUE":
                        blue_radars.append(symbol)
                    else:
                        data.append(symbol)
                else:
                    data.append(symbol)

            elif symbol["type_"] == "AttackRange":
                if attack_range_envelope:
                    if symbol["group"].upper() == "RED":
                        red_attack_ranges.append(symbol)
                    elif symbol["group"].upper() == "BLUE":
                        blue_attack_ranges.append(symbol)
                    else:
                        data.append(symbol)
                else:
                    data.append(symbol)
            else:
                data.append(symbol)


        data.extend(self.shape_marker_data)
        data.extend(merge_range_data(red_radars))
        data.extend(merge_range_data(blue_radars))
        data.extend(merge_range_data(red_attack_ranges))
        data.extend(merge_range_data(blue_attack_ranges))

        new_data = []

        for symbol in data:
            if symbol["mode"] in ["Flag", "Marker", "Text"]:

                if symbol.get('x', None) is not None:
                    if symbol.get('lng', None) is None:
                        try:
                            lng, lat = self.xy2lnglat(symbol["x"], symbol["y"], )
                            symbol["lng"] = round(lng, 6)
                            symbol["lat"] = round(lat, 6)
                        except:
                            symbol["lng"] = None
                            symbol["lat"] = None
                    symbol["x"] = round(symbol["x"], 6)
                    symbol["y"] = round(symbol["y"], 6)
                if symbol.get('lng', None) is not None:
                    if symbol.get('x', None) is None:
                        try:
                            x, y = self.lnglat2xy(symbol["lng"], symbol["lat"])
                            symbol["x"] = round(x, 6)
                            symbol["y"] = round(y, 6)
                        except:
                            symbol["x"] = None
                            symbol["y"] = None
                    symbol["lng"] = round(symbol["lng"], 6)
                    symbol["lat"] = round(symbol["lat"], 6)
                new_data.append(symbol)
            else:
                if symbol.get('x', None) is not None:
                    if symbol.get('lng', None) is None:
                        try:
                            lng, lat = self.xy2lnglat(np.array(symbol["x"]), np.array(symbol["y"]))
                            symbol["lng"] = np.around(lng, 6).tolist()
                            symbol["lat"] = np.around(lat, 6).tolist()
                        except:
                            symbol["lng"] = []
                            symbol["lat"] = []
                    symbol["x"] = np.around(symbol["x"], 6).tolist()
                    symbol["y"] = np.around(symbol["y"], 6).tolist()

                if symbol.get('lng', None) is not None:
                    if symbol.get('x', None) is None:
                        try:
                            x, y = self.lnglat2xy(np.array(symbol["lng"]), np.array(symbol["lat"]))
                            symbol["x"] = np.around(x, 6).tolist()
                            symbol["y"] = np.around(y, 6).tolist()
                            if float('inf') in x:
                                symbol["x"] = []
                                symbol["y"] = []
                        except:
                            symbol["x"] = []
                            symbol["y"] = []
                    symbol["lng"] = np.around(symbol["lng"], 6).tolist()
                    symbol["lat"] = np.around(symbol["lat"], 6).tolist()
                new_data.append(symbol)
                # if len(symbol["lng"]) >= 2:
                #     new_data.append(symbol)
        return new_data

    def _gen_web_render_data3D(self):
        """ 生成三维web绘制数据
        """
        data = []
        for e in self.actives():
            pic_data = e.drawSymbol3D()
            data.extend(pic_data)
        new_data = []
        for symbol in data:
            if symbol["mode"] in ["Flag", "Marker", "Text", "Cylinder", "Ellipsoid"]:
                lng, lat = self.xy2lnglat(symbol["x"], symbol["y"])
                symbol["lng"] = lng
                symbol["lat"] = lat
                new_data.append(symbol)
            else:
                lng, lat = self.xy2lnglat(np.array(symbol["x"]), np.array(symbol["y"]))
                symbol["lng_list"] = lng.tolist()
                symbol["lat_list"] = lat.tolist()
                symbol["z_list"] = symbol["z"]
                symbol["lng"] = 0
                symbol["lat"] = 0
                symbol["z"] = 0
                new_data.append(symbol)
        return new_data

    cpdef dict get_simlation(self):
        """
        获取所有组件基础信息
        Returns:

        """
        cdef dict units_info = {}
        cdef list all_unit = self.units()
        cdef list red_info_list = []
        cdef list blue_info_list = []

        for unit in all_unit:
            unit_info = {}
            # print(unit.attr.db.get("class"))
            if isinstance(unit, (CLASS["Plane"], CLASS["Ship"])):
                unit_info["name"] = unit.name  # unit名称
                unit_info["model"] = unit.model  # unit类型
                unit_info["active"] = unit.isactive  # unit存活状态
                unit_info["speed"] = unit.speed  # unit速度
                unit_info["lng"] = unit.lnglat[0]  # unit位置信息：经度
                unit_info["lat"] = unit.lnglat[1]  # unit位置信息：纬度
                unit_info["course"] = unit.course  # unit速度平面方向
                unit_info["current"] = unit.vitalities.threshold.damage  # unit生命值
                if isinstance(unit, CLASS["Plane"]):
                    unit_info["if_oil"] = True  # 是否有油量
                    # unit_info["oil_mass"] = (unit.motor.attr.dmax - float(unit.motor.distance)) / unit.motor.attr.dmax * 100        #油量百分比
                    unit_info["type"] = "Plane"
                else:
                    unit_info["if_oil"] = False
                    unit_info["type"] = "Ship"
                if unit.group == "RED":
                    red_info_list.append(unit_info)
                else:
                    blue_info_list.append(unit_info)
        units_info["red"] = red_info_list
        units_info["blue"] = blue_info_list
        return units_info

    cpdef float engine_time(self):
        """
        获取当前仿真时间
        Returns:仿真时间

        """
        return self.time

    def get_simulation_info(self):
        """ 获取仿真态势绘制信息 """
        data = self._gen_web_render_data()
        event_texts = self._gen_web_event_texts()
        if self.web_show:
            msg_dict = {'simulation_time': f'{self.time:.2f}秒',
                        'simulation_ratio': round(self.ratio, 1),
                        'fight_time': self.ymdhms,
                        'user_name': self.user_name,
                        'ip': self.web_ip,
                        'data': data,
                        'event_texts': event_texts,
                        'show': self.web_show,
                        }
        else:
            msg_dict = {
                'show': self.web_show,
            }
        return msg_dict

    def _post_simulation_info_single(self):
        """
        发送单个仿真信息
        Returns:

        """
        data = self._gen_web_render_data()
        event_texts = self._gen_web_event_texts()
        msg_dict = {'simulation_time': f'{self.time:.2f}秒',
                    'simulation_ratio': round(self.ratio, 1),
                    'fight_time': self.ymdhms,
                    'user_name': self.user_name,
                    'engine_name': self.name,
                    'ip': self.web_ip,
                    'data': data,
                    'event_texts': event_texts,
                    'show': self.web_show
                    }
        json_data = {
            'func_name': 'push_msim_data',
            'source': 'test',
            'kwargs': msg_dict
        }
        msg = json.dumps(json_data)
        try:
            self.web_client.control(simserver_pb2.MsgStr(msg=msg))
        except:
            #aaaa = 1
            print(f"可能是web服务端的地址{self.web_ip}未定义或对应的web服务未打开, 或者因为保存时del simserver_pb2")

    def _post_simulation_info(self, interval=0.2):
        """ 向web推送仿真态势绘制信息 """
        print("启动推送数据线程")
        if not self.isactive:
            time.sleep(3)
            if not self.isactive:
                print("仿真引擎未激活，推送数据线程退出")
                return
        while self.isactive:
            self._post_simulation_info_single()
            time.sleep(interval)
        # print("暂时不推送数据到Web端")

    def _post_simulation_info_single_to_cpp(self, host, port):
        """
        通过UDP的方式将数据推送至CPP端
        Returns:
        """
        # 取得态势数据
        simulation_list = self._gen_web_render_data()
        # 取得所有单位的态势数据
        unit_simulation_list = [tmp_data for tmp_data in simulation_list if tmp_data["mode"] == "Flag"]
        # 取得当前信息单元序号
        cur_sequence_number = self.sequence_number
        # 对态势数据按照entity_code进行排序
        # 取得目前存储的最大编号的下一编号，即为self.entity_name_to_code_dict中元素数量+1
        next_no = len(self.entity_name_to_code_dict) + 1
        unit_simulation_list = sorted(unit_simulation_list,
                                        key=lambda t: self.entity_name_to_code_dict.get(t["batch_no"], next_no))
        # 遍历态势数据向UDP进行发送
        for unit_simulation_info in unit_simulation_list:
            if unit_simulation_info["pmodel"] in ("VirtualSatellite", "SSMissileBase", "Airport"):
                continue
            # 取得UDP发送的数据包
            pack_data = self.__get_pack_data(unit_simulation_info, cur_sequence_number)
            if pack_data:
                # 发送数据
                self.udp_socket.sendto(pack_data, (host, port))
        self.sequence_number = 0 if self.sequence_number == 255 else self.sequence_number + 1

    def __get_pack_data(self, unit_simulation_info, cur_sequence_number):
        """
        取得UDP发送的数据包
        Args:
            unit_simulation_info: 态势数据信息
            cur_sequence_number: 当前信息单元序号

        Returns:

        """
        date_time_fmt = "%Y-%m-%d %H:%M:%S.%f"
        date_fmt = "%Y-%m-%d"
        sys_datetime = datetime.datetime.now()
        str_cur_date = datetime.datetime.strftime(sys_datetime, date_fmt)
        str_cur_datetime = datetime.datetime.strftime(sys_datetime, date_time_fmt)
        start_time = datetime.datetime.strptime(f"{str_cur_date} 00:00:00.000001", date_time_fmt)
        end_time = datetime.datetime.strptime(str_cur_datetime, date_time_fmt)
        diff_time = end_time - start_time
        seconds = diff_time.seconds
        millisecond = round(diff_time.microseconds / 1000)
        # 取得时间戳，从当天00:00:00开始的毫秒数
        command_product_time = int((seconds * 1000 + millisecond + 1) / 10)
        # 定义编码格式
        encode_str = "gbk"
        # 定义数据对齐格式 字节顺序采用小端
        pack_fmt = "<16sBBBBI16shh8shddfffffff"

        # 取得实体名称
        entity_name = unit_simulation_info["batch_no"]
        if entity_name:
            # 根据实体名称取得实体对象
            entity_unit = self.unit_by_name(entity_name)
            # 取得实体代号
            if entity_name not in self.entity_name_to_code_dict:
                self.entity_name_to_code_dict[entity_name] = self.entity_code
                self.entity_code += 1
            entity_code = self.entity_name_to_code_dict[entity_name]

            # 取得实体型号
            entity_model = entity_unit.model
            entity_type = database.DB.get_model_for_udp(entity_model)
            # 对实体名称通过下划线"_"进行拆分
            split_names = entity_name.split("_")
            # 取得实体编号
            entity_no = database.DB.get_no_for_name(split_names[0])
            # 计算拆分后数据长度
            count = len(split_names)
            if unit_simulation_info["pos_type"] == "missile":
                missile_name = split_names[-1]
                missile_name = missile_name.replace(entity_model, entity_type)
                # missile_name = missile_name.replace('-', '').replace('[', '_').replace(']', '')
                if count == 2:
                    entity_name = f"{entity_no}_{missile_name}"
                elif count == 3:
                    entity_name = f"{entity_no}{str(int(split_names[1])).zfill(2)}_{missile_name}"
            else:
                if count == 1:
                    entity_name = entity_no
                elif count == 2:
                    entity_name = f"{entity_no}{str(int(split_names[1])).zfill(2)}"

            # 取得载体代号 只有飞机才有
            # 载体代号不为0，表示飞机在船上，为0，表示在空中，只传0即可
            carrier_code = 0
            # 取得实体属性
            entity_attribute = 2 if unit_simulation_info["group"] == "RED" else 1
            ip1_list = [int(num) for num in self.udp_src_ip.split(".")]
            ip2_list = [int(num) for num in self.udp_dst_ip.split(".")]
            bytes_list = [0x00, 0x01, 0x62, 0x00] + ip1_list + ip2_list + [0x98, 0x98, 0x00, 0x01]
            csmp_head = bytes(bytes_list)
            # 取得航速 米/秒
            speed = unit_simulation_info["speed"]
            # 将航速转为 千米/小时
            speed = speed * 3600 / 1000
            pack_res = struct.pack(pack_fmt, csmp_head,  # char CSMPhead[16]; //可直接忽略不用赋值
                                   cur_sequence_number,  # unsigned char cellSequenceNumber; // 信息单元序号，0~255循环使用
                                   0xA0,  # unsigned char cellIdentifier; // 信息单元标识，0xA0H
                                   82,  # unsigned short cellLength; // 信息单元长度，82字节
                                   command_product_time,  # unsigned commandProductTime; // 时间戳，从当天00:00:00开始的毫秒数
                                   entity_name.encode(encode_str),  # char EntityName[16]; // 实体名称
                                   entity_code,  # short entity_code; // 实体代号，ID号，唯一标识
                                   carrier_code,  # short carrier_code; // 载体代号，飞机才有用，可不填
                                   entity_type.encode(encode_str),
                                   # char EntityType[8]; // 实体型号，字符串，建立字符串与兵力型号之间的关系，与飞鸿确认，填写模拟器中ForceType.xml中已有的型号
                                   entity_attribute,  # short EntityAttribute; // 实体属性 0:不明 1:敌 2:我 3:友
                                   unit_simulation_info["lng"],  # double Longitude; // 经度
                                   unit_simulation_info["lat"],  # double Latitude; // 纬度
                                   unit_simulation_info["z"],  # float Depth; // 绝对深度（高度）实体距标准海平面的绝对高度
                                   unit_simulation_info["z"],  # float RHeight; // 相对高度，实体距离地面/海面的相对高度
                                   speed,  # float SailVelocity; // 航速，实体运动速度（千米/小时）
                                   unit_simulation_info["az"],  # float SailDirection; // 航向，以正北方向为0，顺时针计算
                                   0,  # float Heading; // 偏航角，实体的纵轴在水平面投影与实体前进方向在水平面上投影的夹角
                                   unit_simulation_info["pitch"],  # float Pitch; // 俯仰角，实体的纵轴与水平面的夹角
                                   0)  # float Roll; // 滚转角，实体的横轴与水平面的方向的夹角

            # 打印数据测试
            is_print = False
            if is_print:
                csmp_head, cell_sequence_number, cell_identifier, cell_length0, cell_length1, command_product_time, \
                    entity_name, entity_code, carrier_code, entity_type, entity_attribute, longitude, latitude, depth, \
                    r_height, sail_velocity, sail_direction, heading, pitch, roll = struct.unpack(pack_fmt, pack_res)

                res_str = "csmp_head =" + str(csmp_head) + \
                          f", cell_sequence_number = {cell_sequence_number}, cell_identifier = {cell_identifier}" + \
                          f", cell_length1 = {cell_length1}, command_product_time = {command_product_time}" + \
                          ", entity_name =" + entity_name.decode(encode_str).strip('\x00') + \
                          f", entity_code = {entity_code}, carrier_code = {carrier_code}" + \
                          ", entity_type =" + entity_type.decode(encode_str).strip('\x00') + \
                          f", entity_attribute = {entity_attribute}, longitude = {longitude}, latitude = {latitude}" + \
                          f", depth = {depth}, r_height = {r_height}, sail_velocity = {sail_velocity}" + \
                          f", sail_direction = {sail_direction}, heading = {heading}, pitch = {pitch}, roll = {roll}"

                print(res_str)

            return pack_res
        else:
            return None

    def _post_simulation_info_to_cpp(self, host, port, interval=1.0):
        """ 向C++端推送仿真态势绘制信息 """
        print("启动C++端推送数据线程")
        if not self.isactive:
            time.sleep(3)
            if not self.isactive:
                print("仿真引擎未激活，向C++端推送数据线程退出")
                return
        while self.isactive:
            self._post_simulation_info_single_to_cpp(host, port)
            time.sleep(interval)

    def _gen_nats_client(self, host, port):
        """ 生成Nats客户端 """
        async def connect_nats():
            return await nats.connect(f"nats://{host}:{port}")
        # 创建Nats客户端
        loop = asyncio.get_event_loop()
        try:
            self.nats_client = loop.run_until_complete(connect_nats())
            # loop.close()
        except:
            pass

    def post_simulation3D_info(self, url="http://192.168.1.131:5000/data"):
        """
        发送仿真3D信息
        Args:
            url: 发送地址

        Returns:

        """
        if self.isactive:
            while self.isactive:
                data = self._gen_web_render_data3D()
                try:
                    msg = json.dumps(data)
                except:
                    print(data)
                print(data)
                response = requests.post(url, data=msg)
                time.sleep(1)

    def post_single_data(self, data):
        raise RuntimeError("请使用save_single_data, post_single_data的功能已经合并到save_single_data")

    def post_multi_data(self, data):
        """ 向web推送单次仿真统计结果
        """
        # data['monitor'] = [{'num': 1, 'unit': '次', 'name': '已完成次数'}, {'num': 20, 'unit': '次', 'name': '总仿真次数'}]
        json_data = json.dumps({
            'func_name': "push_multi_statistics",
            'kwargs': {
                'user_name': self.user_name,
                'ip': self.web_ip,
                'data': data}
        })
        self.web_client.control(simserver_pb2.MsgStr(msg=json_data))

    def save_single_data(self, data):
        """ 保存单次仿真统计数据 """
        self.post_web_statistic_single_data = data
        if self.use_web:
            # 向web推送单次仿真统计结果
            # 当前和 web 前端约定，当 engine_name 字段为空时为单次仿真数据，不为空时为并行仿真数据
            show_data = {
                'func_name': "push_single_statistics",
                'kwargs': {
                    'user_name': self.user_name,
                    'ip': self.web_ip,
                    'data': data,
                    'show': self.web_show
                }
            }
            # 增加并行仿真标签
            if self.name != 'engine':
                show_data['kwargs']['engine_name'] = self.name

            json_data = json.dumps(show_data)
            self.web_client.control(simserver_pb2.MsgStr(msg=json_data))

    def get_single_statistics(self):
        """ 获取单次仿真的统计数据 """
        return self.post_web_statistic_single_data

    # -------------------指令下发查询接口--------------------------

    def _update_cmds(self):
        exception_events = []
        self._unexecuted_cmds_lock.acquire()
        while self._unexecuted_cmds_id:
            _, cmd_id = self._unexecuted_cmds_id.peek()
            cmd = self._unexecuted_id_2_cmd[cmd_id]
            if cmd["begin"] <= self.time:
                _, cmd_id = self._unexecuted_cmds_id.pop()
                cmd = self._unexecuted_id_2_cmd.pop(cmd_id)
                print(f"开始执行指令{cmd['id']}--{cmd['func_name']}--{self.time}--{cmd['begin']}")
                args = cmd.get("args", [])
                kwargs = cmd.get("kwargs", {})
                # 命令执行置信度
                if 'confidence' in kwargs:
                    confidence = kwargs['confidence']
                    assert confidence <= 1 and confidence >= 0
                    # 执行失败
                    if random.random() > confidence:
                        exception_events.append(f"{cmd['func_name']}执行失败")
                        continue
                    else:
                        del kwargs['confidence']
                try:
                    res = getattr(self, cmd["func_name"])(*args, **kwargs)
                    _, cmd_name = res
                    print(f"{cmd['func_name']}的返回值{res}")
                    assert cmd_name is not None, cmd
                    self._cmd_id_name_dct[cmd["id"]] = cmd_name  # 执行命令时生成对应的关系
                except:
                    traceback.print_exc()
                    continue
            else:
                break
        self._unexecuted_cmds_lock.release()
        if exception_events:
            # 只有不为空时才执行，避免将其他地方触发的意外冲击掉
            self.set_exception_event(','.join(exception_events))

    def _state_format(self, res):
        """ 仅对指令的状态字符串进行修改： 成功 -> 执行成功，失败 -> 执行失败, 结束-> 执行结束, 正在执行->正在执行, 未执行->未执行 """

        ## res : {id: {"begin":, "end":, "state": ,}}
        def state_modify(state):
            return "执行" + state if state in ["成功", "失败", "结束"] else state

        for k in res:
            res[k]["state"] = state_modify(res[k]["state"])
        return res

    def receive_query_cmds_and_exception(self, dct:dict={}):
        cmds = dct["send_cmds"]
        self.lock.acquire()
        for cmd in cmds:
            if cmd["id"] in self._cmd_id_name_dct:
                print(f"指令的id有重复, 重复的指令为{cmd}")
                print(f"忽略该指令")
                continue
            try:
                self._unexecuted_cmds_id.push(cmd["begin"], cmd["id"])
                self._unexecuted_id_2_cmd[cmd["id"]] = cmd
            except:
                raise RuntimeError(f"--忽略错误指令--{cmd}")
        self.lock.release()
        res = {}
        cmd_ids = dct["query_ids"]
        for cmd_id in cmd_ids:
            if cmd_id not in self._cmd_id_name_dct:
                res[cmd_id] = {"begin": -1, "end": -1, "state": "未执行"}  # 因C++的客户端不识别None，因此begin和end改为-1
            else:
                cmd_name = self._cmd_id_name_dct[cmd_id]
                cmd = self.cmd_collections[cmd_name]
                if cmd.res is None:
                    state = "正在执行"
                else:
                    state = cmd.res  # "成功" or "失败"
                assert cmd.end_time != np.inf, "cmd_name:%s" % cmd_name  # 因C语言不识别np.inf，为此，必须设置仿真结束时间(未设置，则仿真结束时间为np.inf)
                res[cmd_id] = {"begin": cmd.begin_time, "end": cmd.end_time, "state": state, "cmd_name": cmd.cmd_name}

        out = {"time": self.time, "query_out": self._state_format(res), "exception": self._exception_event}
        return out


    # --------------远海计划行动监控函数方法接口-------------------

    ####--------------------指令集---------------------------#####
    def cmd_fly_plane(self, platform, plane, cmd_res_name:str=None):
        """ 飞机起飞指令 """
        cmd = CmdData(self, "cmd_fly_plane", "飞机起飞", self.time, cmd_res_name=cmd_res_name)

        platform = self.get_unit(platform)
        # plane = plane.split("_")[0] +'_'+ plane.split("_")[1].lstrip('0')
        plane = self.get_unit(plane)
        if not plane.is_at_home:
            cmd.res = "失败"
            print(f"INFO: plane {plane.name} has already taken off !!!")
            return -1, cmd.cmd_name  # 执行失败

        platform.airportsystem.fly_plane(plane, cmd_name=cmd.cmd_name)
        take_off_time = 300
        return take_off_time, cmd.cmd_name

    def gen_cmd_fly_plane(self, platform, plane, cmd_label="飞机起飞", task_label=""):
        """ 生成飞机起飞指令

        Args:
            platform (str): 飞机所在平台的名称
            plane (str): 飞机的名称
            cmd_label (str, optional): 命令标识

        Returns:
            dict: 返回该飞机的起飞指令
        """
        p = self.get_unit(platform)
        plane = self.get_unit(plane)
        cmd = {
            "cmd": cmd_label,
            "task": task_label,
            "platform": plane.name,
            "type": "fixed",
            "begin": 0,
            "end": 300,
            "func_name": 'cmd_fly_plane',
            "kwargs": {'platform': p.name, 'plane': plane.name, 'cmd_track': True}
        }
        return cmd

    def cmd_plane_return_to_base(self, platform, plane, cmd_res_name:str=None):
        """飞机返航指令"""
        cmd = CmdData(self, "cmd_landon_plane", "飞机返航", self.time, cmd_res_name=cmd_res_name)

        platform = self.get_unit(platform)
        plane = self.get_unit(plane)
        plane.return_to_base(platform, cmd_name=cmd.cmd_name)
        return_to_base_time = 1000
        return return_to_base_time, cmd.cmd_name

    def cmd_schedule_plane(self, platform, plane, dst_state, cmd_res_name:str=None):
        """ 飞机准备等级调整指令 """
        cmd = CmdData(self, "cmd_schedule_plane", "飞机准备等级调整", self.time, cmd_res_name=cmd_res_name)

        platform = self.get_unit(platform)
        plane = self.get_unit(plane)
        platform.airportsystem.schedule(plane, dst_state, cmd.cmd_name)
        schedule_time = 100
        return schedule_time, cmd.cmd_name

    def cmd_fly_area(self, plane, speed=None, xyz_points=None, xy_points=None, lnglat_points=None, height=None,
                    cmd_res_name:str=None):
        """飞向指定空域指令，按设定路径点到达位置后自动盘旋

        Args:
            plane (Plane, str): 接收指令的飞机（或飞机名）
            points (list): 路径点列表
            speed (int): 飞行速度 m/s
            cmd_track (bool, optional): 是否追踪指令执行状态. Defaults to False.

        Returns:
            cmd_time: 指令预计执行时间(s)
            cmd_name: 指令唯一名称
        """
        cmd = CmdData(self, "cmd_fly_area", "飞向指定空域", self.time, cmd_res_name=cmd_res_name)
        # plane = plane.split("_")[0] +'_'+ plane.split("_")[1].lstrip('0')
        plane = self.get_unit(plane)
        if speed is None:
            speed = plane.speed
        if height is None:
            height = plane.coords[2]
        points = self.get_waypoints(xyz_points, xy_points, lnglat_points, height)
        self.insert_maneuver_cmd(plane, {"mode": "waypoints", "waypoints": points, "speed": speed,
                                        "cmd_name": cmd.cmd_name}, rightnow=True)
        self.add_maneuver_cmd(plane, {"mode": "Hover"})
        _coords = np.reshape(plane.coords, (1, 3))
        _points = np.r_[_coords, points]
        dis = alg.geo.path_length(_points)
        fly_time = dis / speed
        return fly_time, cmd.cmd_name


    def gen_cmd_fly_area(self, plane, speed=None, xyz_points=None, xy_points=None, lnglat_points=None, height=None,
                         cmd_label="飞向指定空域", task_label=""):
        """
        Args:
            输入飞机名字, 远海管控json文件
        Return:
            指令内容
        """
        plane = self.get_unit(plane)
        if speed is None:
            speed = plane.speed
        if height is None:
            height = plane.coords[2]

        points = self.get_waypoints(xyz_points, xy_points, lnglat_points, height)
        _coords = np.reshape(plane.coords, (1, 3))
        _points = np.r_[_coords, points]
        dis = alg.geo.path_length(_points)
        fly_time = dis / speed
        cmd = {
            "cmd": cmd_label,
            "task": task_label,
            "platform": plane.name,
            "type": "fixed",
            "begin": self.time,
            "end": self.time + fly_time,
            "func_name": 'cmd_fly_area',
            "kwargs": {
                "plane": plane.name,
                "speed": speed,
                "xyz_points": xyz_points,
                "xy_points": xy_points,
                "lnglat_points": lnglat_points,
                "height": height,
                'cmd_track': True
            }
        }
        return cmd

    def cmd_sail_area(self, ship, speed=None, xy_points=None, lnglat_points=None, 
        cmd_res_name:str=None):
        """
        Args:
            ship (Ship, str): 接收指令的飞机（或飞机名）
            points (list): 路径点列表
            speed (int): 飞行速度 m/s
            cmd_track (bool, optional): 是否追踪指令执行状态. Defaults to False.

        Returns:
            cmd_time: 指令预计执行时间(s)
            cmd_name: 指令唯一名称
        """
        cmd = CmdData(self, "cmd_sail_area", "向指定区域航行", self.time, cmd_res_name=cmd_res_name)

        ship = self.get_unit(ship)
        if speed is None:
            speed = ship.speed
            if speed < 1:
                raise RuntimeError(f"{ship}的speed非常小{speed}，须设置速度")

        points = self.get_waypoints(None, xy_points, lnglat_points, height=0)
        # print(f"INFO: ship {ship} go to {points}")
        self.insert_maneuver_cmd(ship, {"mode": "waypoints", "waypoints": points, "speed": speed,
                                        "cmd_name": cmd.cmd_name}, rightnow=True)
        self.add_maneuver_cmd(ship, {"mode": "speed", "speed": 0.0001})  

        # 设置一个非常小的速度，作为静止状态
        # 针对execute_mode="insert_rightnow"或"insert"可能并不适用

        _coords = np.reshape(ship.coords, (1, 3))
        _points = np.r_[_coords, points]
        dis = alg.geo.path_length(_points)
        sail_time = dis / speed

        return sail_time, cmd.cmd_name

    def gen_cmd_ship_transfer(self, ship, xy_pos=None, lnglat_pos=None, dst_course=None, speed=None, radius=None,
                              cmd_label="舰艇队形调整指令", task_label=""):
        ship = self.get_unit(ship)
        x0, y0, _ = ship.coords
        az0 = ship.course
        if xy_pos is not None:
            x1, y1 = xy_pos
        else:
            x1, y1 = self.lnglat2xy(*lnglat_pos)
        if dst_course is not None:
            az1 = dst_course
        else:
            az1 = az0
        assert speed is not None
        assert radius is not None
        waypoints, length = alg.dubins.get_ship_transfer_waypoints([x0, y0], [x1, y1], az0, az1, radius)
        if waypoints is None:
            # 无须变换，直接瞬时调整方向
            transfer_time = 2
        else:
            transfer_time = length / speed
        cmd = {
            "cmd": cmd_label,
            "task": task_label,
            "platform": ship.name,
            "type": "fixed",
            "begin": self.time,
            "end": self.time + transfer_time,
            "func_name": "cmd_ship_transfer",
            "kwargs": {
                'ship': ship.name,
                "xy_pos": xy_pos,
                "lnglat_pos": lnglat_pos,
                "dst_course": dst_course,
                "speed": speed,
                "radius": radius,
                "cmd_track": True,
                "cmd_label": cmd_label
            }
        }
        return cmd

    def cmd_radar_turn_on(self, platform, radar="", cmd_res_name:str=None, cmd_label=" 设备开机"):
        """  开机指令

        已死亡或开机，则不重复开机
        """
        res = "失败"
        p = self.get_unit(platform)
        if radar is None or radar == "":
            for rd in p.radars:
                if rd.isactive and (not rd.is_on):
                    rd.turn_on()
                    res = "成功"
        else:
            for rd in p.radars:
                if rd.model in radar:
                    if rd.isactive and (not rd.is_on):
                        rd.turn_on()
                        res = "成功"

        cmd = CmdData(self, "cmd_radar_turn_on", cmd_label, self.time, cmd_res_name=cmd_res_name)
        cmd.end_time = self.time
        cmd.res = res
        return 0, cmd.cmd_name  # 0表示执行时长非常短

    def cmd_radar_turn_off(self, platform, radar="", cmd_res_name:str=None, cmd_label=" 设备关机"):
        """  关机指令

        已死亡或关机，则不重复关机
        """
        res = "失败"
        p = self.get_unit(platform)
        if radar is None or radar == "":
            for rd in p.radars:
                if rd.isactive and rd.is_on:
                    rd.turn_off()
                    res = "成功"
        else:
            for rd in p.radars:
                if rd.model in radar:
                    if rd.isactive and rd.is_on:
                        rd.turn_off()
                        res = "成功"

        cmd = CmdData(self, "cmd_radar_turn_off", cmd_label, self.time, cmd_res_name=cmd_res_name)
        cmd.end_time = self.time
        cmd.res = res
        return 0, cmd.cmd_name

    def cmd_build_channel(self, detector, attacker, target=None, cmd_res_name:str=None, cmd_label="通道组织构建命令"):
        """ 通道组织构建命令 """
        detector_intel = self.get_intel(detector)
        attacker_intel = self.get_intel(attacker)
        if target is not None and target != '':
            target = self.get_unit(target)
        assert detector_intel is not None
        assert attacker_intel is not None
        assert self.check_isin_network(detector_intel.unit, attacker_intel.unit)
        detector_intel.add_consumer(attacker_intel, target)
        cmd = CmdData(self, "cmd_build_channel", cmd_label, self.time, cmd_res_name=cmd_res_name)
        cmd.end_time = self.time
        cmd.res = "成功"
        return 0, cmd.cmd_name


    def cmd_cancel_channel(self, detector, attacker, target=None, cmd_res_name:str=None, cmd_label="通道组织撤销命令"):
        """ 通道组织撤销命令 """
        detector_intel = self.get_intel(detector)
        attacker_intel = self.get_intel(attacker)
        if target is not None:
            target = self.get_unit(target)
        assert detector_intel is not None
        assert attacker_intel is not None
        assert self.check_isin_network(detector_intel.unit, attacker_intel.unit)
        detector_intel.remove_consumer(attacker_intel, target)
        cmd = CmdData(self, "cmd_cancel_channel", cmd_label, self.time, cmd_res_name=cmd_res_name)
        cmd.end_time = self.time
        cmd.res = "成功"
        return 0, cmd.cmd_name

    def cmd_activate_found_for_strikechain(self, found_name, cmd_res_name:str=None, cmd_label="打击链探测节点激活"):
        cmd = CmdData(self, "cmd_activate_found_for_strikechain", cmd_label, self.time, cmd_res_name=cmd_res_name)
        cmd.end_time = self.time
        cmd.res = "成功"
        return 0, cmd.cmd_name


    def cmd_activate_engage_for_strikechain(self, engage_name, cmd_res_name:str=None, cmd_label="打击链拦截节点激活"):
        cmd = CmdData("cmd_activate_engage_for_strikechain", cmd_label, self.time, cmd_res_name=cmd_res_name)
        cmd.end_time = self.time
        cmd.res = "成功"
        return 0, cmd.cmd_name

    ####-------------对空仿真指令集生成----------------#####
    def get_cmd_plane_return_to_base(self, plane_name, cmd_label="返航指令"):
        """
            Args:
                输入飞机名字
            Return:
                返回该飞机的返航指令
        """
        plane_unit = self.get_unit(plane_name)
        platform_name = plane_unit.home_unit.name
        cmd = {
            "cmd": cmd_label,
            "type": "dynamic",
            "begin": 5400,
            "end": 7000,
            "func_name": 'cmd_plane_return_to_base',
            "args": [],
            "kwargs": {
                "platform": platform_name,
                "plane": plane_name
            }
        }
        return cmd

    def get_cmd_plane_turnon(self, plane_name, yhgk_json_dct, cmd_label="开启设备指令"):
        """
        Args:
            输入飞机名字, 远海管控json文件
        Return:
            返回一条指令
        """
        plane = self.get_unit(plane_name)

        cmd = {
            "cmd": "开启设备指令",
            "type": "fixed",
            "begin": 1200,
            "end": 5400,
            "kwargs": {
                "device": "KE600Radar"
            }
        }
        return cmd
