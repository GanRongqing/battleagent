from enum import Enum

class RaiseErrorFlag(Enum):
    TERMINATE = 'TERMINATE'
    RAISE = 'RAISE'
    DEBUG = 'DEBUG'

class StrikeChainSource(Enum):
    # 打击链构建来源，如果是 msystem, 打击链在 load 时会检查 crosspoint
    MSYSTEM = 'MSYSTEM'
    OUTER = 'OUTER'
    AI_xxgongsi = 'AI_xxgongsi'

class StrikeChainState(Enum):
    # 打击链构建状态
    BUILDED = ''
    LOADING = ''
    FAILED = ''
    OVER = ''
    HAND_DELETE = ''

class LogCommandLabel(Enum):
    GUIDER_PRELOAD = ''
    GUIDER_PRELOAD_CANCEL = ''
    GUIDER_LOAD = ''
    GUIDER_REALASE = ''
    MSG_FRIEND_SEND = ''
    MSG_FRIEND_RECEIVE = ''
    CMD_SEND = ''
    CMD_RECEIVE = ''
    WEAPONSYSTEM_MSG_RECEIVE = ''
    WEAPONSYSTEM_MSG_SEND = ''
    WEAPONSYSTEM_MSG_SEND_DISTRIBUTED = '[分布式]'
    LOAD_RESULT_MSG_SEND = ''
    LOAD_RESULT_MSG_FRIEND_SEND = ''
    LOAD_RESULT_MSG_RECEIVE = ''
    LOAD_RESULT_MSG_FRIEND_RECEIVE = ''
    INTERCEPT_RESULT_MSG_SEND = ''
    INTERCEPT_RESULT_MSG_FRIEND_SEND = ''
    INTERCEPT_RESULT_MSG_RECEIVE = ''
    INTERCEPT_RESULT_MSG_FRIEND_RECEIVE = ''



