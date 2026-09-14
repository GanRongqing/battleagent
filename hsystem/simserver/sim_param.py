import json
import time

from simserver.enums import InvalidScriptName, SimMode

class BaseSimParam:
    def __init__(self, cmd, script_text, token='', config_kwargs={}):
        self.user_name = cmd['user_name']
        self.sim_mode = ''
        self.token = token                        # 仿真任务的唯一标识
        self.cmd = cmd
        self.source = self.cmd.get('source', '')
        self.ip = self.cmd.get('ip', '')
        self.engine_name = ''                     # 引擎名称
        self.script_text = script_text            # 仿真脚本文本
        self.config_kwargs = config_kwargs
        self.update = cmd.get('kwargs', {}).get('update', True)

        self.split_symbols = ['@', '#', '^']      # 分割使用  不能作为参数名

    @property
    def start_sim_req_param(self):
        """ 生成开始仿真的指令信息 """
        
        server_data = {'user_name': self.user_name,
                       'sim_mode': self.sim_mode}
        kwargs = self.kwargs.copy()
        kwargs.update(self.config_kwargs)

        if self.engine_name:
            kwargs['engine_name'] = self.engine_name
            server_data['engine_name'] = self.engine_name
        if self.token:
            server_data['token'] = self.token
        param_data = {
            "text": self.script_text,
            'update': self.update,
            "kwargs": kwargs
        }
        msg_dict = {
            "flag": "simulation",
            "ip": self.ip,
            "source": self.source,
            "user_name": self.user_name,
            'server_data': server_data,
            "func_name": 'init',
            "kwargs": param_data
        }
        return {'msg': json.dumps(msg_dict)}

class SingleSimParam(BaseSimParam):
    def __init__(self, cmd, script_text, config_kwargs={}):
        super().__init__(cmd, script_text, config_kwargs=config_kwargs)
        self.sim_mode = SimMode.SINGLE.value
        self.kwargs = cmd.get('kwargs', dict()).get('kwargs', dict())

class ParallelSimParam(BaseSimParam):
    def __init__(self, cmd, token, script_text, kwargs, sim_index):
        super().__init__(cmd, script_text, token)
        self.sim_mode = SimMode.PARALLEL.value
        self.kwargs = kwargs           # 全部的仿真参数字典
        for k, v in self.kwargs.items():
            for symbol in self.split_symbols:
                if isinstance(k, str):
                    assert symbol not in k
                if isinstance(v, str):
                    assert symbol not in v
        self.sim_index = sim_index     # 相同仿真参数下的多次仿真的次序号
        self.update_name()

    def update_name(self):
        '''更新 engine_name'''
        # 大样本仿真 engine_name 命名规则暂定如下 {token}@{sim_mode}@{该模式参数信息}@{time_tag}
        # time_tag = datetime.datetime.now().strftime("%Y%m%d%H%M%S")   这种形式可能精度不够出现重名
        time_tag = f'{int(time.time())}'
        param_tag = '#'.join([f'{k}^{v}' for k, v in self.kwargs.items() if (len(f'{k}-{v}') < 100)])
        param_tag += f'#INDEX^{self.sim_index}'
        engine_name = '@'.join([self.token, self.sim_mode, param_tag, time_tag])
        assert len(engine_name.split("@")) == 4
        self.engine_name = engine_name

class BranchDeduceSimParam(BaseSimParam):
    def __init__(self, cmd, token, script_text, branch_deduce_param, kwargs, 
            checkpoint_bytes=b'', branch_history=[], trigger_names=[], answer_name=''):
        super().__init__(cmd, script_text, token)
        self.sim_mode = SimMode.BRANCH_DEDUCE.value
        self.branch_deduce_param = branch_deduce_param # 分支推演参数  {trigger1: [answer1, answer2, ...], ...}
        self.kwargs = kwargs                           # 全部的仿真参数字典
        self.checkpoint_bytes = checkpoint_bytes       # 引擎触发分支时保存的当前态势
        self.branch_history = branch_history           # 触发历史 [[trigger_name1, answer_name1], ...]
        self.trigger_names = trigger_names             # 本次仿真可以触发的 trigger 函数名
        self.answer_name = answer_name                 # 本次仿真开始之前需要执行的 answer 函数名
        self.update_name()

    def update_name(self):
        '''更新 engine_name'''
        # 大样本仿真 engine_name 命名规则定义如下 {token}@{sim_mode}@{该模式参数信息}@{time_tag}
        time_tag = f'{int(time.time())}'
        param_tag = '#'.join(['^'.join(h) for h in self.branch_history])
        engine_name = '@'.join([self.token, self.sim_mode, param_tag, time_tag])
        assert len(engine_name.split("@")) == 4
        self.engine_name = engine_name

    @property
    def start_sim_req_param(self):
        req_param = super().start_sim_req_param
        msg = json.loads(req_param['msg'])
        msg['kwargs']['branch_deduce_data'] = {
            'engine_name': self.engine_name,
            'trigger_names': self.trigger_names,
            'answer_name': self.answer_name
        }
        req_param['msg'] = json.dumps(msg)
        if self.checkpoint_bytes:
            req_param['checkpoint_bytes'] = self.checkpoint_bytes
        return req_param