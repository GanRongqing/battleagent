import os
import dill
import time
import grpc
import json
import datetime as dt
import argparse
import traceback
import importlib
import threading
from threading import Thread, Lock
from concurrent import futures

import simserver_pb2
import simserver_pb2_grpc

from sim_result import SimResult
from enums import ServerReturnMsg, SimMode, SimState
from utils import get_local_ip, get_member_funcs, GRPC_OPTIONS, ScriptTreeNode

import simulation.core as core
import simulation.database as database
from grpc.experimental import aio
import asyncio

DIR = os.path.dirname(os.path.abspath(__file__))
DATETIME_FMT = "%Y-%m-%d %H:%M:%S"


class SimServer(simserver_pb2_grpc.GreeterServicer):
    def __init__(self, server_port, baseserver_ip='192.168.240.11', baseserver_port=6000):
        super().__init__()
        # 服务本身的 ip, port, 用于注册到base_server
        self.server_ip = get_local_ip()
        self.server_port = server_port
        self.server_url = f'{self.server_ip}:{self.server_port}'
        self.baseserver_ip = baseserver_ip
        self.baseserver_port = baseserver_port
        channel = grpc.insecure_channel("{0}:{1}".format(self.baseserver_ip, self.baseserver_port),
                                        options=GRPC_OPTIONS)
        self.base_client = simserver_pb2_grpc.GreeterStub(channel=channel)
        self.lock = Lock()
        self.engine = None

        # 仿真脚本配置
        self.sces = json.load(open(os.path.join(DIR, 'config', "sces.json"), 'r', encoding='utf-8-sig'))
        self.script_tree = ScriptTreeNode.load_sces_json(self.sces)
        self.gengtu_ip = [line.strip() for line in
                          open(os.path.join('config', 'gengtu_ip.config'), 'r', encoding='utf8').readlines()]

        # web 端显示配置
        self.origin_render_config = database.load_render_config()
        self.origin_checkbox_dict = database.load_checkbox_config()

        self.clear()

        # 注册服务到 base_server, 这两步当前都前后依赖关系
        self._register_server()

        # 心跳检测
        self._heartbeat_thread = Thread(target=self._heartbeat_thread)
        self._heartbeat_thread.start()

    def _acquire_server_lock(self, info):
        """获取服务锁"""
        # 这么写方便在函数内 debug
        # if info != 'heartbeat':
        #     print('acquire lock: ', info)
        self.lock.acquire()

    def _release_server_lock(self, info):
        """释放服务锁"""
        # if info != 'heartbeat':
        # print(f'[{self.server_url}] realease lock: ', info)
        self.lock.release()

    def _register_server(self):
        msg_dict = {
            "flag": "base_server",
            "ip": self.server_ip,
            "source": "SELF",
            "user_name": "SELF",
            "func_name": 'register_simserver',
            "kwargs": {
                "url": self.server_url
            }
        }
        try:
            response = self.base_client.control(simserver_pb2.MsgStr(msg=json.dumps(msg_dict)))
        except Exception as e:
            print(f'{self.server_ip}:{self.server_port} register base_server failed, exit!')
            exit(1)

    def control(self, request, context):
        cmd = json.loads(request.msg)
        res = SimResult(cmd)
        try:
            func = cmd.get("func_name", None)
            kwargs = cmd.get('kwargs', {})
            if func in get_member_funcs(self):
                # 先判断是否由SimServer对象的成员函数执行
                start_time = time.time()
                print(f'{dt.datetime.now().strftime(DATETIME_FMT)}\tFUNC START\t[simulation]{func}')
                if func == 'init':  # 保存的 engine 状态文件
                    kwargs['checkpoint_bytes'] = request.bytes_data
                getattr(self, func)(res, **kwargs)
                if func == 'init':
                    # 此时为引擎启动成功，更新引擎状态和索引
                    self._update_server_data(cmd.get('server_data', {}))
                print(f'[{self.server_url}] {func} time cost: {time.time() - start_time}')
                print(f'{dt.datetime.now().strftime(DATETIME_FMT)}\tFUNC END\t[simulation]{func}')
            else:
                # 再判断是否由engine的成员函数执行
                if self.engine is None:
                    res.msg = ServerReturnMsg.ENGINE_IS_NONE.value
                    res.data = {"error": {"des": "engine is None", "server_url": self.server_url}}
                elif not self.engine.isactive:
                    res.msg = ServerReturnMsg.ENGINE_NOT_ACTIVATE.value
                    res.data = {"error": {"des": "engine not activate", "server_url": self.server_url}}
                elif func in get_member_funcs(self.engine):
                    start_time = time.time()
                    if func not in ['get_simulation_info', 'get_single_statistics']:
                        print(f'{dt.datetime.now().strftime(DATETIME_FMT)}\tFUNC START\t[simulation]{func}')
                    res.data = getattr(self.engine, func)(**kwargs)
                    if func not in ['get_simulation_info', 'get_single_statistics']:
                        print(f'[{self.server_url}] {func} time cost: {time.time() - start_time}')
                        print(f'{dt.datetime.now().strftime(DATETIME_FMT)}\tFUNC END\t[simulation]{func}')
                else:
                    res.msg = ServerReturnMsg.FUNC_NOT_FOUND.value
            return res.grpc_result()
        except:
            if len(request.msg) <= 200:
                print(f'{dt.datetime.now().strftime(DATETIME_FMT)}\t{self.server_url}:\t{request.msg}')
            else:
                print(f'{dt.datetime.now().strftime(DATETIME_FMT)}\t{self.server_url}:\t{request.msg[:200]}')
            traceback.print_exc()
            res.msg = ServerReturnMsg.INTERNAL_ERROR.value
            return res.grpc_result()

    def _update_server_data(self, server_data={}):
        self.user_name = server_data.get('user_name', '')
        self.sim_mode = server_data.get('sim_mode', '')
        self.token = server_data.get('token', '')
        self.engine_name = server_data.get('engine_name', '')

    def clear(self, res=None):
        """ 清空当前的仿真 """
        self.engine = None

        # web 端显示配置
        self.render_config = self.origin_render_config
        self.checkbox_dict = self.origin_checkbox_dict

        # 仿真索引标识
        self._update_server_data()

    def get_engine_url(self, res):
        res.data = f'{self.server_ip}:{self.server_port}'
        return res.grpc_result()

    def render_config_update(self, res, config_type=None, data=None):
        """ 修改前端显示方式 """
        if data is None:
            data = {}
        if config_type == 'checkbox':
            for k, v in data.items():
                self.render_config[self.checkbox_dict[k]['name']] = v
            if self.engine is not None:
                self.engine.render_config.update(self.render_config)
                print(self.engine.render_config)
        elif config_type == 'track':
            self.render_config.update({'history_points_units': [k for k, v in data.items() if v]})
            if self.engine is not None:
                self.engine.render_config.update(self.render_config)
        elif config_type == 'component':
            self.render_config.update({'component_render_units': [k for k, v in data.items() if v]})
            if self.engine is not None:
                self.engine.render_config.update(self.render_config)
        else:
            res.msg = ServerReturnMsg.FUNC_PARAM_ERROR.value

    def set_typical_target_param(self, res, target_rcs=1, target_speed=300, target_height=1000,
                                 target_type='SSMissile'):
        # 设置典型目标参数
        self.render_config.update(
            {"target": {"rcs": target_rcs, "speed": target_speed, "height": target_height, "type_": target_type}})
        if self.engine is not None:
            self.engine.render_config.update(self.render_config)

    def get_default_typical_target_param(self, res):
        # 获取典型目标参数
        if self.engine is None:
            render_config_tmp = self.render_config
        else:
            render_config_tmp = self.engine.render_config
        res.data = render_config_tmp.get('target', {"rcs": 0.1, "speed": 255, "height": 1000, "type_": "SSMissile"})

    def get_checkbox_list(self, res):
        # 获取勾选框列表
        res.data = {k: self.render_config[v['name']] for k, v in self.checkbox_dict.items() if
                    'name' in v and v['name'] in self.render_config}

    def get_script_list(self, res):
        # 获取脚本列表, 支持多级文件夹结构
        res.data = self.script_tree.to_json(mode=SimMode.SINGLE.value)

    def get_gengtu_ip(self, res):
        res.data = self.gengtu_ip
        print(f'get_gengtu_ip: {res.data}')

    def init(self, res, gengtu_ip=None, text='', branch_deduce_data=None, checkpoint_bytes=b'', gen_engine=False,
             update=True, kwargs=None):
        """
        执行流程
        1.判断是否加载 engine 保存文件 .pkl
        1.1 加载 .pkl 文件, 使用分支保存之前的显示配置
        1.2 加载显示配置，生成新 engine, 激活引擎
        2.配置新的分支触发点和分支处理方案
        """
        if branch_deduce_data is None:
            branch_deduce_data = dict()
        if kwargs is None:
            kwargs = dict()

        self._acquire_server_lock("init")

        kwargs['render_config'] = self.render_config
        kwargs['checkbox_dict'] = self.checkbox_dict
        kwargs['user_name'] = res.cmd['user_name']
        kwargs['simserver'] = self
        try:
            # 优先读取保存的 checkpoint
            if checkpoint_bytes:
                assert text
                with open(os.path.join(DIR, "temp.py"), "w", encoding="utf-8") as f:
                    f.write(text)
                import temp
                importlib.reload(temp)
                engine = dill.loads(checkpoint_bytes)
            else:
                if not text:
                    if gen_engine:
                        # 生成一个空的引擎
                        engine = core.engine.Engine(**kwargs)
                        res.data = {'engine_name': engine.name}
                    else:
                        res.msg = ServerReturnMsg.FUNC_PARAM_ERROR.value
                    self._release_server_lock("init1")
                    return
                else:
                    # 根据脚本生成引擎
                    if gengtu_ip != '不显示':
                        kwargs['gengtu_ip'] = gengtu_ip
                    else:
                        kwargs['gengtu_ip'] = None
                    # 生成仿真脚本的完整路径
                    with open(os.path.join(DIR, "temp.py"), "w", encoding="utf-8") as f:
                        f.write(text)
                    import temp
                    importlib.reload(temp)
                    engine = temp.sim(**kwargs)
                    engine.activate()
            checkbox_names = [v['name'] for v in list(self.checkbox_dict.values())]
            new_render_config = {k: v for k, v in engine.render_config.items() if k in checkbox_names and v}
            self.render_config.update(new_render_config)
            self.engine = engine

            if branch_deduce_data:
                self.engine.reset_trigger_handler(branch_deduce_data['engine_name'],
                                                  branch_deduce_data['trigger_names'],
                                                  branch_deduce_data['answer_name'])
                self.engine.simserver = self
                self.engine.restart_update()

            print(f"{self.server_ip}:{self.server_port} [{engine.name}]引擎激活成功")
            res.data = {'engine_name': engine.name}

            if update:  # 是否立即开始更新
                thread = threading.Thread(target=engine.update)
                thread.start()
                print(f"{self.server_ip}:{self.server_port} [{engine.name}]引擎开始运行")

        except Exception as e:
            print('脚本启动失败 ', e)
            traceback.print_exc()
            self.clear()
        finally:
            self._release_server_lock("init")

    def heartbeat(self):
        """ 向 base_server 更新当前仿真状态和数据 """
        self._acquire_server_lock("heartbeat")

        # engine is None 仿真未开始
        # not engine.isactive 仿真结束, 会发送单次仿真结果时的统计数据, 会 执行 self.clear()
        data = {
            "url": self.server_url,
            "user_name": self.user_name,
            "sim_mode": self.sim_mode,
            "token": self.token,
            "engine_name": self.engine_name,
            "state": SimState.RUNNING.value if self.engine is not None and
                                               self.engine.isactive else SimState.STOP.value,
            "engine_terminate_data": self.engine.post_web_statistic_single_data if \
                (self.engine is not None) and (not self.engine.isactive) and \
                (not self.engine.checkpoint_bytes) else None
        }
        # print(self.server_url, data)
        checkpoint_bytes = b''
        if (self.engine is not None) and (not self.engine.isactive):
            if self.engine.checkpoint_bytes:
                checkpoint_bytes = self.engine.checkpoint_bytes
                data['trigger_name'] = self.engine.triggered_name
            self.clear()

        # print(f"[{self.server_url}] {data.get('trigger_name', None)}  {len(checkpoint_bytes)}")
        msg_dict = {
            "flag": "base_server",
            "ip": self.server_ip,
            "source": "SELF",
            "user_name": "SELF",
            "func_name": 'heartbeat',
            "kwargs": {
                "data": data
            }
        }
        msg = json.dumps(msg_dict)
        self._release_server_lock("heartbeat")
        try:
            self.base_client.control(simserver_pb2.MsgStr(msg=msg, bytes_data=checkpoint_bytes), timeout=20)
        except:
            print(f'BaseServer 状态异常(可能是调用SimServer时处于长期阻塞状态)，SimServer[{self.server_url}]退出服务')
            exit(1)

    def _heartbeat_thread(self):
        while True:
            self.heartbeat()
            time.sleep(5)


