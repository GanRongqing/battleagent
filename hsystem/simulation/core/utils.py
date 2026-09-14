import datetime
import math
import struct
from simulation.core.constant import PACK_FORMAT, MSG_TYPE_TO_FUNCTION, MSG_HEAD_LENGTH


def unpack_udp_data(data):
    # 取得报文类型
    msg_type = bytes_to_int(data[10:12])
    # 根据报文类型取得解包函数名称
    func_name = f"unpack_{MSG_TYPE_TO_FUNCTION[msg_type]}_data"
    # 根据函数名称取得函数
    remote_func = eval(func_name)
    # 进行函数调用
    return remote_func(data)


def pack_udp_data(params):
    # 取得报文类型
    msg_type = params["msg_type"]
    # 根据报文类型取得解包函数名称
    func_name = f"pack_{MSG_TYPE_TO_FUNCTION[msg_type]}_data"
    # 根据函数名称取得函数
    remote_func = eval(func_name)
    # 进行函数调用
    return remote_func(params)


def pack_task_command_data(params):
    # 平台数量 UINT8
    platform_nums = 3
    # 任务区域点数量 UINT8
    task_area_point_nums = 4
    # 目标数量 UINT8
    target_nums = 2
    # 计算数据长度 = 消息头数据长度 + 消息体数据长度（固定参数长度 + 平台数量*每个平台数据长度 + 任务区域点数量*每个区域点数据长度 + 目标数量*每个目标数据长度）
    length = MSG_HEAD_LENGTH + 23 + platform_nums * 5 + task_area_point_nums * 12 + target_nums * 16

    # 定义参数
    args = gen_msg_head_args(1, length, 105)
    # 任务编号 UINT16
    args.append(1001)
    # 任务类型 UINT16
    args.append(201)
    # 速度 UINT16，单位：0.1米/秒，需要转为整数，乘以10**1
    args.append(decimal_to_int(10.5, 1))
    # 集群批号 UINT32
    args.append(100302)
    # 集群队形 UINT8，2：三角；3：横；4：竖；5：T；6：倒V；
    args.append(2)
    # 集群横向距离 UINT32，单位：0.1米
    args.append(decimal_to_int(100.5, 1))
    # 集群纵向距离 UINT32，单位：0.1米
    args.append(decimal_to_int(150.5, 1))
    # 平台数量 UINT8
    fmt_param1 = platform_nums * "IB"
    args.append(platform_nums)
    for i in range(1, platform_nums + 1):
        # 平台i批号 UINT32，8位编批，编批规则见附录
        args.append((2000 + i) * 10000 + 1101)
        # 平台i长僚属性 UINT8，1：长；2：僚；
        args.append(1 if i == 1 else 2)

    # 任务区域类型 UINT8，2：多边形；3：长T航点；
    args.append(2)
    # 任务区域点数量 UINT8
    fmt_param2 = task_area_point_nums * "iii"
    args.append(task_area_point_nums)
    for i in range(1, task_area_point_nums + 1):
        # 任务区域点i经度 INT32，取值：0.000001度，需要转为整数，乘以10**6
        args.append(decimal_to_int(127.056489 + i / 10, 6))
        # 任务区域点i纬度 INT32，取值：0.000001度，需要转为整数，乘以10**6
        args.append(decimal_to_int(27.256845 + i / 10, 6))
        # 任务区域点i高度 INT32，取值：0.1米，需要转为整数，乘以10**1
        args.append(decimal_to_int(0.1, 1))

    # 目标数量 UINT8
    args.append(target_nums)
    fmt_param3 = target_nums * "Iiii"
    for i in range(1, target_nums + 1):
        # 目标i批号 UINT32，8位编批，编批规则见附录
        args.append((2000 + i) * 10000 + 1101)
        # 目标i经度 INT32，取值：0.000001度，需要转为整数，乘以10**6
        args.append(decimal_to_int(125.056489 + i / 10, 6))
        # 目标i纬度 INT32，取值：0.000001度，需要转为整数，乘以10**6
        args.append(decimal_to_int(25.256845 + i / 10, 6))
        # 目标i高度 INT32，取值：0.1米，需要转为整数，乘以10**1
        args.append(decimal_to_int(0.2, 1))

    # 取得格式字符串（有三个参数：动态平台个数、动态任务区域、动态目标个数）
    pack_fmt = PACK_FORMAT["task_command"].format(fmt_param1, fmt_param2, fmt_param3)
    # 打包数据并返回
    pack_res = struct.pack(pack_fmt, *args)
    return pack_res


