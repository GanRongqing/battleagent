
"""
仿真结束处理, 状态处理流程
sim_server 结束
-> heartbeat 更新 client 状态 和 single_sim_state 状态 (is_done)
-> (单次仿真 如果超过 client 为该用户保留时间)
    large_sample_thread 释放 client, 更新 mode 状态
"""

import os
import sys
import time
import grpc
import json
import argparse
import datetime as dt
import importlib
import traceback
import threading
from queue import Queue
from concurrent import futures
from threading import Thread, Lock
from multiprocessing import Process
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict, OrderedDict

import simserver_pb2
import simserver_pb2_grpc
from server_config import BaseServerConfig
from client_pool import ClientPool
from sim_result import SimResult
from sim_client import SimClient
from sim_data import LargeSampleData
from enums import ServerReturnMsg, InvalidScriptName, SimMode, SimState
from sim_param import ParallelSimParam, SingleSimParam, BranchDeduceSimParam
from server_state import ServerState, ParallelSimSingleExpState, BranchDeduceSimSingleExpState
from utils import DIR, GRPC_OPTIONS, get_local_ip, get_member_funcs, load_text_file


from simulation import utilities as utl
from simulation import database
from simulation import algorithm
from simulation import core
from simulation import message
from simulation import arsenal

from json_utils import get_branch_answer_dict
import numpy as np
from grpc.experimental import aio
import asyncio


mode_dict = {'全遍历': 'cro', '正交遍历': 'cro', '单组遍历': 'cro', '对齐遍历': 'cro'}

FILTER_FUNC = ["heartbeat", "get_parallel_sim_progress", "get_parallel_state", "get_branch_deduce_sim_progress",
               "get_parallel_simulation_info", "get_parallel_statistics", "get_branch_deduce_simulation_info",
               "get_all_branch_deduce_siming_engines", "get_branch_deduce_statistics", "get_simulation_info",
               "get_single_statistics", "get_red_strikechain_list"]

DATETIME_FMT = "%Y-%m-%d %H:%M:%S"


