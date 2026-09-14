""" Message and Command definition.

Message and command associated with core components.
"""
import os
import sys
import time
import logging
import logging.handlers

import numpy as np
from simulation.core import entity, arch

## define logger level
# DEBUG, INFO, WARNING, ERROR, CRITICAL 这五个日志等级分别为10,20,30,40,50
DEBUG, INFO, WARNING, ERROR, CRITICAL = logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL # 10,20,30,40,50
DECISION, SENSOR, PHYSICS, COMMAND = 24, 25, 26, 27
REDIS, REDIS_MSG = 28, 29 # Redis推送事件

def get_tracer(engine, level, terminal=True, fpath=None):
    """ Initiate logger for event and data tracking. """
    logger = __get_logger(engine)
    logger.setLevel(level)
    if terminal:
        __config_terminal_handler(logger, level)
    if fpath is not None:
        assert isinstance(fpath, str)
        __config_file_handler(logger, level, fpath)
    return logging.LoggerAdapter(logger, {"timestamp" : __EngineTimer(engine)})


def __get_logger(engine):
    time_tag = time.strftime("%Y-%m-%d-%H-%M-%S") + "-"+ str(np.random.randint(10000, 99999))
    # logging靠名字识别日志，为避免多次运行时重复在同一个logger上反复添加handler，名称随机并唯一

    # 改变日志映射关系，定制化日志等级名称
    logging.addLevelName(24, "DECISION")
    logging.addLevelName(25, "SENSOR")
    logging.addLevelName(26, "PHYSICS")
    logging.addLevelName(27, "COMMAND") # 指挥关系相关
    logging.addLevelName(28, "REDIS")
    logging.addLevelName(29, "REDIS_MSG")

    return  logging.getLogger(engine.name + '_' + time_tag)


class __EngineTimer:
    """ Helper class for formatting simulation engine time. """

    def __init__(self, parent):
        self._parent = parent

    def __call__(self, parent):
        self._parent = parent

    def __str__(self):
        """ Simulation engine timestamp. """
        return "{} {}".format(self._parent.tick, self._parent.ymdhms)


def __config_terminal_handler(logger, level):
    fmt = "%(timestamp)s %(levelname)s %(message)s"
    ostream = sys.stdout
    if level in [logging.DEBUG, logging.ERROR, logging.WARNING, logging.CRITICAL]:
        fmt = "%(filename)s:%(lineno)d " + fmt
    handler = logging.StreamHandler(ostream)
    handler.setFormatter(logging.Formatter(fmt))
    logger.addHandler(handler)
    

def __config_file_handler(logger, level, fpath):
    if not os.path.exists(fpath):
        os.makedirs(fpath)
    fmt = "%(timestamp)s %(levelname)s %(message)s"
    if level in [logging.DEBUG, logging.ERROR, logging.WARNING, logging.CRITICAL]:
        fmt = "%(filename)s:%(lineno)d " + fmt
    handler = logging.FileHandler(os.path.join(fpath, "sim.log"), mode='w', encoding='utf-8')

    handler.setFormatter(logging.Formatter(fmt))
    logger.addHandler(handler)

def _add_escape_character(s):
    return s.replace('<', '&lt;').replace('>', '&gt;')

class LogData:
    def __init__(self, level, fmt, args, kwargs):
        self.level = level
        self.fmt = fmt
        self.args = args
        self.kwargs = kwargs

    def get_print_param(self):
        args_tmp = []
        for s in self.args:
            if isinstance(s, arch.Platform):   # 平台
                args_tmp.append(s.name)
            elif isinstance(s, entity.Entity): # 组件
                args_tmp.append(s.ucname)
            else:
                args_tmp.append(s)                  # 字符串, 或者 bool

        return self.level, self.fmt, args_tmp, self.kwargs

    def get_redis_show_param(self):
        return self.fmt.replace('%s', '{}').format(*self.args)

    def get_msystem_web_show_param(self):
        args_tmp = []
        for s in self.args:
            # 此处单双引号不能改变, 涉及 web 端解析 html 格式
            if isinstance(s, arch.Platform):   # 平台
                args_tmp.append(f"<span style='color: {_add_escape_character(s.group)}'>{_add_escape_character(s.name)}</span>")
            elif isinstance(s, entity.Entity): # 组件
                args_tmp.append(f"<span style='color: {_add_escape_character(s.group)}'>{_add_escape_character(s.ucname)}</span>")
            else:
                args_tmp.append(s)                  # 字符串, 或者 bool
            
        return self.fmt.replace('%s', '{}').format(*args_tmp)