def pack_strike_command_data(params):
    # 定义参数
    args = gen_msg_head_args(1, 21, 106)
    # 平台批号 UINT32，8位编批，编批规则见附录
    args.append(20011101)
    # WQ类型 UINT8，0：
    args.append(0)
    # 目标批号 UINT32，8位编批，编批规则见附录
    args.append(20011101)
    # 打包数据并返回
    pack_res = struct.pack(PACK_FORMAT["strike_command"], *args)
    return pack_res


def pack_platform_state_data(params):
    # 定义参数
    args = gen_msg_head_args(1, 41, 107)
    # 平台批号 UINT32，8位编批，编批规则见附录
    args.append(10015000)
    # 长僚属性 UINT8，0：未组建编队；1：长；2：僚；
    args.append(0)
    # 执行任务类型 UINT16
    args.append(201)
    # 执行任务状态 UINT16
    args.append(2011)
    # 集群批号 UINT32
    args.append(100302)
    # 平台经度 INT32，需要转为整数，乘以10**6
    args.append(decimal_to_int(127.056489, 6))
    # 平台纬度 INT32，需要转为整数，乘以10**6
    args.append(decimal_to_int(27.256845, 6))
    # 平台深度 INT32，需要转为整数，乘以10**1
    args.append(decimal_to_int(0.5, 1))
    # 平台速度 UINT16，需要转为整数，乘以10**1
    args.append(decimal_to_int(10.5, 1))
    # 平台航向角 UINT16，需要转为整数，乘以10**2
    args.append(decimal_to_int(95.86, 2))
    # 打包数据并返回
    pack_res = struct.pack(PACK_FORMAT["platform_state"], *args)
    return pack_res


def pack_target_situation_data(params):
    # 定义参数
    args = gen_msg_head_args(1, 35, 108)
    # 目标批号 UINT32，8位编批，编批规则见附录
    args.append(10015000)
    # 目标经度 INT32，取值：0.000001度，需要转为整数，乘以10**6
    args.append(decimal_to_int(127.056489, 6))
    # 目标纬度 INT32，取值：0.000001度，需要转为整数，乘以10**6
    args.append(decimal_to_int(27.256845, 6))
    # 目标高度 INT32，取值：0.1米海拔高度，需要转为整数，乘以10**1
    args.append(decimal_to_int(0.5, 1))
    # 目标方位 UINT16，取值：0.1度，，需要转为整数，乘以10**1
    args.append(decimal_to_int(135.5, 1))
    # 目标类型 UINT8，1.WR机；2.WR艇
    args.append(1)
    # 目标速度 UINT16，取值：0.1节，需要转为整数，乘以10**1
    args.append(decimal_to_int(20.5, 1))
    # 目标航向 UINT16，取值：0.1度，需要转为整数，乘以10**1
    args.append(decimal_to_int(315.5, 1))
    # 打包数据并返回
    pack_res = struct.pack(PACK_FORMAT["target_situation"], *args)
    return pack_res


def pack_radar_state_data(params):
    # 定义参数
    args = gen_msg_head_args(1, 63, 109)
    # 载荷类型 Byte，1=雷达
    args.append(1)
    # 载荷状态 Byte，0=未知或关机，1=开机或正常，2=故障
    args.append(1)
    # 载荷编号 Byte
    args.append(1)
    # 载荷方位角 Int16,0.1°
    args.append(decimal_to_int(120.1, 1))
    # 载荷俯仰角 Int16,0.1°
    args.append(decimal_to_int(122.1, 1))
    # 载荷探测范围 Int16,探测半径,m
    args.append(decimal_to_int(10, 0))
    # 中心频率 Int16，0.1Ghz
    args.append(decimal_to_int(11.1, 1))
    # 工作带宽 Int16，0.1Mhz
    args.append(decimal_to_int(12.1, 1))
    # 接收机带宽 Int16，0.1Mhz
    args.append(decimal_to_int(13.1, 1))
    # 天线增益 Int16，0.1dB
    args.append(decimal_to_int(14.1, 1))
    # 波束方位宽度 Int16，0.01rad
    args.append(decimal_to_int(15.25, 2))
    # 波束俯仰宽度 Int16，0.01rad
    args.append(decimal_to_int(16.25, 2))
    # 波束10dB位置 Int16，0.01rad
    args.append(decimal_to_int(17.25, 2))
    # 扫描周期 Int16, 0.1°/s
    args.append(decimal_to_int(18.1, 1))
    # 噪声系数 Int16，0.1dB
    args.append(decimal_to_int(19.1, 1))
    # 相参脉冲个数 Int16，
    args.append(1)
    # 脉冲宽度最小值 Int16，us
    args.append(decimal_to_int(20, 0))
    # 脉冲宽度最大值 Int16，us
    args.append(decimal_to_int(200, 0))
    # 精跟目标ID Int16,
    args.append(2)
    # 批号列表 Int16,
    args.append(1001)
    # 瞬时信号带宽 Int16，0.1Mhz
    args.append(decimal_to_int(21.1, 1))
    # 信号周期 Int16，0.1ms
    args.append(decimal_to_int(22.1, 1))
    # 发射功率 Int32，w
    args.append(decimal_to_int(500, 0))
    # 发射损耗 Int16，0.1dB
    args.append(decimal_to_int(23.1, 1))
    # 接收损耗 Int16，0.1dB
    args.append(decimal_to_int(24.1, 1))
    # 波束指向 Int16, 0.1°
    args.append(decimal_to_int(25.1, 1))
    # 打包数据并返回
    pack_res = struct.pack(PACK_FORMAT["radar_state"], *args)
    return pack_res