async def serve(port, base_server_ip, base_server_port):
    server = aio.server(futures.ThreadPoolExecutor(max_workers=20), options=GRPC_OPTIONS)
    servicer = SimServer(port, base_server_ip, base_server_port)
    simserver_pb2_grpc.add_GreeterServicer_to_server(servicer, server)
    server.add_insecure_port(f'0.0.0.0:{port}')
    # 开始接收请求进行服务
    await server.start()
    # 使用 ctrl+c 可以退出服务
    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        await server.stop(None)
    # print(f"端口 {port} 仿真服务器已启动")
    # try:
    #     while True:
    #         time.sleep(1)
    # except KeyboardInterrupt:
    #     server.stop(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='M simulation')
    parser.add_argument("--port", type=int, help="sim_server port", default=6001)
    parser.add_argument("--baseserver_ip", type=str, help="base_server ip", default='127.0.0.1')
    parser.add_argument("--baseserver_port", type=int, help="base_server port", default=6000)
    args = parser.parse_args()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.wait([serve(args.port, args.baseserver_ip, args.baseserver_port)]))
    loop.close()

    # sces = json.load(open(os.path.join(DIR, 'config', "sces.json"), 'r', encoding='utf-8-sig'))
    # script_tree = ScriptTreeNode.load_sces_json(sces)
    # print(script_tree.to_json())