class BaseServer(simserver_pb2_grpc.GreeterServicer):
    """ 主调度服务 """

    def __init__(self):
        super().__init__()

        self._config = BaseServerConfig()  
        self._server_lock = Lock()  

        self._client_pool = ClientPool(self._config.client_pool_config)

        self._database_json_db = database.DB.json_db  
        self._server_state = ServerState(self._config.server_state_config)  

        self._url_client_dict = dict()  
        self._sim_param_waiting_queue = Queue()  
        self._waiting_stop_client_queue = Queue()  

        self._thread_pool = ThreadPoolExecutor(max_workers=40)

        
        self._large_sample_thread = Thread(target=self._large_sample_thread)
        self._large_sample_thread.start()

        
        self._heartbeat_thread = Thread(target=self._heartbeat_thread)
        self._heartbeat_thread.start()

    def _acquire_server_lock(self, info):
        """获取服务锁"""
        
        
        
        self._server_lock.acquire()

    def _release_server_lock(self, info):
        """释放服务锁"""
        
        
        self._server_lock.release()

    def _grpc_result(self, res, release=True):
        if release and self._server_lock.locked():
            self._release_server_lock('AUTO')
        return res.grpc_result()

    def _authorize(self, cmd, res):
        """ 鉴权 """
        
        source = cmd.get('source', None)
        if not source or source not in self._config.auth_list:
            res.msg = ServerReturnMsg.SOURCE_INVALID.value
            return False
        ip = cmd.get('ip', "")
        if ip == '':
            res.msg = ServerReturnMsg.IP_EMPTY.value
            return False

        
        if source == "gengtu":
            cmd["flag"] = "simulation"
            cmd["user_name"] = "gengtu"
            ip = cmd['ip']
            
            if ip == "192.9.200.5":
                cmd["user_name"] = "gengtu1"
            elif ip == "10.1.24.105":
                cmd["user_name"] = "gengtu2"
            kwargs = cmd.get('params', {})
            func_name = cmd.get('func', None)
            if func_name is None:
                res.msg = ServerReturnMsg.FUNC_IS_NONE.value
                return self._grpc_result(res)
            cmd["func_name"] = func_name
            if func_name == "init":
                kwargs["gengtu_ip"] = ip
                kwargs["kwargs"] = {"web_ip": "192.168.240.20:50051"}
            cmd["kwargs"] = kwargs
            print(cmd)
            res = SimResult(cmd)  

        user_name = cmd.get('user_name', "")
        if user_name == '':
            res.msg = ServerReturnMsg.USER_EMPTY.value
            return False

        func_name = cmd.get('func_name', None)
        if func_name is None:
            res.msg = ServerReturnMsg.FUNC_IS_NONE.value
            return False

        flag = cmd.get("flag", None)
        if flag not in ["base_server", "remote_call", "database", "simulation"]:
            res.msg = ServerReturnMsg.FLAG_ERROR.value
            return False

        return True

    def register_simserver(self, res, url):
        """ 启动的 sim_server 主动注册到 base_server 中 """
        sim_client = SimClient(url)
        self._acquire_server_lock("register_simserver")
        flag = self._client_pool.add(sim_client)
        if flag:
            print(f'{url} SimServer 服务注册成功')
        else:
            print(f'{url} SimServer 服务已经注册')
        self._release_server_lock("register_simserver")
        return self._grpc_result(res)

    def control(self, request, context):
        """ grpc请求入口 """
        cmd = json.loads(request.msg)
        res = SimResult(cmd)
        
        if not self._authorize(cmd, res):
            return self._grpc_result(res, release=False)
        func_name = cmd['func_name']
        flag = cmd['flag']
        user_name = cmd['user_name']

        
        try:
            kwargs = cmd.get('kwargs', {})
            args = cmd.get('args', [])
            if flag == 'base_server':
                if func_name == 'heartbeat':
                    bytes_data = request.bytes_data
                    kwargs['data']['checkpoint_bytes'] = bytes_data

                
                if func_name in get_member_funcs(self):
                    start_time = time.time()
                    if func_name not in FILTER_FUNC:
                        print(f'{dt.datetime.now().strftime(DATETIME_FMT)}\tFUNC START\t[{flag}]{func_name}')
                    getattr(self, func_name)(res, **kwargs)
                    if func_name not in FILTER_FUNC:
                        print(f'{func_name} time cost: {time.time() - start_time}')
                        print(f'{dt.datetime.now().strftime(DATETIME_FMT)}\tFUNC END\t[{flag}]{func_name}')
                    return self._grpc_result(res, release=False)
                else:
                    res.msg = ServerReturnMsg.FUNC_PARAM_ERROR.value
                    return self._grpc_result(res, release=False)

            elif flag == 'remote_call':
                
                library_name = cmd.get('library_name', None)
                if library_name is None or func_name is None:
                    res.msg = ServerReturnMsg.FUNC_PARAM_ERROR.value
                    return self._grpc_result(res, release=False)
                try:
                    print(cmd)
                    remote_func = eval(library_name + '.' + func_name)
                    start_time = time.time()
                    print(f'{dt.datetime.now().strftime(DATETIME_FMT)}\tFUNC START\t[{flag}]{func_name}')
                    if not args:
                        res.data = remote_func(**kwargs)
                    else:
                        res.data = remote_func(*args, **kwargs)
                    print(f'{func_name} time cost: {time.time() - start_time}')
                    print(f'{dt.datetime.now().strftime(DATETIME_FMT)}\tFUNC END\t[{flag}]{func_name}')
                    return self._grpc_result(res, release=False)
                except Exception as e:
                    print(f'func name {func_name} error', e)
                    traceback.print_exc()
                    res.msg = ServerReturnMsg.FUNC_PARAM_ERROR.value
                    return self._grpc_result(res, release=False)

            elif flag == "database":
                
                if func_name in get_member_funcs(database.DB):
                    try:
                        start_time = time.time()
                        print(f'{dt.datetime.now().strftime(DATETIME_FMT)}\tFUNC START\t[{flag}]{func_name}')
                        res.data = getattr(database.DB, func_name)(**kwargs)
                        print(f'{func_name} time cost: {time.time() - start_time}')
                        print(f'{dt.datetime.now().strftime(DATETIME_FMT)}\tFUNC END\t[{flag}]{func_name}')
                        return self._grpc_result(res, release=False)
                    except Exception as e:
                        print(f'func name {func_name} error', e)
                        res.msg = ServerReturnMsg.FUNC_PARAM_ERROR.value
                        return self._grpc_result(res, release=False)
                else:
                    res.msg = ServerReturnMsg.FUNC_PARAM_ERROR.value
                    return self._grpc_result(res, release=False)

            elif flag == 'simulation':
                
                self._acquire_server_lock('simulation')
                state = self._server_state.search(user_name, SimMode.SINGLE.value)
                
                if state is None:
                    assert cmd.get('engine_name', '') == ''
                    client = self._client_pool.get_free_client(SimMode.SINGLE.value)
                    
                    if client is not None:
                        
                        state = self._server_state.create_state(user_name, SimMode.SINGLE.value)
                        state.set_client(client)
                    else:
                        res.msg = ServerReturnMsg.NO_FREE_SERVER.value
                        self._release_server_lock('simulation1')
                        return self._grpc_result(res)
                cmd['server_data'] = {'user_name': user_name, 'sim_mode': SimMode.SINGLE.value}
                client = state.client
                
                if func_name == "init":
                    if client.is_running:
                        
                        res.msg = ServerReturnMsg.ENGINE_SIM_RUNNING.value
                        res.data = {"error": f"用户{user_name}下的单次仿真还未结束"}
                    else:
                        
                        
                        text, config_kwargs = self._process_single_sim_cmd(cmd)
                        if not text:
                            res.msg = ServerReturnMsg.FUNC_PARAM_ERROR.value
                            return
                        single_sim_param = SingleSimParam(cmd, text, config_kwargs=config_kwargs)
                        if cmd['source'] == "gengtu":
                            def func():
                                
                                client.push_req(**(single_sim_param.start_sim_req_param))

                            thread = threading.Thread(target=func)
                            thread.start()
                            res.msg = ServerReturnMsg.ENGINE_ACTIVATE_THREAD.value
                        else:
                            response = client.push_req(**(single_sim_param.start_sim_req_param))
                            res.load_response(response)
                        state.is_done = False
                        client.state = SimState.RUNNING.value
                else:
                    
                    
                    if cmd['source'] == "gengtu":
                        def func():
                            client.push_req(json.dumps(cmd))

                        thread = threading.Thread(target=func)
                        thread.start()
                        res.msg = ServerReturnMsg.ENGINE_ACTIVATE_THREAD.value
                    else:
                        response = client.push_req(json.dumps(cmd))  
                        res.load_response(response)
                self._release_server_lock('simulation2')
                return self._grpc_result(res)
            else:
                res.msg = ServerReturnMsg.FLAG_ERROR.value
                return self._grpc_result(res, release=False)
        except Exception as e:
            traceback.print_exc()
            print(f'错误请求: ', cmd[:200])
            res.msg = ServerReturnMsg.INTERNAL_ERROR.value
            return self._grpc_result(res)

    def _process_single_sim_cmd(self, cmd):
        text = ''
        fname = cmd.get('kwargs', {}).get('fname', '')
        if not fname:
            return text
        cmd['engine_name'] = fname
        param_dict = self._config.sces.get(fname, {})
        fpath = param_dict.get('fpath', None)
        kwargs = param_dict.get('kwargs', {})
        if not fpath:
            return text
        if os.path.isabs(fpath):
            fullpath = fpath
        else:
            fullpath = os.path.join(DIR, fpath)
        with open(fullpath, "r", encoding="utf-8") as f:
            text = f.read()
        return text, kwargs

    def _get_all_sim_scripts(self, res, mode):
        """ 获取所有支持大样本仿真的仿真脚本名称 """
        res.data = {'scripts': self._config.script_tree.to_json(mode=mode)}
        return self._grpc_result(res, release=False)

    def load_json_db(self, res):
        res.data = self._database_json_db

    def _load_parallel_reducer(self, reducer_text):
        """加载 reducer"""
        reducer = None
        if reducer_text:
            with open('temp1.py', "w", encoding="utf-8") as f:
                f.write(reducer_text)
            import temp1
            importlib.reload(temp1)
            try:
                from temp1 import reducer
            except:
                pass
        return reducer

    def _load_branch_deduce_reducer(self, reducer_text):
        """加载 reducer"""
        reducer = None
        compare_reducer = None
        if reducer_text:
            with open('temp1.py', "w", encoding="utf-8") as f:
                f.write(reducer_text)
            import temp1
            importlib.reload(temp1)
            try:
                from temp1 import reducer, compare_reducer
            except:
                pass
        return reducer, compare_reducer

    def _remove_param_waiting_queue(self, user_name, sim_mode, token):
        tmp_queue = Queue()
        while not self._sim_param_waiting_queue.empty():
            sim_param = self._sim_param_waiting_queue.get()
            if sim_param.token == token:
                
                if sim_param.user_name != user_name or sim_param.sim_mode != sim_mode:
                    print('warning: 要停止的token对应的仿真模式或用户名错误')
                    tmp_queue.put(sim_param)
            else:
                tmp_queue.put(sim_param)
        self._sim_param_waiting_queue = tmp_queue

    def _get_large_sample_state(self, res, sim_mode):
        """ 指定的用户是否正在大样本仿真 """
        user_name = res.cmd["user_name"]  
        self._acquire_server_lock('get_large_sample_state')
        state = self._server_state.search(user_name, sim_mode)
        flag = False
        if state is not None:
            flag = state.is_running
        res.data = {'running': flag}
        self._release_server_lock('get_large_sample_state')
        return self._grpc_result(res)

    def get_parallel_state(self, res):
        """ 指定的用户是否正在并行仿真 """
        return self._get_large_sample_state(res, SimMode.PARALLEL.value)

    def get_branch_deduce_state(self, res):
        """ 指定的用户是否正在并行仿真 """
        return self._get_large_sample_state(res, SimMode.BRANCH_DEDUCE.value)

    def get_all_branch_deduce_sim_scripts(self, res):
        """ 获取所有支持大样本仿真的仿真脚本名称 """
        return self._get_all_sim_scripts(res, mode=SimMode.BRANCH_DEDUCE.value)

    def get_all_parallel_sim_scripts(self, res):
        """ 获取所有支持大样本仿真的仿真脚本名称 """
        return self._get_all_sim_scripts(res, mode=SimMode.PARALLEL.value)

    def get_parallel_sim_script_params(self, res, script):
        """ 获取指定仿真脚本名称对应的仿真可变化参数信息"""
        if not self._config.script_tree.search(script, mode=SimMode.PARALLEL.value):
            res.msg = ServerReturnMsg.FUNC_PARAM_ERROR.value
        else:
            res.data = self._config.sces[script]['parallel_param_constraint']
        return self._grpc_result(res, release=False)

    def get_parallel_sim_progress(self, res, token=None):
        """ 获取当前用户并行仿真整体进度, 或者指定单次并行仿真实验的进度"""
        self._acquire_server_lock("get_parallel_sim_progress")

        user_name = res.cmd["user_name"]  
        if token is not None:
            state = self._server_state.search(user_name, SimMode.PARALLEL.value, token)
        else:
            state = self._server_state.search(user_name, SimMode.PARALLEL.value)
        if state is not None:
            data = state.sim_progress
            res.data = {'data': data}
        else:
            res.msg = ServerReturnMsg.LARGE_SAMPLE_SIM_NOT_RUNNING.value
        self._release_server_lock("get_parallel_sim_progress")

        return self._grpc_result(res)

    def _get_parallel_sim_reduce_result(self, res, token, mode):
        user_name = res.cmd["user_name"]
        state = self._server_state.search(user_name, SimMode.PARALLEL.value, token)
        if state is None:
            res.msg = ServerReturnMsg.FUNC_PARAM_ERROR.value
            return
        
        if mode == 'process_data':
            res.data = state.process_data
        elif mode == 'save_data':
            res.data = state.save_data
        else:
            res.data = state.terminate_data

    def get_parallel_sim_reduce_save_result(self, res, token):
        """ 显示大样本仿真过程中web上上显的数据(需符合echarts格式) """
        self._acquire_server_lock("get_parallel_sim_reduce_save_result")
        self._get_parallel_sim_reduce_result(res, token, 'save_data')
        self._release_server_lock("get_parallel_sim_reduce_save_result")

        return self._grpc_result(res)

    def get_parallel_sim_reduce_process_result(self, res, token):
        """ 显示大样本仿真过程中web上上显的数据(需符合echarts格式) """
        self._acquire_server_lock("get_parallel_sim_reduce_process_result")
        self._get_parallel_sim_reduce_result(res, token, 'process_data')
        self._release_server_lock("get_parallel_sim_reduce_process_result")

        return self._grpc_result(res)

    def get_parallel_sim_reduce_tarminate_result(self, res, token):
        """ 获取大样本仿真结果数据 """
        self._acquire_server_lock("get_parallel_sim_reduce_tarminate_result")
        self._get_parallel_sim_reduce_result(res, token, 'terminate_data')
        self._release_server_lock("get_parallel_sim_reduce_tarminate_result")
        return self._grpc_result(res)

    def get_all_parallel_siming_engines(self, res, token=None):
        """ 查询该用户正在并行仿真的引擎 """
        self._acquire_server_lock("get_all_parallel_siming_engines")
        user_name = res.cmd.get("user_name", "")
        if token is not None:
            state = self._server_state.search(user_name, SimMode.PARALLEL.value, token)
            if state is None:
                res.data = dict()
            else:
                res.data = {k: token for k in state.running_state.keys()}
        else:
            state = self._server_state.search(user_name, SimMode.PARALLEL.value)
            if state is None:
                res.data = dict()
            else:
                res_d = {}
                for token, single_exp_state in state.single_exp_state_dict.items():
                    res_d.update({k: token for k in single_exp_state.running_state.keys()})
                res.data = res_d
        self._release_server_lock("get_all_parallel_siming_engines")
        return self._grpc_result(res)

    def get_all_parallel_siming_tokens(self, res):
        """ 显示该用户所有的大样本仿真任务(token) """
        self._acquire_server_lock("get_all_parallel_siming_tokens")
        user_name = res.cmd.get("user_name", "")
        state = self._server_state.search(user_name, SimMode.PARALLEL.value)
        if state is None:
            res.data = {'tokens': []}
        else:
            res.data = {'tokens': list([k for k, v in state.single_exp_state_dict.items() \
                                        if v.is_running])}
        self._release_server_lock("get_all_parallel_siming_tokens")
        return self._grpc_result(res)

    def get_all_branch_deduce_siming_engines(self, res, token=None):
        """ 查询该用户正在并行仿真的引擎 """
        self._acquire_server_lock("get_all_branch_deduce_siming_engines")
        user_name = res.cmd.get("user_name", "")
        if token is not None:
            state = self._server_state.search(user_name, SimMode.BRANCH_DEDUCE.value, token)
            if state is None:
                res.data = dict()
            else:
                res.data = {node.engine_name: token for node in state.iter_node() \
                            if node.state and not node.state.is_done}

        else:
            state = self._server_state.search(user_name, SimMode.BRANCH_DEDUCE.value)
            if state is None:
                res.data = dict()
            else:
                res_d = {}
                for token, single_exp_state in state.single_exp_state_dict.items():
                    res_d.update({node.engine_name: token for node in single_exp_state.iter_node() \
                                  if node.state and not node.state.is_done})
                res.data = res_d
        self._release_server_lock("get_all_branch_deduce_siming_engines")
        return self._grpc_result(res)

    def _get_recent_large_sample_sim_tokens(self, res, mode):
        """ 显示该用户最近的大样本仿真任务(token)

        最近的定义为正在运行的任务或任务结束(未更新)在1小时之内
        """
        self._acquire_server_lock("get_recent_parallel_sim_tokens")
        user_name = res.cmd['user_name']
        state = self._server_state.search(user_name, mode)
        if state is None:
            res.data = {'tokens': []}
        else:
            res.data = {'tokens': list([k for k, v in state.single_exp_state_dict.items() \
                                        if time.time() - v.last_update_time < self._config.recent_parallel_time_thres])}
        self._release_server_lock("get_recent_parallel_sim_tokens")
        return self._grpc_result(res)

    def get_recent_parallel_sim_tokens(self, res):
        """ 显示该用户最近的大样本仿真任务(token) """
        return self._get_recent_large_sample_sim_tokens(res, SimMode.PARALLEL.value)

    def get_recent_branch_deduce_sim_tokens(self, res):
        """ 显示该用户最近的分支推演任务(token) """
        return self._get_recent_large_sample_sim_tokens(res, SimMode.BRANCH_DEDUCE.value)

    def get_branch_deduce_sim_progress(self, res, token):
        """ 显示分支推演进程 """
        self._acquire_server_lock("get_branch_deduce_sim_progress")
        user_name = res.cmd['user_name']
        state = self._server_state.search(user_name, SimMode.BRANCH_DEDUCE.value, token)
        if state is None:
            res.msg = ServerReturnMsg.FUNC_PARAM_ERROR.value
        else:
            res.data = {'data': state.sim_progress}
        self._release_server_lock("get_branch_deduce_sim_progress")
        return self._grpc_result(res)

    def get_branch_deduce_reduce_result(self, res, token, engine_names):
        self._acquire_server_lock("get_branch_deduce_reduce_result")
        user_name = res.cmd['user_name']
        state = self._server_state.search(user_name, SimMode.BRANCH_DEDUCE.value, token)
        if state is None:
            res.msg = ServerReturnMsg.FUNC_PARAM_ERROR.value
        else:
            res.data = {'data': state.reduce(engine_names)}
        self._release_server_lock("get_branch_deduce_reduce_result")
        return self._grpc_result(res)

    def get_branch_deduce_reduce_result_for_yuanhai(self, res, token):
        self._acquire_server_lock("get_branch_deduce_reduce_result_for_yuanhai")
        user_name = res.cmd['user_name']
        state = self._server_state.search(user_name, SimMode.BRANCH_DEDUCE.value, token)
        if state is None:
            res.msg = ServerReturnMsg.FUNC_PARAM_ERROR.value
        else:
            
            res.data = {"done": not state.is_running, "effect": []}
            
            if not state.is_running:
                
                trigger_dict = {
                    "trigger1-answer1": ("branch_1_answer", "0"), "trigger1-answer2": ("branch_1_answer", "1"),
                    "trigger1-answer3": ("branch_1_answer", "2"), "trigger2-answer4": ("branch_3_answer", "0"),
                    "trigger2-answer5": ("branch_3_answer", "1"), "trigger2-answer6": ("branch_3_answer", "2"),
                }
                
                progress = state.sim_progress
                
                weights_map = {
                    "intercept_max": [0.35, 0.35, -0.1, -0.1, 0.1],
                    "lose_min": [0.1, 0.1, -0.35, -0.35, 0.1],
                    "balance": [0.2, 0.2, -0.2, -0.2, 0.2]
                }
                
                weight = weights_map["balance"]
                
                trigger1_data = progress.get("children", [])
                for trigger1 in trigger1_data:
                    branch1_key, branch1_value = trigger_dict[f"{trigger1['name']}-{trigger1['value']}"]
                    
                    trigger2_data = trigger1.get("children", [])
                    for trigger2 in trigger2_data:
                        branch3_key, branch3_value = trigger_dict[f"{trigger2['name']}-{trigger2['value']}"]
                        
                        trigger2_engine_name = trigger2["engine_name"]
                        
                        state_node = state.search(trigger2_engine_name)
                        
                        terminate_data = state_node.terminate_data['data'][0][0]['series'][0]['data']
                        
                        scores = weight * np.array(terminate_data)
                        score = round(scores[:].sum(), 2)
                        res.data['effect'].append({
                            branch1_key: branch1_value, "branch_2_answer": "none", branch3_key: branch3_value,
                            "intercept_missile_num": terminate_data[0], "intercept_plane_num": terminate_data[1],
                            "lose_plane_num": terminate_data[2], "lose_ship_num": terminate_data[3],
                            "shoot_missile_num": terminate_data[4], "score": score
                        })
                effect_list = res.data['effect']
                res.data['effect'] = sorted(effect_list, key=lambda e: e["score"], reverse=True)
        self._release_server_lock("get_branch_deduce_reduce_result_for_yuanhai")
        return self._grpc_result(res)

    def _get_large_sample_simulation_info(self, res, user_name, sim_mode, token, engine_name):
        """ 获取大样本仿真实时态势"""
        state = self._server_state.search(user_name, sim_mode, token, engine_name)
        if state and state.client is not None:
            

            future = self._thread_pool.submit(state.client.get_simulation_info)
            response = future.result()
            res.load_response(response)
        else:
            res.msg = ServerReturnMsg.FUNC_PARAM_ERROR.value
        return res

    def get_parallel_simulation_info(self, res, token, engine_name):
        """ 获取并行仿真实时态势"""
        user_name = res.cmd['user_name']
        return self._get_large_sample_simulation_info(res, user_name, SimMode.PARALLEL.value, token, engine_name)

    def get_branch_deduce_simulation_info(self, res, token, engine_name):
        """ 获取分支推演实时态势"""
        user_name = res.cmd['user_name']
        return self._get_large_sample_simulation_info(res, user_name, SimMode.BRANCH_DEDUCE.value, token, engine_name)

    def _get_large_sample_statistics(self, res, user_name, sim_mode, token, engine_name):
        """ 获取大样本仿真实时数据"""
        state = self._server_state.search(user_name, sim_mode, token, engine_name)
        if state and state.client is not None:
            response = state.client.get_single_statistics()
            res.load_response(response)
        else:
            res.msg = ServerReturnMsg.FUNC_PARAM_ERROR.value
        return res

    def get_parallel_statistics(self, res, token, engine_name):
        """ 获取并行仿真实时数据"""
        user_name = res.cmd['user_name']
        return self._get_large_sample_statistics(res, user_name, SimMode.PARALLEL.value, token, engine_name)

    def get_branch_deduce_statistics(self, res, token, engine_name):
        """ 获取并行仿真实时数据"""
        user_name = res.cmd['user_name']
        return self._get_large_sample_statistics(res, user_name, SimMode.BRANCH_DEDUCE.value, token, engine_name)

    def start_branch_deduce_sim_for_yuanhai(self, res, script_name='', script_text='', reducer_text='',
                                            max_running_engine_num=0, yuanhai_plan_json=None, origin_reduce_data=None,
                                            kwargs=None):
        """
        对于前台传过来的json数据按照branch_deduce_plan需要的格式进行封装
        Args:
            res: object
            script_name: str
            script_text: str
            reducer_text: str
            max_running_engine_num: int
            yuanhai_plan_json: obj
            origin_reduce_data: obj
            kwargs: obj
        Returns:

        """
        if kwargs is None:
            kwargs = {}

        assert yuanhai_plan_json is not None, '分支推演情况下json地址不能为空'
        branch_deduce_param = get_branch_answer_dict(yuanhai_plan_json)
        self.start_branch_deduce_sim(res, script_name=script_name, script_text=script_text, reducer_text=reducer_text,
                                     max_running_engine_num=max_running_engine_num,
                                     branch_deduce_param=branch_deduce_param, origin_reduce_data=origin_reduce_data,
                                     kwargs=kwargs)

    def _check_branch_deduce_param_constraint(self, data, constraint):
        """检查分支推演参数满足约束"""
        for n in data:
            if n not in constraint:
                return False
        return True

    def start_branch_deduce_sim(self, res, script_name='', branch_deduce_param=None, script_text='', reducer_text='',
                                origin_reduce_data=None, max_running_engine_num=0, kwargs=None):
        if kwargs is None:
            kwargs = {}

        self._acquire_server_lock("start_branch_deduce_sim")
        print(res.cmd)
        
        timestamp = dt.datetime.now().strftime("%Y%m%d%H%M%S")
        user_name = res.cmd['user_name']
        token = f'{script_name}_{timestamp}'

        
        if script_name and self._config.script_tree.search(script_name, mode=SimMode.BRANCH_DEDUCE.value):
            script_data = self._config.sces[script_name]
            default_kwargs = script_data.get('kwargs', dict())
            param_constraint = script_data['branch_deduce_param_constraint']
            default_branch_deduce_param = script_data['default_branch_deduce_param']
        else:
            script_data = dict()
            default_kwargs = dict()
            param_constraint = dict()
            default_branch_deduce_param = dict()
        print(script_data)

        
        if not branch_deduce_param:
            branch_deduce_param = default_branch_deduce_param
        tmp_kwargs = {}
        for k, v in default_kwargs.items():
            if k not in kwargs:
                tmp_kwargs[k] = v
        kwargs.update(tmp_kwargs)

        
        if not script_text:
            fpath = script_data.get('fpath', None)
            if fpath is None:
                res.msg = ServerReturnMsg.FUNC_PARAM_ERROR.value
                self._release_server_lock("start_branch_deduce_sim1")
                return self._grpc_result(res)
            script_text = load_text_file(fpath)
            for k, v in script_data.get('kwargs', {}).items():
                if not k in kwargs:
                    kwargs[k] = v

        
        if reducer_text == '':
            reducer_path = script_data.get('reducer_path', None)
            if reducer_path:
                reducer_text = load_text_file(reducer_path)
        reducer, compare_reducer = \
            self._load_branch_deduce_reducer(reducer_text)

        
        for k, v in branch_deduce_param.items():
            if (not k in param_constraint) or (not isinstance(v, list)):
                res.msg = ServerReturnMsg.FUNC_PARAM_ERROR.value
                self._release_server_lock("start_branch_deduce_sim2")
                return self._grpc_result(res)
            if self._check_branch_deduce_param_constraint(v, param_constraint[k]):
                continue
            else:
                res.msg = ServerReturnMsg.FUNC_PARAM_ERROR.value
                self._release_server_lock("start_branch_deduce_sim3")
                return self._grpc_result(res)

        trigger_names = [k for k in branch_deduce_param.keys()]
        self._sim_param_waiting_queue.put(
            BranchDeduceSimParam(res.cmd, token, script_text, branch_deduce_param, kwargs,
                                 trigger_names=trigger_names))

        engine_num = max_running_engine_num if max_running_engine_num > 0 \
            else self._config.large_sample_engine_num_per_user
        single_exp_state = BranchDeduceSimSingleExpState(script_name=script_name, max_running_engine_num=engine_num,
                                                         reducer=reducer, compare_reducer=compare_reducer,
                                                         origin_reduce_data=origin_reduce_data)
        state = self._server_state.search(user_name, SimMode.BRANCH_DEDUCE.value)
        if state is None:
            state = self._server_state.create_state(user_name, SimMode.BRANCH_DEDUCE.value)
        state.add_state(token, single_exp_state)
        res.data = {'token': token}
        self._release_server_lock("start_branch_deduce_sim")
        return self._grpc_result(res)

    def stop_branch_deduce_sim(self, res, token):
        """ 停止指定的大样本仿真任务, 可以停止并行仿真任务和分支推演仿真任务"""
        return self._stop_large_sample_sim(res, SimMode.BRANCH_DEDUCE.value, token)

    def _check_parallel_param_constraint(self, param_type, data, constraint):
        """检查并行仿真参数满足约束"""
        if param_type in ['int', 'float']:
            for n in data:
                if n < constraint[0] or n > constraint[1]:
                    return False
        else:
            for n in data:
                if n not in constraint:
                    return False
        return True

    def start_parallel_sim(self, res, script_name="", param_data=None, exp_method='全遍历', single_group_exp_num=1,
                           script_text='', reducer_text='', max_running_engine_num=0, origin_reduce_data=None,
                           kwargs=None):
        """ 并行仿真调度
        Args:
            param_data: 需要变化的参数及变化的值
            single_group_exp_num 及其上面的参数提供给web端配置, 后面的参数只用于开发者手动启动并行仿真使用
            参数使用优先级: 手动配置的遍历参数 param_data > 手动配置的指定参数 kwargs > 配置文件中的默认参数 kwargs
        """
        if kwargs is None:
            kwargs = {}
        if param_data is None:
            param_data = {}

        self._acquire_server_lock('start_parallel_sim')
        
        timestamp = dt.datetime.now().strftime("%Y%m%d%H%M%S")
        user_name = res.cmd['user_name']
        token = f'{script_name}_{timestamp}'

        
        if script_name and self._config.script_tree.search(script_name, mode=SimMode.PARALLEL.value):
            script_data = self._config.sces[script_name]
            default_kwargs = script_data.get('kwargs', dict())
            param_constraint = script_data['parallel_param_constraint']
        else:
            script_data = dict()
            default_kwargs = dict()
            param_constraint = dict()

        
        param_data = OrderedDict(param_data)
        tmp_kwargs = {}
        for k, v in kwargs.items():
            if k not in param_data:
                tmp_kwargs[k] = v
        for k, v in default_kwargs.items():
            if k not in param_data and k not in tmp_kwargs:
                tmp_kwargs[k] = v
        kwargs = tmp_kwargs
        if not script_text:
            fpath = script_data.get('fpath', None)
            if fpath is None:
                res.msg = ServerReturnMsg.FUNC_PARAM_ERROR.value
                self._release_server_lock("start_parallel_sim1")
                return self._grpc_result(res)
            script_text = load_text_file(fpath)
            for k, v in script_data.get('kwargs', {}).items():
                if not k in kwargs:
                    kwargs[k] = v

        
        if reducer_text == '':
            reducer_path = script_data.get('reducer_path', None)
            if reducer_path:
                reducer_text = load_text_file(reducer_path)
        reducer = self._load_parallel_reducer(reducer_text)
        
        param_values = []
        for k, v in param_data.items():
            if (not k in param_constraint) or (not isinstance(v, list)):
                res.msg = ServerReturnMsg.FUNC_PARAM_ERROR.value
                self._release_server_lock("start_parallel_sim2")
                return self._grpc_result(res)
            if len(v) == 0:
                continue
            param_type = param_constraint[k]['type']
            if self._check_parallel_param_constraint(param_type, v, param_constraint[k]['value']):
                param_values.append(v)
            else:
                res.msg = ServerReturnMsg.FUNC_PARAM_ERROR.value
                self._release_server_lock("start_parallel_sim3")
                return self._grpc_result(res)

        
        paras = utl.design.generate_para(*param_values, mode=mode_dict[exp_method], times=1)
        large_sample_sim_num = 0
        if paras:
            for para in paras:
                param_dict = {}
                for param_name, value in zip(list(param_data.keys()), para):
                    param_dict[param_name] = value
                kwargs.update(param_dict)
                for i in range(single_group_exp_num):
                    self._sim_param_waiting_queue.put(
                        ParallelSimParam(res.cmd, token, script_text, kwargs, i + 1))
                    large_sample_sim_num += 1
        else:
            
            for i in range(single_group_exp_num):
                self._sim_param_waiting_queue.put(
                    ParallelSimParam(res.cmd, token, script_text, kwargs, i + 1))
                large_sample_sim_num += 1

        engine_num = max_running_engine_num if max_running_engine_num > 0 \
            else self._config.large_sample_engine_num_per_user
        single_exp_state = ParallelSimSingleExpState(script_name=script_name, all_num=large_sample_sim_num,
                                                     max_running_engine_num=engine_num, reducer=reducer,
                                                     origin_reduce_data=origin_reduce_data)
        state = self._server_state.search(user_name, SimMode.PARALLEL.value)
        if state is None:
            state = self._server_state.create_state(user_name, SimMode.PARALLEL.value)
        state.add_state(token, single_exp_state)
        res.data = {'token': token}
        self._release_server_lock("start_parallel_sim")
        return self._grpc_result(res)

    def stop_parallel_sim(self, res, token):
        """ 停止指定的大样本仿真任务, 可以停止并行仿真任务和分支推演仿真任务"""
        return self._stop_large_sample_sim(res, SimMode.PARALLEL.value, token)

    def _stop_large_sample_sim(self, res, sim_mode, token):
        """ 停止指定的大样本仿真任务, 可以停止并行仿真任务和分支推演仿真任务
            Args:
                token: 单次实验唯一标识
        """
        self._acquire_server_lock('stop_parallel_sim')
        user_name = res.cmd.get("user_name", "")
        
        self._remove_param_waiting_queue(user_name, sim_mode, token)

        
        state = self._server_state.search(user_name, sim_mode)
        single_clients = state.stop(token)
        if not single_clients:
            res.msg = ServerReturnMsg.LARGE_SAMPLE_SIM_NOT_RUNNING.value
            self._release_server_lock("stop_parallel_sim1")
            return self._grpc_result(res)
        for client in single_clients:
            self._waiting_stop_client_queue.put(client)
        self._release_server_lock("stop_parallel_sim")
        return self._grpc_result(res)

    def show_sim_state(self, res):
        self._acquire_server_lock('show_sim_state')
        res.data = self._server_state.show()
        self._release_server_lock("show_sim_state")
        return self._grpc_result(res)

    def show_server_state(self, res):
        """查看当前仿真引擎数据"""
        self._acquire_server_lock("show_server_state")

        res.data = {
            'free_client_num': self._client_pool.free_num,
            'busy_client_num': len(self._client_pool) - self._client_pool.free_num,
            'server_data': [{'url': client.url, 'mode': client.mode, 'state': client.state,
                             'heartbeat_last_update_time': client.heartbeat_last_update_time} for _, client in
                            self._client_pool.items()]
        }

        self._release_server_lock("show_server_state")
        return self._grpc_result(res)

    def _large_sample_thread(self):
        
        while True:
            self._acquire_server_lock('large_sample_thread')

            
            token_running_num = defaultdict(int)  
            sim_end_args = []
            for user_name, sim_mode, token, engine_name, single_state in self._server_state.iter_state():
                if not single_state.is_done:
                    token_running_num[token] += 1
                    state = self._server_state.search(user_name, sim_mode, token)
                    state.update_state_time()
                else:
                    sim_end_args.append([user_name, sim_mode, token, engine_name])
            for arg in sim_end_args:
                res = self._server_state.process_sim_end(*arg)
                
                if arg[1] == SimMode.BRANCH_DEDUCE.value:
                    for sim_param in res['sim_params']:
                        self._sim_param_waiting_queue.put(sim_param)

            
            
            if not self._waiting_stop_client_queue.empty():
                client = self._waiting_stop_client_queue.get()
                
                if client.mode != SimMode.FREE.value:
                    client.stop_engine()
                    client.mode = SimMode.FREE.value
                    client.state = SimState.STOP.value
            else:
                
                client = self._client_pool.get_free_client(SimMode.PARALLEL.value)
                if client is not None:
                    tmp_sim_param_queue = Queue()
                    
                    if not self._sim_param_waiting_queue.empty():
                        sim_param = self._sim_param_waiting_queue.get()
                        
                        state = self._server_state.search(sim_param.user_name, sim_param.sim_mode, sim_param.token)
                        max_running_engine_num = state.max_running_engine_num
                        
                        if token_running_num[sim_param.token] >= max_running_engine_num:
                            tmp_sim_param_queue.put(sim_param)
                        else:
                            response = client.push_req(**sim_param.start_sim_req_param)
                            if response.msg == "FUNC_SUCCESS":
                                state.add_client(sim_param.engine_name, client, sim_param)
                                client.state = SimState.RUNNING.value
                                client.mode = sim_param.sim_mode
                            else:
                                print(f"大样本仿真[{sim_param.token}][{sim_param.engine_name}]下单次仿真启动失败，"
                                      f"具体结果为[{response.msg}]")
                                print(f"跳过该单次仿真任务")
                                tmp_sim_param_queue.put(sim_param)
                    
                    while not self._sim_param_waiting_queue.empty():
                        sim_param = self._sim_param_waiting_queue.get()
                        tmp_sim_param_queue.put(sim_param)
                    self._sim_param_waiting_queue = tmp_sim_param_queue

            
            self._server_state.update_state()

            self._release_server_lock("large_sample_thread")
            time.sleep(1)

    def heartbeat(self, res, data):
        """ SimServer 定期向 BaseServer 发送仿真状态和信息 """
        self._acquire_server_lock("heartbeat")
        url = res.cmd['kwargs']['data']['url']
        self._client_pool.update_state(url)
        state = self._server_state.search(data['user_name'], data['sim_mode'])
        
        
        
        if state is not None:
            if data['sim_mode'] == SimMode.SINGLE.value:
                
                state.update_state(data)
            else:
                
                
                single_exp_state = state.search(data['token'])
                
                
                if single_exp_state is not None and data['engine_name']:
                    single_state = single_exp_state.search(data['engine_name'])
                    assert single_state is not None, print(data['token'], data['engine_name'],
                                                           self._server_state.show())
                    single_state.update_state(data)
        self._release_server_lock('heartbeat')

    def _heartbeat_thread(self):
        
        while True:
            
            self._acquire_server_lock("_heartbeat_thread")
            del_url = []
            for url, client in self._client_pool.items():
                if time.time() - client.heartbeat_last_update_time > \
                        self._config.simserver_delete_time_thres:
                    del_url.append(url)
            for url in del_url:
                self._client_pool.remove(url)
            self._release_server_lock("_heartbeat_thread")
            time.sleep(10)