def pack_photoelectric_state_data(params):
    # 定义参数
    args = gen_msg_head_args(1, 34, 110)
    # 载荷类型 Byte，2=光电
    args.append(2)
    # 载荷状态 Byte，0=未知或关机，1=开机或正常，2=故障
    args.append(1)
    # 载荷编号 Byte
    args.append(1)
    # 载荷方位角 Int16,0.1°
    args.append(decimal_to_int(120.1, 1))
    # 载荷俯仰角 Int16,0.1°
    args.append(decimal_to_int(122.1, 1))
    # 传感器类型 Byte，0:可见光、1：中波红外、2：长波红外、3：激光
    args.append(0)
    # 水平分辨率 Int16, Pixel
    args.append(decimal_to_int(1920, 0))
    # 垂直分辨率 Int16, Pixel
    args.append(decimal_to_int(1080, 0))
    # 镜头宽高比 Int16，0.01%，宽/高
    args.append(decimal_to_int(16 / 9, 2))
    # 水平视场角 Int16，0.01°
    args.append(decimal_to_int(80.33, 2))
    # 垂直视场角 Int16，0.01°
    args.append(decimal_to_int(90.33, 2))
    # 红外感知低温 Int16，0.1℃
    args.append(decimal_to_int(-25.2, 1))
    # 红外感知高温 Int16，0.1℃
    args.append(decimal_to_int(37.5, 1))
    # 打包数据并返回
    pack_res = struct.pack(PACK_FORMAT["photoelectric_state"], *args)
    return pack_res


def pack_simulation_ratio_data(params):
    # 定义参数
    args = gen_msg_head_args(1, 15, 111)
    # 仿真倍速 UINT8，1-10
    args.append(5)
    # 仿真步长 UINT16，20-1000(ms)
    args.append(700)
    # 打包数据并返回
    pack_res = struct.pack(PACK_FORMAT["simulation_ratio"], *args)
    return pack_res


def pack_target_lethality_data(params):
    # 定义参数
    args = gen_msg_head_args(1, 17, 112)
    # 目标批号 UINT32，8位编批，编批规则见附录
    args.append(10015000)
    # 目标是否死亡 UINT8，0 死亡 1 存活
    args.append(1)
    # 打包数据并返回
    pack_res = struct.pack(PACK_FORMAT["target_lethality"], *args)
    return pack_res


def pack_group_state_data(params):
    # 集群平台数量 UINT8
    platform_nums = 3
    # 计算数据长度 = 消息头数据长度 + 消息体数据长度（固定参数长度 + 平台数量*每个平台数据长度）
    length = MSG_HEAD_LENGTH + 19 + platform_nums * 4

    # 定义参数
    args = gen_msg_head_args(1, length, 113)
    # 集群批号 UINT32，6位编批
    args.append(100302)
    # 集群类型 UINT8，1：WR机集群 2：WR艇集群
    args.append(1)
    # 集群平台数量 UINT8
    args.append(platform_nums)
    fmt_param = platform_nums * "I"

    # 集群队形 UINT8，2：三角；3：横；4：竖；5：T；6：倒V；
    args.append(2)
    # 任务类型 UINT16，见附件
    args.append(201)
    # 任务状态 UINT16，见附件
    args.append(2011)

    # 平台批号
    for i in range(1, platform_nums + 1):
        # 平台i批号 UINT32，8位编批，编批规则见附录
        args.append((2000 + i) * 10000 + 1101)

    # 集群横向距离 UINT32，单位：0.1米
    args.append(decimal_to_int(100.5, 1))
    # 集群纵向距离 UINT32，单位：0.1米
    args.append(decimal_to_int(150.5, 1))

    # 取得格式字符串（有1个参数：动态平台个数）
    pack_fmt = PACK_FORMAT["group_state"].format(fmt_param)
    # 打包数据并返回
    pack_res = struct.pack(pack_fmt, *args)
    return pack_res


