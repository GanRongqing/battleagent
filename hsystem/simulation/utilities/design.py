"""
实验设计工具函数
"""
from itertools import product
from allpairspy import AllPairs

def generate_para(*args, mode="con", times=1):
    if mode == "con":
        return _generate_con_para(*args)*times
    elif mode == "cro":
        return _generate_cro_para(*args)*times
    elif mode == "zip":
        return _generate_zip_para(*args)*times
    elif mode == "ort":
        return _generate_ort_para(*args)*times
    else:
        raise RuntimeError("unknown mode")

            
def _generate_con_para(*args):
    # 单个变量依次变动可能值
    paras = []
    base_para = []
    for arg in args:
        base_para.append(arg[0])
    paras.append(base_para)
    for i, arg in enumerate(args):
        for ar in arg[1:]:
            para = base_para.copy()
            para[i] = ar 
            paras.append(para)
    return paras


def _generate_cro_para(*args):
    # 多个变量交叉变动值
    return [para for para in product(*args)]


def _generate_zip_para(*args):
    # 成对变动变量值
    ls = [len(arg) for arg in args]
    # the same length list
    assert max(ls) == min(ls)
    return [para for para in zip(*args)]


def _generate_ort_para(*args):
    """正交实验设计
    """
    l = list(map(tuple, AllPairs(list(args))))
    return l


if __name__ == "__main__":
    print(generate_para([1,2], [3,4], mode="con", times=9))