import time
import json

class LargeSampleData:
    """ 大样本仿真模式下的存储的大样本仿真的多次仿真的聚合信息
    """
    def __init__(self, user_name, branch_deduce_plan=None):
        self.user_name = user_name
        self.script_name = ""  # 大样本仿真的脚本名称
        self.engine_num = 0  # 最大可同时占用的引擎的数量
        self.all_num = 0
        self.running_num = 0
        self.done_num = 0
        self.failure_num = 0
        self.failure_list = []
        self.reducer = None
        self.branch_deduce_plan = branch_deduce_plan
        self.cache_data = None # 用于存储原始的和仿真结果的数据
        self.web_data = None # 用于存储web上显的数据
        self.last_update_time = time.time()

    def setattr(self, k, v):
        try:
            setattr(self, k, v)
            self.last_update_time = time.time()
        except:
            print(f'{k} 不是 LargeSampleData 类的属性, 跳过')

    def append_failure_sim_name(self, failure_sim_name):
        self.failure_list.append(failure_sim_name)
        self.failure_num = len(self.failure_list)
        self.last_update_time = time.time()

    def __str__(self):
        return json.dumps({
            'user_name': self.user_name,
            'all_num': self.all_num,
            'running_num': self.running_num,
            'done_num': self.done_num,
            'failure_name': self.failure_num,
            'failure_list': self.failure_list,
            'cache_data': self.cache_data,
            'web_data': self.web_data,
            'last_update_time': self.last_update_time,
        })