def pack_weapon_state_data(params):
    # 定义参数
    args = gen_msg_head_args(1, 19, 114)
    # 武器数量 UINT16，10
    args.append(10)
    # 武器类型 UINT8，0：
    args.append(0)
    # 所属平台 UINT32，平台编号
    args.append(10015000)
    # 打包数据并返回
    pack_res = struct.pack(PACK_FORMAT["weapon_state"], *args)
    return pack_res


def unpack_task_command_data(data):
    # 平台数量参数位置索引
    index1 = 31
    # 取得平台数量
    platform_nums = bytes_to_int(data[index1:index1 + 1])
    fmt_param1 = platform_nums * "IB"

    # 任务区域点数量参数位置索引
    index2 = index1 + 1 + platform_nums * 5 + 1
    # 取得任务区域点数量
    task_area_point_nums = bytes_to_int(data[index2: index2 + 1])
    fmt_param2 = task_area_point_nums * "iii"

    # 目标数量参数位置索引
    index3 = index2 + 1 + task_area_point_nums * 12
    # 取得目标数量
    target_nums = bytes_to_int(data[index3: index3 + 1])
    fmt_param3 = target_nums * "Iiii"

    # 取得格式字符串（有三个参数：动态平台个数、动态任务区域、动态目标个数）
    pack_fmt = PACK_FORMAT["task_command"].format(fmt_param1, fmt_param2, fmt_param3)
    # 解包数据并转为列表
    unpack_data_list = list(struct.unpack(pack_fmt, data))
    # 速度 单位：0.1米/秒
    unpack_data_list[9] = int_to_decimal(unpack_data_list[7], 1)
    # 集群横向距离 单位：0.1米
    unpack_data_list[12] = int_to_decimal(unpack_data_list[10], 1)
    # 集群纵向距离 单位：0.1米
    unpack_data_list[13] = int_to_decimal(unpack_data_list[11], 1)

    # 计算第一个任务区域点数据位置
    start_index1 = 12 + platform_nums * 2 + 3
    for i in range(task_area_point_nums):
        index = start_index1 + 3 * i
        # 任务区域点经度 取值：0.000001度
        unpack_data_list[index] = int_to_decimal(unpack_data_list[index], 6)
        # 任务区域点纬度 取值：0.000001度
        unpack_data_list[index + 1] = int_to_decimal(unpack_data_list[index + 1], 6)
        # 任务区域点高度 取值：0.1米
        unpack_data_list[index + 2] = int_to_decimal(unpack_data_list[index + 2], 1)

    # 计算第一个目标批号的位置
    start_index2 = 12 + platform_nums * 2 + 2 + task_area_point_nums * 3 + 2
    for i in range(target_nums):
        index = start_index2 + 4 * i
        # 目标经度 取值：0.000001度
        unpack_data_list[index + 1] = int_to_decimal(unpack_data_list[index + 1], 6)
        # 目标纬度 取值：0.000001度
        unpack_data_list[index + 2] = int_to_decimal(unpack_data_list[index + 2], 6)
        # 目标高度 取值：0.1米
        unpack_data_list[index + 3] = int_to_decimal(unpack_data_list[index + 3], 1)

    # 返回数据
    return unpack_data_list


def unpack_strike_command_data(data):
    # 解包数据并转为列表
    unpack_data_list = list(struct.unpack(PACK_FORMAT["strike_command"], data))
    # 返回数据
    return unpack_data_list


def unpack_platform_state_data(data):
    # 解包数据并转为列表
    unpack_data_list = list(struct.unpack(PACK_FORMAT["platform_state"], data))
    # 定义需要转换格式的索引列表
    index_power_list = [(11, 6), (12, 6), (13, 1), (14, 1), (15, 2)]
    for index, power in index_power_list:
        unpack_data_list[index] = int_to_decimal(unpack_data_list[index], power)
    # 返回数据
    return unpack_data_list


