import time
import json
from copy import deepcopy
from queue import Queue
from simserver.enums import SimMode, SimState
from collections import defaultdict
from simserver.sim_param import BranchDeduceSimParam

def get_branch_history(engine_name):
    res = []
    engine_name_data = engine_name.split('@')
    assert len(engine_name_data) == 4 and \
        engine_name_data[1] == SimMode.BRANCH_DEDUCE.value, print(engine_name, engine_name_data)
    history = engine_name_data[2].split('#')
    for h in history:
        h_d = h.split('^')
        if len(h_d) == 2:
            res.append(h_d)
    return res

class SingleSimState:
    '''单次仿真模式仿真状态'''
    def __init__(self, client=None, sim_param=None):
        self.client = client
        self.sim_param = sim_param
        self.terminate_data = {}
        # 仿真结束置为 True, 和 is_running 的区分在于仿真开始后, 接受到
        # sim_server 的心跳包后 is_running才会置为 True
        self.is_done = False                    
        self.trigger_name = ''                  # 本次单次仿真触发的 trigger 名称
        self.checkpoint_bytes = b''             # 分支推演触发保存状态
        self.last_update_time = time.time()     # 上次仿真结束的时间的时间

    @property
    def is_running(self):
        return self.client.is_running if self.client else False

    def show(self):
        return {'last_update_time': self.last_update_time,
                'is_done': self.is_done,
                'terminate_data': len(self.terminate_data) > 0}

    def set_client(self, client):
        self.client = client

    def process_sim_end(self, clear_client_flag=True):
        # 单次仿真在 server_state 层次上判断空闲时间，如果过长直接清空
        self.last_update_time = time.time()
        if clear_client_flag:
            self.clear_client()

    def clear_client(self):
        self.client.mode = SimMode.FREE.value
        self.client = None
    
    def update_state(self, data):
        if self.is_running and data['state'] == SimState.STOP.value: 
            self.is_done = True
        if self.client:
            self.client.update_state(data['state'])
        if not self.terminate_data and data.get('engine_terminate_data', None):
            self.terminate_data = data['engine_terminate_data']
        if not self.trigger_name and data.get('trigger_name', None):
            self.trigger_name = data['trigger_name']
        if data.get('checkpoint_bytes', b''):
            self.checkpoint_bytes = data['checkpoint_bytes']

class LargeSampleSimState:
    ''' 并行仿真和分支推演使用'''
    def __init__(self):
        self.single_exp_state_dict = dict() # token: SingleExpState

    @property
    def is_running(self):
        for k, v in self.single_exp_state_dict.items():
            if v.is_running:
                return True
        return False

    def show(self):
        return {k: v.show() for k, v in self.single_exp_state_dict.items()}

    def add_state(self, token, single_exp_state):
        assert token not in self.single_exp_state_dict
        self.single_exp_state_dict[token] = single_exp_state

    def search(self, token, engine_name=None):
        state = self.single_exp_state_dict.get(token, None)
        if state is None or engine_name is None:
            return state
        res = state.search(engine_name)
        return res

    def process_sim_end(self, token, engine_name):
        single_exp_state = self.single_exp_state_dict[token]
        return single_exp_state.process_sim_end(engine_name)
    
    def stop(self, token):
        state = self.search(token)
        if state is None or not state.is_running:
            return []
        waiting_stop_clients = state.stop()
        self.single_exp_state_dict.pop(token)
        return waiting_stop_clients

class ParallelSimState(LargeSampleSimState):
    ''' 并行仿真任务状态 '''
    # 管理一个用户执行的所有并行仿真任务
    @property
    def sim_progress(self):
        data = defaultdict(int)
        for state in self.single_exp_state_dict.values():
            for k, v in state.sim_progress.items():
                data[k] += v
        return data

class BranchDeduceSimState(LargeSampleSimState):
    ''' 分支推演任务状态 '''
    # 管理一个用户执行的所有分支推演任务
    pass

SimStateDict = {
    SimMode.SINGLE.value: SingleSimState,
    SimMode.PARALLEL.value: ParallelSimState,
    SimMode.BRANCH_DEDUCE.value: BranchDeduceSimState
}

