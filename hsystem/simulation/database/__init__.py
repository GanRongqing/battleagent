import os
import copy
import time
import json
import json5
import pickle
import pyproj
import numpy as np
import pandas as pd
from glob import glob 
import pickle
from simulation.algorithm.geometry import reckon
import datetime as dt
import pandas as pd


DIR = os.path.dirname(os.path.abspath(__file__))

def naive(config):
    """ 去掉数据字典中的说明文字，只保留键和值
    """
    d = {}
    for key, value in config.items():
        if not isinstance(value, dict):
            d[key] = value 
        elif "value" in value:
            d[key] = value["value"]
        else:
            d[key] = naive(value)
    return d 

def recursive_naive(config):
    """ 递归去掉配置字典中的说明文字，只保留键和值
    
    通过该操作，得到的类似deepcopy的一个新的对象
    配置字典的值可能是：字典、列表、布尔值、浮点值、整型、字符串
    {bool, dict, float, int, list, str}
    """
    # 如果输入是一个字典dict，那么首先直接返回key为“value”的值，如果不存在，则递归调用naive
    if isinstance(config, dict):
        return {key: recursive_naive(value) for key, value in config.items()} if "value" not in config else recursive_naive(config["value"])
    # 如果输入是一个列表list，那么对于列表中的每一项，递归调用naive处理
    if isinstance(config, list):
        return [recursive_naive(item) for item in config]
    # 否则，输入是bool，float，int，str，直接返回config
    return config

def load_json(dirpath):
    conf = {}
    for f in glob(dirpath+"/**/*.json", recursive=True):  ##遍历dirpath文件夹下所有json文件
        if ".ipynb_checkpoints" in f:
            continue
        with open(f, encoding="UTF-8") as ff:
            c = json5.load(ff)  ##打开某个json文件并转字典
        conf.update(c)
    return conf

def load_one_json(fpath, light=True):
    """ 读取某个json文件返回字典 """
    with open(os.path.join(DIR, fpath), encoding="UTF-8") as f:
        conf=json5.load(f)
    if light:
        conf=naive(conf)
    return conf

def load_json_db(cache=True):

    pkl = os.path.join(DIR, "cache_json.pkl")
    if cache:
        if os.path.exists(pkl):
            f = open(pkl, "rb")
            conf = pickle.load(f)
            f.close()
            return conf
    conf = load_json(os.path.join(DIR, "json"))
    _commander = load_json(os.path.join(DIR, "commander"))
    conf.update(_commander)
    f = open(pkl, "wb")
    pickle.dump(conf, f)
    f.close()
    return conf

def load_csv(dirpath):
    conf = {}
    for f in glob(dirpath+"/**/*.csv", recursive=True):
        basename = os.path.basename(f)
        key = basename[:-4]
        # 支持对csv文件进行以‘#’开头的注释   
        # d = pd.read_csv(f, comment="#", engine="python", encoding="ansi")
        d = pd.read_csv(f, comment="#", engine="python", encoding="utf-8")
        conf[key] = d
    return conf

def load_csv_db(cache=True):
    pkl = os.path.join(DIR, "cache_csv.pkl")
    if cache:
        if os.path.exists(pkl):
            f = open(pkl, "rb")
            conf = pickle.load(f)
            f.close()
            return conf
    conf = load_csv(os.path.join(DIR, "csv"))
    f = open(pkl, "wb")
    pickle.dump(conf, f)
    f.close()
    return conf
   
def load_render_config():
    c = json5.load(open(os.path.join(DIR, "config/render.json"), encoding="UTF-8"))
    d = naive(c)
    return d

def load_sim_config():
    c = json5.load(open(os.path.join(DIR, "config/sim.json"), encoding="UTF-8"))
    d = naive(c)
    return d

def load_symbol_config():
    c = json5.load(open(os.path.join(DIR, "config/entity_symbol_id.json"), encoding="UTF-8"))
    d = naive(c)
    return d

def load_checkbox_config():
    d = json5.load(open(os.path.join(DIR, "config/checkbox_config.json"), encoding="UTF-8"))
    return d

def load_platform_dict_sunao():
    c = json5.load(open(os.path.join(DIR, "config/platform_dict_sunao.json"), encoding="UTF-8"))
    d = naive(c)
    return d

