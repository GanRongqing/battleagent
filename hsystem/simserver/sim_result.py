import json
from simserver import simserver_pb2

from simserver.enums import ServerReturnMsg

class SimResult:
    def __init__(self, cmd):
        # 暂定 cmd 不能为空, 有些数据需要 cmd 携带
        self._msg = ServerReturnMsg.FUNC_SUCCESS.value
        self._data = None
        self.cmd = cmd

    @property
    def data(self):
        if self._data is not None:
            return self._data
        return None

    @data.setter
    def data(self, data):
        self._data = data

    @property
    def msg(self):
        return self._msg

    @msg.setter
    def msg(self, msg):
        self._msg = msg

    def load_response(self, response):
        self.msg = response.msg
        if response.data:
            self.data = json.loads(response.data)
    
    def grpc_result(self):
        if self.data is not None:
            return simserver_pb2.MsgStr(msg=self.msg, data=json.dumps(self.data))
        return simserver_pb2.MsgStr(msg=self.msg)