class BaseSingleExpState:
    ''' 一次并行仿真或分支推演任务状态 '''
    def __init__(self, script_name, max_running_engine_num, reducer, origin_reduce_data):
        self.script_name = script_name                         # 运行脚本名称
        self.max_running_engine_num = max_running_engine_num   # 能够使用的引擎数量
        self.reducer = reducer                                 # reducer 函数
        self.origin_reduce_data = origin_reduce_data           # reducer 初始数据
        self.last_update_time = time.time()                    # 上次更新仿真进程的时间

    def show(self):
        raise NotImplementedError()

    def update_state_time(self):
        self.last_update_time = time.time()

    @property
    def using_state(self):
        ''' 正在使用 client 的state , large_sample_thread 清理使用'''
        raise NotImplementedError()

    @property
    def is_running(self):
        ''' 当前任务是否未结束 '''
        raise NotImplementedError()

    @property
    def sim_progress(self):
        ''' 仿真进度 '''
        raise NotImplementedError()

    def search(self):
        raise NotImplementedError()

    def stop(self):
        raise NotImplementedError()

    def add_client(self):
        raise NotImplementedError()
    
    def reduce(self):
        raise NotImplementedError()
    
    def process_sim_end(self):
        raise NotImplementedError()

class ParallelSimSingleExpState(BaseSingleExpState):
    ''' 并行仿真单次实验仿真状态 '''
    def __init__(self, script_name='', all_num=0, max_running_engine_num=0, reducer=None, origin_reduce_data={}):
        super().__init__(script_name, max_running_engine_num, reducer, origin_reduce_data)
        self.sim_mode = SimMode.PARALLEL.value
        self.all_num = all_num                                 # 总仿真次数
        self.running_state = dict()                            # engine_name: SingleSimState
        self.done_state = dict()                               # engine_name: SingleSimState
        self.failure_num = 0

        self.save_data = origin_reduce_data           # reduce 执行并行仿真存储的所有结果
        self.process_data = None                      # reduce 执行并行仿真上显中间结果
        self.terminate_data = None                    # reduce 执行并行仿真上显最终结果

    def show(self):
        d = {}
        d.update({k: {"sim_state": 'running', 'single_state': v.show()} \
                    for k, v in self.running_state.items()})
        d.update({k: {"sim_state": 'done', 'single_state': v.show()} \
                    for k, v in self.done_state.items()})
        res = {'single_states': d,
                'use_reducer': self.reducer is not None,
                'process_data': self.process_data is not None,
                'terminate_data': self.terminate_data is not None}
        return res

    @property
    def using_state(self):
        return self.running_state

    @property
    def is_running(self):
        return self.all_num != len(self.done_state)

    @property
    def sim_progress(self):
        return {'all_sim_num': self.all_num,
                'sim_running_num': len(self.running_state),
                'sim_done_num': len(self.done_state),
                'failure_num': self.failure_num}

    def search(self, engine_name):
        state = self.running_state.get(engine_name, None)
        if state is None:
            state = self.done_state.get(engine_name, None)
        return state

    def stop(self):
        ''' 手动停止该仿真 '''
        return [state.client for state in self.running_state.values()]

    def add_client(self, engine_name, client, sim_param):
        self.running_state[engine_name] = SingleSimState(client, sim_param)
        client.mode = self.sim_mode

    def process_sim_end(self, engine_name):
        single_sim_state = self.running_state.pop(engine_name)
        single_sim_state.process_sim_end()
        self.done_state[engine_name] = single_sim_state

        # 最后处理保证整个实验结束时能更新 terminate_result
        self.reduce(engine_name)
        self.update_state_time()

    def reduce(self, engine_name):
        if self.reducer is not None:
            single_state = self.done_state.get(engine_name, None)
            assert single_state is not None, print(engine_name, self.show())
            self.save_data, self.process_data = self.reducer(self.save_data, single_state.terminate_data)
        if not self.is_running:
            self.terminate_data = self.process_data

