from functools import wraps
import inspect
from inspect import signature
import datetime

def check_sim(func):
    """ 检查仿真脚本中的sim函数是否符合定义的要求 """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # 检查函数名称是否为sim
        assert func.__name__ == "sim"
        # 检查sim函数是否定义如下参数
        sig_params = signature(func).parameters
        keys = list(sig_params.keys())
        assert len(keys) >= 8
        assert keys[0] == "simserver"
        assert keys[1] == "engine_name"
        assert keys[2] == "web_ip"
        assert keys[3] == "gengtu_ip"
        assert keys[4] == "user_name"
        assert keys[5] == "render_config"
        assert keys[6] == "checkbox_dict"
        assert keys[7] == "logtag"
        for k, v in sig_params.items():
            assert v.default is not inspect._empty, "sim函数的所有参数必须为关键字参数"
        result = func(*args, **kwargs)
        return result
    return wrapper