def unpack_target_situation_data(data):
    # 解包数据并转为列表
    unpack_data_list = list(struct.unpack(PACK_FORMAT["target_situation"], data))
    # 定义需要转换格式的索引列表
    index_power_list = [(7, 6), (8, 6), (9, 1), (10, 1), (12, 1), (13, 1)]
    for index, power in index_power_list:
        unpack_data_list[index] = int_to_decimal(unpack_data_list[index], power)
    # 返回数据
    return unpack_data_list


def unpack_radar_state_data(data):
    # 解包数据并转为列表
    unpack_data_list = list(struct.unpack(PACK_FORMAT["radar_state"], data))
    # 定义需要转换格式的索引列表
    index_power_list = [(9, 1), (10, 1), (11, 0), (12, 1), (13, 1), (14, 1), (15, 1), (16, 2), (17, 2), (18, 2),
                        (19, 1), (20, 1), (21, 0), (22, 0), (23, 0), (26, 1), (27, 1), (28, 0), (29, 1), (30, 1),
                        (31, 1)]
    for index, power in index_power_list:
        unpack_data_list[index] = int_to_decimal(unpack_data_list[index], power)
    # 返回数据
    return unpack_data_list


def unpack_photoelectric_state_data(data):
    # 解包数据并转为列表
    unpack_data_list = list(struct.unpack(PACK_FORMAT["photoelectric_state"], data))
    # 定义需要转换格式的索引列表
    index_power_list = [(9, 1), (10, 1), (12, 0), (13, 0), (14, 2), (15, 2), (16, 2), (17, 1), (18, 1)]
    for index, power in index_power_list:
        unpack_data_list[index] = int_to_decimal(unpack_data_list[index], power)
    # 返回数据
    return unpack_data_list


def unpack_simulation_ratio_data(data):
    # 解包数据并转为列表
    unpack_data_list = list(struct.unpack(PACK_FORMAT["simulation_ratio"], data))
    # 返回数据
    return unpack_data_list


def unpack_target_lethality_data(data):

    # 解包数据并转为列表
    unpack_data_list = list(struct.unpack(PACK_FORMAT["target_lethality"], data))
    # 返回数据
    return unpack_data_list


def unpack_group_state_data(data):

    # 集群平台数量参数位置索引
    index1 = 17
    # 取得平台数量
    platform_nums = bytes_to_int(data[index1:index1 + 1])
    fmt_param = platform_nums * "I"

    # 取得格式字符串（有1个参数：动态平台个数）
    pack_fmt = PACK_FORMAT["group_state"].format(fmt_param)
    # 解包数据并转为列表
    unpack_data_list = list(struct.unpack(pack_fmt, data))
    # 集群横向距离 单位：0.1米
    unpack_data_list[-2] = int_to_decimal(unpack_data_list[-2], 1)
    # 集群纵向距离 单位：0.1米
    unpack_data_list[-1] = int_to_decimal(unpack_data_list[-1], 1)
    # 返回数据
    return unpack_data_list


def unpack_weapon_state_data(data):

    # 解包数据并转为列表
    unpack_data_list = list(struct.unpack(PACK_FORMAT["weapon_state"], data))
    # 返回数据
    return unpack_data_list


def gen_msg_head_args(no, length, msg_type):

    # 取得系统时间戳，从当天00:00:00开始的毫秒数
    # 距离凌晨的时间戳
    system_time = get_system_time()
    # 定义参数
    # 序号 UINT8，一级标识 UINT8 FF，长度 UINT16，时间 UINT32，备用 UINT16，报文类型 UINT16
    return [no, 0xFF, length, system_time, 0, msg_type]


def decimal_to_int(value, power):

    return int(value * math.pow(10, power))


def int_to_decimal(value, power):
    """
        整数转小数（除以10对应的幂次）
    :param value: 数值
    :param power: 10的幂次
    :return: 转换后的小数
    """
    return value / math.pow(10, power)


def bytes_to_int(bytes_data):
    # 大端使用
    # return int(bytes_data.hex(), 16)
    # 小端使用
    return int(bytes_data[::-1].hex(), 16)


def get_system_time():
    """
        取得系统时间戳，从当天00:00:00开始的毫秒数
    :return: 系统时间戳
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
    return int((seconds * 1000 + millisecond + 1) / 10)
