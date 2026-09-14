import grpc
import time
import json
import traceback
from simserver import simserver_pb2
from simserver import simserver_pb2_grpc

from simserver.utils import GRPC_OPTIONS
from simserver.enums import ServerReturnMsg, SimMode, SimState, InvalidScriptName


class SimClient:
    """ 
    可以理解为SimServer的代理, 视同SimServer
    不记录仿真相关信息 
    """

    def __init__(self, url):
        self.url = url
        channel = grpc.insecure_channel(url, options=GRPC_OPTIONS)
        client = simserver_pb2_grpc.GreeterStub(channel=channel)
        self.client = client
        # 被哪种仿真模式占用, 在处理对应模式的 SimParam 类实例时设置, 
        # 对应的单次仿真结束后置为 FREE
        self.mode = SimMode.FREE.value
        # 当前的仿真引擎的运行状态, 由 SimServer 的 heartbeat 控制            
        self.state = SimState.STOP.value
        self.heartbeat_last_update_time = time.time()

    @property
    def in_use(self):
        return self.mode != SimMode.FREE.value

    @property
    def is_running(self):
        return self.state != SimState.STOP.value

    def to_dict(self):
        dct = {
            "url": self.url,
            "user_name": self.user_name,
            "token": self.token,
            "state": self.state.value,
            "engine_name": self.engine_name,
            "in_use": self.in_use,
            "heartbeat_last_update_time": self.heartbeat_last_update_time
        }
        return dct

    def update_state(self, state=None):
        if state:
            self.state = state
        self.heartbeat_last_update_time = time.time()

    def push_req(self, msg, data=None, checkpoint_bytes=b''):
        """ 向SimServer发起grpc请求

        包括单次仿真和大样本仿真
        """
        try:
            timeout = 20
            if data:
                res = self.client.control(simserver_pb2.MsgStr(msg=msg, data=data, bytes_data=checkpoint_bytes),
                                          timeout=timeout)
            else:
                res = self.client.control(simserver_pb2.MsgStr(msg=msg, bytes_data=checkpoint_bytes), timeout=timeout)
        except:
            traceback.print_exc()
            return simserver_pb2.MsgStr(msg=ServerReturnMsg.TIMEOUT.value)
        return res

    def stop_engine(self):
        # 这个 user_name 为 SELF 时, 代表停止并行仿真引擎，前面已经校验过开始、停止并行仿真的是同一用户
        msg_dict = {
            "flag": "simulation",
            "ip": "127.0.0.1",
            "source": "SELF",
            "user_name": "SELF",
            "func_name": 'terminate',
        }
        res = self.push_req(json.dumps(msg_dict))
        return res

    def get_simulation_info(self):
        msg_dict = {
            "flag": "simulation",
            "ip": "127.0.0.1",
            "source": "SELF",
            "user_name": "SELF",
            "func_name": 'get_simulation_info',
        }
        res = self.push_req(json.dumps(msg_dict))
        return res

    def get_single_statistics(self):
        msg_dict = {
            "flag": "simulation",
            "ip": "127.0.0.1",
            "source": "SELF",
            "user_name": "SELF",
            "func_name": 'get_single_statistics',
        }
        res = self.push_req(json.dumps(msg_dict))
        return res

    def clear(self):
        msg_dict = {
            "flag": "simulation",
            "ip": "127.0.0.1",
            "source": "SELF",
            "user_name": "SELF",
            "func_name": 'clear',
        }
        return self.push_req(json.dumps(msg_dict))