class StateTreeNode:
    def __init__(self, engine_name, triggered_name=None, answer_name=None):
        self.engine_name = engine_name
        self.triggered_name = triggered_name
        self.answer_name = answer_name
        self.children = dict() # answer_name: TreeNode
        self.state = None      
    
    def search(self, branch_history, return_node=False):
        if branch_history:
            return self.children[branch_history[0][1]] \
                    .search(branch_history[1:], return_node)
        else:
            if return_node:
                return self
            else:
                return self.state

    def add_client(self, branch_history, single_sim_state, engine_name):
        # branch_history 为路径， engine_name 为新 single_sim_state 的名字
        if branch_history:
            # 非根节点
            node = self.search(branch_history[:-1], return_node=True)
            triggered_name = branch_history[-1][0]
            answer_name = branch_history[-1][1]
            child = StateTreeNode(engine_name, triggered_name, answer_name)
            child.add_client([], single_sim_state, engine_name)
            node.children[answer_name] = child
        else:
            # 根节点
            self.state = single_sim_state
    
    def to_json(self):
        # 为了生成的为 json 格式, 如此设置
        # label 为前端显示字符串, value 为传给 msystem 的字符串
        res = {'name': self.triggered_name, 
                'value': self.answer_name,
                'engine_name': self.engine_name,
                'is_done': self.state.is_done}
        if len(self.children) > 0:
            res['children'] = [c.to_json() for c in self.children.values()]
        return res

    def iter(self):
        res = list()
        q = Queue()
        q.put(self)
        while not q.empty():
            node = q.get()
            yield node
            res.append(node)
            for child in node.children.values():
                q.put(child)

    def reduce(self, reducer, origin_reduce_data):
        reduce_data = deepcopy(origin_reduce_data)
        web_data = None
        if reducer:
            for node in self.iter():
                if node.state.terminate_data:
                    reduce_data, web_data = reducer(reduce_data,
                                        node.state.terminate_data)
        return web_data

class BranchDeduceSimSingleExpState(BaseSingleExpState):
    ''' 分支推演单次实验仿真状态 '''
    def __init__(self, script_name='', max_running_engine_num=0, 
            reducer=None, compare_reducer=None, origin_reduce_data={}):
        super().__init__(script_name, max_running_engine_num, reducer, origin_reduce_data)
        self.sim_mode = SimMode.BRANCH_DEDUCE.value
        self.compare_reducer = compare_reducer                 # 对比不同节点的仿真数据的函数
        self._node = None

    def show(self):
        return dict()

    @property
    def using_state(self):
        res = dict()
        if not self._node:
            return res
        for node in self._node.iter():
            state = node.state
            if state is not None and state.client is not None:
                res[node.engine_name] = state
        return res

    @property
    def is_running(self):
        # 1.所有的节点 is_done == False
        # 2.所有的叶子节点都有 terminate_result
        if not self._node:
            return True
        for node in self._node.iter():
            single_sim_state = node.state
            if not single_sim_state.is_done:
                return True
            if len(node.children) == 0 and not single_sim_state.terminate_data:
                return True
        return False

    def search(self, engine_name):
        if self._node is None:
            return None
        branch_history = get_branch_history(engine_name)
        res = self._node.search(branch_history)
        return res

    def search_node(self, engine_name):
        if self._node is None:
            return None
        branch_history = get_branch_history(engine_name)
        res = self._node.search(branch_history, return_node=True)
        return res

    @property
    def sim_progress(self):
        if self._node:
            return self._node.to_json()
        else:
            return {}

    def stop(self):
        waiting_stop_list = []
        if self._node:
            for node in self._node.iter():
                single_sim_state = node.state
                if not single_sim_state.is_done:
                    waiting_stop_list.append(single_sim_state.client)
        return waiting_stop_list

    def add_client(self, engine_name, client, sim_param):
        single_sim_state = SingleSimState(client, sim_param)
        if self._node is None:
            self._node = StateTreeNode(engine_name)
        branch_history = get_branch_history(engine_name)
        self._node.add_client(branch_history, single_sim_state, engine_name)
        client.mode = self.sim_mode

    def reduce(self, engine_names):
        # 1.合并节点下所有仿真结果
        datas = []
        for engine_name in engine_names:
            state_node = self.search_node(engine_name)
            reduce_data = state_node.reduce(self.reducer, 
                        self.origin_reduce_data)
            if reduce_data:
                datas.append(reduce_data)
        # 2 对比不同节点的 reduce 结果
        if datas and self.compare_reducer:
            return self.compare_reducer(datas)
        else:
            return {"data": []}

    def process_sim_end(self, engine_name):         
        self.update_state_time()
        single_sim_state = self.search(engine_name)
        single_sim_state.process_sim_end()
        # trigger_name 为空代表触发过所有分支
        sim_params = []
        if single_sim_state.trigger_name:
            # 触发过的 trigger 不再触发
            branch_history = get_branch_history(engine_name)
            sim_param = single_sim_state.sim_param
            branch_deduce_param = sim_param.branch_deduce_param
            triggered_names = [h[0] for h in branch_history] + [single_sim_state.trigger_name]
            trigger_names = [k for k in branch_deduce_param.keys() if k not in triggered_names]
            for answer_name in branch_deduce_param.get(single_sim_state.trigger_name, []):
                tmp_branch_history = branch_history.copy()
                tmp_branch_history.append([single_sim_state.trigger_name, answer_name])
                sim_param = BranchDeduceSimParam(sim_param.cmd, 
                                                sim_param.token, 
                                                sim_param.script_text, 
                                                sim_param.branch_deduce_param, 
                                                sim_param.kwargs, 
                                                single_sim_state.checkpoint_bytes, 
                                                tmp_branch_history,
                                                trigger_names,
                                                answer_name)
                sim_params.append(sim_param)
        return {'sim_params': sim_params}

    def iter_node(self):
        if self._node:
            return self._node.iter()
        return []

