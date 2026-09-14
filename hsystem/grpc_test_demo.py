# 引用GRPC通信相关的包
import grpc
import json
from pprint import pprint

# 引用与仿真系统交互的GRPC通信协议
from simulation import simserver_pb2
from simulation import simserver_pb2_grpc

_HOST = '124.220.84.217'# ip地址固定为本地ip
_PORT = '6000' # 端口号固定为6000
channel = grpc.insecure_channel("{0}:{1}".format(_HOST, _PORT))
client = simserver_pb2_grpc.GreeterStub(channel=channel)
user_name = "admin" # user_name固定为admin

# 算法与仿真系统的交互接口
msg = json.dumps({
    "source": "gengtu",
    "ip": "test",
    "user_name": user_name,
    "engine_name": "",
    "flag": "simulation",
    "func_name": "init",
    "kwargs": {
        "fname": "测试用例1",  # 使用 sces.json 中配置的脚本名
        "update": True          # 让引擎开始运行
    }
})

# msg = json.dumps({
#        "source":"test",
#        "ip":"test",
#        "user_name": user_name,
#        "engine_name": "",
#        "flag":"simulation",
#        "func_name":"get_state", # 接口函数名
#        "kwargs":{} # 接口函数的参数
#    })
# msg = json.dumps({
#     "source": "test",
#     "ip": "test",
#     "user_name": user_name,
#     "engine_name": "",
#     "flag": "simulation",
#     "func_name": "send_command",  # 开启雷达
#     "kwargs": {
#         "cmd": {
#             "unit_name": "white_usv1",  # 必须是白方(RED)平台，不是 black_usv1
#             "target_speed": 80,         # 期望速度（m/s）
#             "target_course": 0         # 期望航向（度）[0, 360]
#         }
#     }
# })
# msg = json.dumps({
#     "source": "test",
#     "ip": "test",
#     "user_name": user_name,
#     "engine_name": "",
#     "flag": "simulation",
#     "func_name": "cmd_lock",
#     "kwargs": {
#         "cmd": {
#             "unit_name1": "white_usv1",
#             "unit_name2": "black_usv1",
#         }
#     }
# })
# msg = json.dumps({
#     "source": "test",
#     "ip": "test",
#     "user_name": user_name,
#     "engine_name": "",
#     "flag": "simulation",
#     "func_name": "cmd_uav_takeoff",
#     "kwargs": {
#         "cmd": {
#             "unit_name": "white_uav1",
#             "home_name": "white_usv1",
#             "target_speed": 90,
#             "target_course": 90
#         }
#     }
# })
# msg = json.dumps({
#    "source": "test",
#    "ip": "test",
#    "user_name": user_name,
#    "engine_name": "",
#    "flag": "simulation",
#    "func_name": "terminate",
#    "kwargs": {}
# })

request = client.control(simserver_pb2.MsgStr(msg=msg)) # request为接口函数的返回值
print("返回消息如下：",request.msg)
# 检查是否有返回数据
if request.data:
    data = json.loads(request.data)
    print("返回数据:")
    pprint(data)
else:
    print("没有返回数据")