def load_environment():
    db = load_json(os.path.join(DIR, "environment"))
    db = recursive_naive(db)
    csv_db = load_csv(os.path.join(DIR, "environment"))
    db.update(csv_db)
    return db

def get_tree(cache=True):
    load_tree(cache=cache)

def load_tree(cache=True):
    """ 获取json文件夹下的各级文件目录以及最后一级文件的key """
    pkl = os.path.join(DIR, "cache_tree.pkl")
    if cache:
        if os.path.exists(pkl):
            f = open(pkl, "rb")
            tree = pickle.load(f)
            f.close()
            return tree
    path = os.path.join(DIR, "json")
    tree = []
    for dirpath, folders, fnames in os.walk(path):
        lst = []
        folder = os.path.basename(dirpath)
        if folder == ".ipynb_checkpoints":
            continue
        lst.append(folder)
        for fname in fnames:
            if fname[-5:]==".json":
                with open(os.path.join(dirpath, fname), encoding="utf-8") as f:
                    dct = json5.load(f)
                lst.append([fname[:-5]] + list(dct.keys()))
        tree.append(lst.copy())
    tree = tree[1:] + tree[0][1:]
    # 除第一层之外，其它各层的第一个元素值为目录
    f = open(pkl, "wb")
    pickle.dump(tree, f)
    f.close()
    return tree


