import json
import os
from copy import deepcopy
import os
from itertools import product
import numpy as np


def update_nested_dict(dct, nested_key, value, v1, local=False):
    if not local:
        tmp_dict = deepcopy(dct)
    else:
        tmp_dict = dct
    keys = nested_key.split(".")
    tmp = tmp_dict
    assert "[" not in keys[-1], "最后一个标识必须为字典的一个键"
    for key in keys[:-1]:
        if "[" not in key:
            assert isinstance(tmp, dict)
            if key not in tmp:
                raise RuntimeError("字典中未找到对应的键")
            tmp = tmp[key]
        elif "=" not in key:
            # 形如[1]
            idx = int(key[1:-1])
            assert isinstance(tmp, list)
            if idx < 0 or idx > (len(tmp)-1):
                raise RuntimeError("下标超过列表的长度")
            tmp = tmp[idx]
        else:
            # 形如[a=2]
            _key, _value =  key[1:-1].split("=")
            if  _value =="": ###_value取v1的值，可为任意类型值
                _value=v1
            else:
                _value = eval(_value) # 如果是字符串，则应用单引号表示
            assert isinstance(tmp, list)
            res = None
            for _tmp in tmp:
                if (_key in _tmp) and _tmp[_key] == _value:
                    res = _tmp
                    break
            if res is not None:
                tmp = res
            else:
                raise RuntimeError("列表中未找到对应的键和值")       
    tmp[keys[-1]] = value
    return tmp_dict


def gen_json(fname, updated, v1, tag="updated", encoding="utf-8"):
    """ 对json文件中的某个嵌套变量进行修改，批量生成json文件

    ---------依次对字典里单个变量进行嵌套修改，动态生成想定文件-------------
    >>> fname = "fire_test.json"
    >>> updated = {
    >>>     # 正常字典嵌套型
    >>>     "INFO.test_data.water": 1.2,
    >>>     # 正常字典嵌套型和列表嵌套
    >>>     "INFO.test_data.[0].multi_sonar": 2
    >>>     # 正常字典嵌套型和列表嵌套
    >>>     "BLUE.members.[id=BlueJT1].coodrs": 2
    >>> }

    >>> updated = {
    >>>     # 正常字典嵌套型和列表嵌套
    >>>     "taskData.operUnit.warship.[shipGlobalId=].shipGlobalId.value": [1,2,3]
    >>> }
    >>> v1 = {"name": "舰船Id","value": "18"}
    --------------------------------------------------------------------
    """
    assert isinstance(updated, dict)
    fdir = os.path.dirname(fname)
    fbase = os.path.basename(fname)[:-5]
    fpath = os.path.join(fdir, fbase)
    if not os.path.exists(fpath):
        os.makedirs(fpath)
    new_name = os.path.join(fpath, tag+".json")

    with open(fname, 'rb') as f:
        dct = json.load(f)

    for nested_key, value in updated.items():
        dct = update_nested_dict(dct, nested_key, value, v1,local=True)
    
    with open(new_name, 'w', encoding=encoding) as f:
        json.dump(dct, f, indent=4, ensure_ascii=False)


def gen_batch_jsons(fname, updated, v1=0, mode="cro", encoding="utf-8"):
    """
    ---------------交叉修改变量，动态生成想定文件---------------------------
    >>> fname = "fire_test.json"
    >>> updated = {"INFO.test_data.water": [1.5, 1.6],
    >>>            "INFO.test_data.multi_sonar": [[0, 1], [1, 0]],
    >>>            "BLUE.members.ESB2.velocity": [[0, -8, 0], [0, -9, 0]]}    
    --------------------------------------------------------------------
    """
    fbase = os.path.basename(fname)[:-5]
    keys = []
    values = []
    assert isinstance(updated, dict)
    assert mode in ["cro", "zip"]
    for k, v in updated.items():
        keys.append(k)
        assert isinstance(v, list)
        values.append(v)
    if mode == "cro":
        i=1
        for para in product(*values):
            _updated = dict(zip(keys, para))
            #gen_json(fname, _updated, v1,tag=fbase+"_"+str(para), encoding=encoding)
            gen_json(fname, _updated, v1,tag=fbase+"_"+str(i), encoding=encoding)
            i=i+1
    else:
        # zip
        i=1
        ls = [len(arg) for arg in values]
        # the same length list
        assert max(ls) == min(ls)
        for para in zip(*values):
            _updated = dict(zip(keys, para))
            # gen_json(fname, _updated, v1,tag=fbase+"_"+str(para), encoding=encoding)
            gen_json(fname, _updated, v1,tag=fbase+"_"+str(i), encoding=encoding)
            i=i+1
   


