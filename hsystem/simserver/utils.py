import os
import socket
import inspect

from simserver.enums import SimMode

DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_MESSAGE_LENGTH = 1024 * 1024 * 1024
GRPC_OPTIONS = [
    ('grpc.so_reuseport', 0),
    ('grpc.max_seed_message_length', MAX_MESSAGE_LENGTH),
    ('grpc.max_receive_message_length', MAX_MESSAGE_LENGTH),
    ('grpc.enable_retries', 1)
]

class ScriptTreeNode:
    # 多级文件夹树结构

    @classmethod
    def load_sces_json(cls, j):
        node = cls()
        for key, value in j.items():
            data = key.split('/')
            node.add_data(data, value)
        return node

    def __init__(self, value='', layer=0):
        self.value = value
        self.layer = layer
        self.children = []
        self.mode = None

    def search(self, full_name, mode=None):
        # 查找相同文件夹的子节点
        data = full_name.split('/')
        node = self
        for i, s in enumerate(data):
            for child in node.children:
                if child.value == s:
                    node = child
                    if i == len(data) - 1 and \
                        (mode is None or mode in node.mode):
                        return node
        return None

    def add_data(self, data, value):
        # data 为 List[str], 最后一级的 str 为文件名，其他为各级文件夹名
        node = self
        for i, s in enumerate(data):
            assert len(s) > 0, '脚本名称格式错误!'
            child = node.search(s)
            if child:
                if i == len(data) - 1:
                    raise RuntimeError("该脚本名称已存在")
                node = child
            else:
                tmp_node = ScriptTreeNode(s, i+1)
                node.children.append(tmp_node)
                node = tmp_node
            if i == len(data) - 1:
                node.mode = value.get('sim_mode', [SimMode.SINGLE.value])

    def to_json(self, mode):
        # 为了生成的为 json 格式, 如此设置
        # label 为前端显示字符串, value 为传给 msystem 的字符串
        if self.children:
            # 非根和叶子节点
            if self.layer != 0:
                res = {'label': self.value, 'value': self.value}
                if len(self.children) > 0:
                    res['children'] = []
                    for c in self.children:
                        tmp_res = c.to_json(mode)
                        if tmp_res:
                            res['children'].append(tmp_res)
                if self.mode or res['children']:
                    return res
                else:
                    return None
            else:
                # 根节点
                res = []
                for c in self.children:
                    tmp_res = c.to_json(mode)
                    if tmp_res:
                        res.append(tmp_res)
                return res
        else:
            # 叶子节点
            if self.mode and mode in self.mode:
                res = {'label': self.value, 'value': self.value}
                return res
            else:
                return None

def get_local_ip():
    hostname = socket.gethostname()
    ip = socket.gethostbyname(hostname)
    return ip

def get_member_funcs(entity):
    """ 获取类对象的属性方法 """
    members = inspect.getmembers(entity)
    if not members:
        return []
    return list(zip(*members))[0]

def load_text_file(path, copy_to_temp=''):
    if os.path.isabs(path):
        fullpath = path
    else:
        # 以msystem为根目录
        fullpath = os.path.join(DIR, path)
    with open(fullpath, "r", encoding="utf-8") as f:
        text = f.read()
    if len(copy_to_temp):
        with open(os.path.join(DIR, 'simserver', copy_to_temp), "w", encoding="utf-8") as f:
            f.write(text)
    return text

