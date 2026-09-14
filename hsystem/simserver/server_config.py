import os
import json
from simserver.utils import ScriptTreeNode
from simserver.utils import DIR


class ClientPoolConfig:
    def __init__(self):
        self.single_sim_min_workers = 1  


class ServerStateConfig:
    def __init__(self):
        self.single_mode_save_time = 60  
        self.parallel_mode_data_save_time = 7 * 24 * 3600  


class BaseServerConfig:
    def __init__(self):
        self.single_sim_workers = 1  
        self.sces = json.load(
            open(os.path.join(DIR, "simserver", 'config', "sces.json"), 'r', encoding='utf-8-sig'))  
        self.script_tree = ScriptTreeNode.load_sces_json(self.sces)
        self.auth_list = [line.strip() for line in
                          open(os.path.join(DIR, "simserver", 'config', 'auth.config'), 'r',
                               encoding='utf8').readlines()]  
        self.recent_parallel_time_thres = 3600
        self.simserver_delete_time_thres = 5 * 60
        self.large_sample_engine_num_per_user = 10  

        self.client_pool_config = ClientPoolConfig()
        self.server_state_config = ServerStateConfig()