class DataBase(object):
    """ 数据库

    对外提供统一的仿真装备数据库接口

    数据库以嵌套字典的形式组织
    数据库中的嵌套字典一般来说，只有三级，即{key1:{key2:value}}或两级{key1:DataFrame}
    除csv数据未实现平台级修改外，其他均已实现
    实现逻辑是：
    组件按unit.name查询，弹药按home_unit.name查询，
    但弹药组件是按unit.name查询！！！可根据需要修改！！！
    具体可查看具体的代码以确认，并可根据需要修改
    """
    def __init__(self, flag=None, cache=True):
        # flag 表示特定的数据库补充数据
        self.csv_db = load_csv_db(cache=cache)
        self.db_tree = load_tree(cache=cache)
        self.json_db = load_json_db(cache=cache)
        if flag == "yuanhai":
            _conf = load_one_json("other/yuanhai.json", light=False)
            # 将补充数据更新到数据库中,类似add_unit_model_data和add_unit_name_data的功能
            for k in self.json_db.keys():
                if k in _conf:
                    for k2 in _conf[k].keys():
                        if k2 in self.json_db:
                            k2_value = copy.deepcopy(self.json_db[k2])
                            k2_value.update(_conf[k][k2])
                            _conf[k][k2] = k2_value
                    self.json_db[k].update(_conf[k])

        self.json_naive_db = recursive_naive(self.json_db) # 一个新的与json_db无关的对象,去掉了无关的说明文字
        json_keys = set(self.json_naive_db.keys())
        csv_keys = set(self.csv_db.keys())
        intersection = json_keys & csv_keys
        assert intersection == set(), intersection # 交集必须说为空
        self.force_db = {} # 仿真装备参数
        self.force_db.update(self.json_naive_db)
        self.force_db.update(self.csv_db)
        
        self.force = load_one_json("config/force.json", light=True) # 机舷号与类型的对应关系表
        # self.sunao_platform_dict = load_platform_dict_sunao()
        self._keys = set(self.force_db.keys()) 
        #记录数据库生成后最开始的keys，以确保后续增加的unit_name不与原始的keys重复
    def __getitem__(self, key):

        return self.force_db[key]

    def __setitem__(self, key, value):
        self.force_db[key] = value

    def __contains__(self, key):
        if key in self.force_db:
            return True
        else:
            return False
    # 上述三个魔法函数主要是为了兼容之前的将DataBase直接作为字典使用的代码

    # def get_model_from_sunao(self, sunao_model):
    #     if sunao_model in self.force_db:
    #         return sunao_model
    #     else:
    #         return self.sunao_platform_dict.get("sunaoToM", {}).get(sunao_model, None)

    def get_model_for_sunao(self, m_model):
        return self.sunao_platform_dict.get("mToSunao", {}).get(m_model, m_model)

    def get_model_for_udp(self, model):
        return self.sunao_platform_dict.get("mToUdp", {}).get(model, model)

    def get_model_from_udp(self, model):
        return self.sunao_platform_dict.get("udpToM", {}).get(model, model)

    def get_no_for_name(self, name):
        return self.sunao_platform_dict.get("nameToNo", {}).get(name)

    def get_name_for_no(self, no):
        return self.sunao_platform_dict.get("noToName", {}).get(no)

    def get_platform_model(self, platform):
        return self.force[platform]

    def add_unit_model_data(self, unit_model, key1):
        """ 增加以key1键及对应的值为值，以unit_model为键的临时字典
        即{unit_name:{key1:{key2:value}}}
        目的是增加按平台类型临时修改的功能
        """
        key1_value = copy.deepcopy(self.force_db[key1])
        self.force_db[unit_model][key1] = key1_value

    def add_unit_name_data(self, unit_name, key1):
        """ 增加以key1键及对应的值为值，以unit_name为键的临时字典
        即{unit_name:{key1:{key2:value}}}
        目的是增加按平台临时修改的功能
        """
        assert unit_name not in self._keys, "unit_name与数据库中的原始keys重名"
        key1_value = copy.deepcopy(self.force_db[key1])
        if unit_name in self:
            self.force_db[unit_name][key1] = key1_value
        else:
            self.force_db[unit_name] = {key1: key1_value}

    def get(self, k, d=None, unit_model=None, unit_name=None):
        """增加优先按平台类型或平台名字查找子集
        目的是增加按平台临时修改的功能

        Args:
            k: 查询的关键字
            d: 如果查询为空， 默认返回值
            unit_model: 平台类型
            unit_name: 平台名称
        """
        if unit_name is not None and unit_name in self.force_db and k in self.force_db[unit_name]:
            return self.force_db[unit_name][k]
        elif unit_model is not None and unit_model in self.force_db and k in self.force_db[unit_model]:
            return self.force_db[unit_model][k]
        elif k in self.force_db:
            return self.force_db[k]
        else:
            return d

    def update_json(self, dirpath):
        """ 
        加载dirpath文件夹下所有的json文件
        """
        conf = recursive_naive(load_json(dirpath))
        self.force_db.update(conf)

    def get_info_init(self):
        """M系统显示所有数据库兵力知识图谱的函数

        Returns:
            _dict_: 数据库中飞机、船、潜艇的知识图谱显示信息
        """

        out={"parent_name":"装备数据库","children":[{"node_name": "飞机", "link_name":"include","category":"component","props":[],"children":[]},
                                                   {"node_name": "舰艇", "link_name":"include","category":"component","props":[],"children":[]},
                                                   {"node_name": "潜艇", "link_name":"include","category":"component","props":[],"children":[]}]}

        ###按知识图谱显示的格式生成返回值
        child1,child2,child3=[],[],[]
        for k in self._get_plane_names():
            child1.append({"node_name":k,"link_name":"include","category":"component","props":[]})
        for k in self._get_ship_names():
            child2.append({"node_name":k,"link_name":"include","category":"component","props":[]})
        for k in self._get_submarine_names():
            child3.append({"node_name":k,"link_name":"include","category":"component","props":[]})
        out["children"][0]["children"]=child1
        out["children"][1]["children"]=child2
        out["children"][2]["children"]=child3
        return out


    def get_database_info(self):
        """ 获取数据库的基本信息 """
        # 本应放在DataBase类中，但为保持与web端的接口不变，暂未调整
        table_count = len(list(self.json_db.keys()))
        record_count = sum([len(v) for v in list(self.json_db.values())])
        return {'table_count': table_count, 'record_count': record_count, 'data': self.db_tree}

    def get_table(self, k):
        """_summary_

        Args:
            k (str): 装备model
        """
        conf = load_csv(dirpath)
        self.force_db.update(conf)

    def _check_list_is_component(self, list0): 
        """ 判断list0是否包含force_db中的元素
        
        也即是否是单个组件(设置了相对位置信息等)或组件列表,形如
        ["XX", pd, paz, ph, az1, az2]
        或["XX", "YY"]
        或[["XX", pd, paz, ph, az1, az2], "YY"]
        """
        flag = False
        if list0:
            if isinstance(list0[0], str) and (list0[0] in self.force_db):
                flag = True
            elif isinstance(list0[0], list) and isinstance(list0[0][0], str) and (list0[0][0] in self.force_db):
                flag = True
        return flag

    def _get_info_child(self, k, v, unit_model=None, unit_name=None):
        """ 递归生成知识树的支(link_name)和支指向的下节点(node_name) """
        if k == 'class':
            # category:attr
            return {"node_name":str(v), "link_name":k, "category":"attr", "props":[], "children":[]}
        elif isinstance(v, bool):
            # category:attr
            return {"node_name":str(v), "link_name":k, "category":"attr", "props":[], "children":[]}
        elif isinstance(v, (float, int)):
            # category:val
            return {"node_name":str(v), "link_name":k, "category":"val", "props":[], "children":[]}
        elif isinstance(v, str):
            child_res = self.get(v, unit_model=unit_model, unit_name=unit_name)
            if child_res is None:
                # category:attr
                return {"node_name":v, "link_name":k, "category":"attr", "props":[], "children":[]}
            elif isinstance(child_res, pd.DataFrame):
                # category:attr
                # 值为数据框类型 作为props输出
                props = []
                for i in child_res.columns.values:
                    props.append({"name":str(i), "value":list(child_res[str(i)])})
                return {"node_name":v, "link_name":k, "category":"attr", "props":props, "children":[]}                        
            else:
                # category:component 
                # 单个组件(未设置相对位置信息等), 可进一步点击而展开
                return {"node_name":v, "link_name":k, "category":"component", "props":[], "children":[]}
        elif isinstance(v, list):
            if v == []:
                # category:attr
                return {"node_name":"[]", "link_name":k, "category":"attr", "props":[], "children":[]}
            else:
                if self._check_list_is_component(v):
                    # 单个组件(设置了相对位置信息等)或组件列表
                    if isinstance(v[0], str) and (v[0] in self.force_db):
                        if (len(v) in [4, 6]) and isinstance(v[1], (float, int)): # 主要是为了去掉["XX", "YY"]这种情况
                            # category:component 
                            # 单个组件(设置了相对位置信息等), 可进一步点击而展开
                            if len(v) == 6:
                                props = [{"name":"相对中心距离(m)","value": v[1]},
                                        {"name":"相对中心方位","value": v[2]},
                                        {"name":"相对中心高度(m)","value": v[3]},
                                        {"name":"相对轴起始方向","value": v[4]},
                                        {"name":"相对轴终止方向","value": v[5]}]
                            else:
                                props = [{"name":"相对中心距离(m)","value": v[1]},
                                        {"name":"相对中心方位","value": v[2]},
                                        {"name":"相对中心高度(m)","value": v[3]}]
                            return {"node_name":v[0], "link_name":k, "category":"component", "props":props, "children":[]}

                    # category:attr
                    # 按组件列表处理
                    children = []
                    for i, item in enumerate(v):
                        child = self._get_info_child(str(i), item, unit_model=unit_model, unit_name=unit_name)
                        children.append(child)
                    return {"node_name":"list", "link_name":k, "category":"attr", "props":[], "children":children}
                else:
                    # category:attr
                    # 普通的list
                    # 列表元素当做参数输出
                    props=[]
                    for i, item in enumerate(v):
                        props.append({"name":str(i),"value": item})
                    return {"node_name":"list_value", "link_name":k, "category":"attr", "props":props, "children":[]}        
        elif isinstance(v, dict):
            # category:attr
            children = []
            for _k, _v in v.items():
                child = self._get_info_child(_k, _v, unit_model=unit_model, unit_name=unit_name)
                children.append(child)
            return {"node_name":"dict", "link_name":k, "category":"attr", "props":[], "children":children}
        else:
            raise RuntimeError(f"未知参数类型v{v}")
        
    def _get_plane_names(self):
        return [key for key, val in self.json_naive_db.items() if val["class"] == "Plane"]

    def _get_ship_names(self):
        return [key for key, val in self.json_naive_db.items() if val["class"] == "Ship"]

    def _get_submarine_names(self):
        return [key for key, val in self.json_naive_db.items() if val["class"] == "Submarine"]

    def get_info(self, k, unit_model=None, unit_name=None, is_force=True):
        """  知识图谱点击按钮返回数据信息功能接口函数

        Args:
            k: 查询的关键字
            unit_model: 平台类型
            unit_name: 平台名称
            is_force: 是否需要从FORCE中查询机舷号对应的类型
        Returns:
            
            out: 所点击按钮的信息, 其中category有component attr val 三种
        """
        if k in ["飞机", "舰艇", "潜艇"]:
            out = self._get_info_category(k)
            return out
        res = self.get(k, unit_model=unit_model, unit_name=unit_name)
        if res is None:
            if is_force: 
                ### 查询的是否为兵力
                if k in self.force:
                    k1 = self.force[k]
                    res = self.get(k1, unit_model=unit_model, unit_name=unit_name)
        if res is None:
            out = None
        else:
            if isinstance(res, dict): # 正常情况下res一定是字典，不可能为DataFrame
                children = []
                for key, v in res.items(): 
                    child = self._get_info_child(key, v, unit_model=unit_model, unit_name=unit_name)
                    children.append(child)
                out = {"parent_name":k, "children":children}
            else:
                out = None
        return out     

    def _get_info_category(self, k):
        if k not in ["飞机", "舰艇", "潜艇"]:
            return None
        if k == "飞机":
            names = self._get_plane_names()
        elif k == "舰艇":
            names = self._get_ship_names()
        else:
            names = self._get_submarine_names()
        children = []
        for name in names:
            children.append({"node_name":name,"link_name":"include","category":"component","props":[]})
        return {"parent_name":k,"children":children}

    def get_info_init(self):
        """M系统显示所有数据库兵力知识图谱的函数

        Returns:
            _dict_: 数据库中飞机、船、潜艇的知识图谱显示信息
        """

        out={"parent_name":"装备数据库","children":[{"node_name": "飞机", "link_name":"include","category":"component","props":[],"children":[]},
                                                   {"node_name": "舰艇", "link_name":"include","category":"component","props":[],"children":[]},
                                                   {"node_name": "潜艇", "link_name":"include","category":"component","props":[],"children":[]}]}

        ###按知识图谱显示的格式生成返回值
        child1,child2,child3=[],[],[]
        for k in self._get_plane_names():
            child1.append({"node_name":k,"link_name":"include","category":"component","props":[]})
        for k in self._get_ship_names():
            child2.append({"node_name":k,"link_name":"include","category":"component","props":[]})
        for k in self._get_submarine_names():
            child3.append({"node_name":k,"link_name":"include","category":"component","props":[]})
        out["children"][0]["children"]=child1
        out["children"][1]["children"]=child2
        out["children"][2]["children"]=child3
        return out


    def get_database_info(self):
        """ 获取数据库的基本信息 """
        # 本应放在DataBase类中，但为保持与web端的接口不变，暂未调整
        table_count = len(list(self.json_db.keys()))
        record_count = sum([len(v) for v in list(self.json_db.values())])
        return {'table_count': table_count, 'record_count': record_count, 'data': self.db_tree}

    def get_table(self, k):
        """_summary_

        Args:
            k (str): 装备model
        """
        # dct = self.get(k=k)
        dct = self.json_db.get(k, None)
        if not dct:
            return None
        else:
            table = []
            for key, val in dct.items():
                if isinstance(val, dict):
                    name = val.get("name", "未命名") # 属性名
                    value = val.get("value", "null") # 值
                    unit = val.get("unit", "") # 单位
                    type_ = val.get("type", "") # 值的类型
                    range_ = val.get("range", "") # 取值范围
                    comment = val.get("comment", "") # 备注
                else:
                    if key == "name":
                        name = "名称"
                        value = val
                        unit = ""
                        type_ = "str"
                        range_ = ""
                        comment = ""
                    else:
                        name = "未命名"
                        value = val
                        unit = ""
                        type_ = "str"
                        range_ = ""
                        comment = ""
                table.append([key, name, value, unit, type_, range_, comment])
            return table


    def check_munition_is_aamissile(self, m_model):
        m = self.get(k=m_model)
        if m is None:
            return None
        if m["class"] == "AAMissile":
            return True
        else:
            return False

    def check_munition_is_ssmissile(self, m_model):
        m = self.get(k=m_model)
        if m is None:
            return None
        if m["class"] == "SSMissile":
            return True
        else:
            return False

DB = DataBase(flag="", cache=True)
