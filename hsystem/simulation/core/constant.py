# 字节顺序
BYTE_ORDER = {
    "original_o": "@",  # 字节顺序：按原字节，大小：按原字节，对齐方式：按原字节
    "original_n": "=",  # 字节顺序：按原字节，大小：标准，对齐方式：无
    "big_end": ">",  # 字节顺序：大端，大小：标准，对齐方式：无
    "small_end": "<",  # 字节顺序：小端，大小：标准，对齐方式：无
    "network": "!"  # 字节顺序：网络（=大端），大小：标准，对齐方式：无
}

# 消息头数据长度
MSG_HEAD_LENGTH = 12
# 消息头 采用小端
MSG_HEAD = f"{BYTE_ORDER['small_end']}BBHIHH"

# 消息数据包格式
PACK_FORMAT = {
    "task_command": MSG_HEAD + "HHHIBIIB{}BB{}B{}",  # 任务指令
    "strike_command": f"{MSG_HEAD}IBI",  # 打击指令
    "platform_state": f"{MSG_HEAD}IBHHIiiiHH",  # 平台状态
    "target_situation": f"{MSG_HEAD}IiiiHBHH",  # 目标态势
    "radar_state": f"{MSG_HEAD}BBBhhhhhhhhhhhhhhhhhhhihhh",  # 雷达载荷能力
    "photoelectric_state": f"{MSG_HEAD}BBBhhBhhhhhhh",  # 光电载荷能力
    "simulation_ratio": f"{MSG_HEAD}BH",  # 仿真倍速
    "target_lethality": f"{MSG_HEAD}IB",  # 目标毁伤
    "group_state": MSG_HEAD + "IBBBHH{}II",  # 集群状态，{}根据集群平台数量进行参数替换
    "weapon_state": f"{MSG_HEAD}HBI"  # 武器状态
}

# 任务类型
TASK_TYPE = {
    "201": 201,  #
    "202": 202,  #
    "203": 203,  #
    "204": 204,  #
    "205": 205,  #
    "206": 206,  #
    "208": 208,  #
    "209": 209,  #
    "211": 211  #
}

# 任务状态
TASK_STATE = {
    "2011": 2011,  #
    "2021": 2021,  #
    "2022": 2022,  #
    "2031": 2031,  #
    "2032": 2032,  #
    "2041": 2041,  #
    "2042": 2042,  #
    "2043": 2043,  #
    "2051": 2051,  #
    "2052": 2052,  #
    "2061": 2061,  # 。
    "2081": 2081,  #
    "2082": 2082,  #
    "2083": 2083,  #
    "2091": 2091,  #
    "2092": 2092,  #
    "2093": 2093,  #
    "2111": 2111,  #
    "2112": 2112,  #
    "2113": 2113,  #
}

# 报文类型 和 解包函数映射关系
MSG_TYPE_TO_FUNCTION = {
    105: "task_command",
    106: "strike_command",
    107: "platform_state",
    108: "target_situation",
    109: "radar_state",
    110: "photoelectric_state",
    111: "simulation_ratio",
    112: "target_lethality",
    113: "group_state",
    114: "weapon_state"
}