async def serve(ip, port):
    server = aio.server(futures.ThreadPoolExecutor(max_workers=40), options=GRPC_OPTIONS)
    servicer = BaseServer()
    simserver_pb2_grpc.add_GreeterServicer_to_server(servicer, server)
    server.add_insecure_port(f'{ip}:{port}')
    
    await server.start()
    
    print(f"端口 {port} 仿真服务器已启动")
    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        await server.stop(None)
    
    
    
    
    


def start_base_server(ip, port):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.wait([serve(ip, port)]))
    loop.close()


def start_sim_server(sim_server_port, base_server_ip, base_server_port):
    os.system(f'{sys.executable} sim_server.py --port {sim_server_port} --baseserver_ip {base_server_ip} '
              f'--baseserver_port {base_server_port}')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='M simulation')
    parser.add_argument("--ip", type=str, help="simulation params", default="0.0.0.0")
    parser.add_argument("--port", type=int, help="simulation params", default=6000)
    parser.add_argument("--min_simserver_port", type=int, help="min_simserver_port", default=6001)
    parser.add_argument("--simserver_num", type=int, help="simserver_num", default=5)
    parser.add_argument("--only_start_simserver", type=bool, help="simulation iter", default=False)
    args = parser.parse_args()

    
    if not args.only_start_simserver:
        base_server_ip = get_local_ip()
        p = Process(target=start_base_server, args=(args.ip, args.port,))
        p.start()
    else:
        base_server_ip = args.ip
    
    server_ports = list(range(args.min_simserver_port, args.min_simserver_port + args.simserver_num, 1))
    for port in server_ports:
        p = Process(target=start_sim_server, args=(port, base_server_ip, args.port,))
        p.start()
        time.sleep(0.5)