class ServerState:
    def __init__(self, config):
        self._config = config
        self._state = dict()

    def show(self):
        d = dict()
        for user_name, state in self._state.items():
            d[user_name] = {k: v.show() for k, v in state.items()}
        return d

    def search(self, user_name, sim_mode, token=None, engine_name=None):
        '''查询用户在该仿真模式下的状态'''
        if user_name not in self._state:
            return None
        if sim_mode not in self._state[user_name]:
            return None
        state = self._state[user_name][sim_mode]
        if not token:
            return state
        else:
            return state.search(token, engine_name)

    def create_state(self, user_name, sim_mode):
        assert self.search(user_name, sim_mode) is None, f'{user_name} {sim_mode} state 已存在'
        self._state.setdefault(user_name, dict())
        state = SimStateDict[sim_mode]()
        self._state[user_name][sim_mode] = state  
        return state
    
    def iter_state(self, filter_single_mode=True):
        ''' 遍历所有正在使用的 client'''
        for user_name, state in self._state.items():
            for sim_mode, sim_state in state.items():
                if sim_mode == SimMode.SINGLE.value:
                    if filter_single_mode:
                        continue
                    else:
                        yield user_name, sim_mode, None, None, sim_state
                else:
                    for token, single_exp_state in \
                            sim_state.single_exp_state_dict.items():      
                        for engine_name, single_state in single_exp_state.using_state.items():
                            yield user_name, sim_mode, token, engine_name, single_state

    def process_sim_end(self, user_name, sim_mode, token, engine_name):
        '''仿真结束更新服务状态'''
        # 该过程只在 base_server._large_sample_process 中, 所以更新会有延迟，外部已经加锁
        state = self.search(user_name, sim_mode)
        if sim_mode == SimMode.SINGLE.value:
            if time.time() - self._state[user_name].last_end_time > \
                    self._config.single_mode_save_time:
                state.process_sim_end()
                self._state[user_name].pop(sim_mode)
            else:
                state.process_sim_end(clear_client_flag=False)
            return
        else:
            return state.process_sim_end(token, engine_name)
          
    def update_state(self):
        '''更新服务状态'''
        # 该过程只在 base_server._large_sample_process 中, 外部已经加锁
        del_user = []
        for user_name, state in self._state.items():
            del_mode = []
            for sim_mode, sim_state in state.items():
                if sim_mode == SimMode.SINGLE.value:
                    if sim_state.client is None:
                        del_mode.append(sim_mode)
                elif sim_mode == SimMode.PARALLEL.value:
                    del_token = []
                    for token, single_exp_state in \
                            sim_state.single_exp_state_dict.items():
                        # 仿真统计数据保留一段时间
                        if len(single_exp_state.running_state) == 0 and \
                                time.time() - single_exp_state.last_update_time > \
                                self._config.parallel_mode_data_save_time:
                            del_token.append(token)
                    for token in del_token:
                        sim_state.pop(token)
                    if len(sim_state.single_exp_state_dict) == 0:
                        del_mode.append(sim_mode)
            for mode in del_mode:
                state.pop(mode)
            if len(state) == 0:
                del_user.append(user_name)
        for user_name in del_user:
            self._state.pop(user_name)

