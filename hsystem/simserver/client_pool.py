from simserver.enums import SimMode


class ClientPool:
    def __init__(self, config):
        self._config = config
        self._clients = dict()

    def __getitem__(self, item):
        return self._clients[item]
    
    def __len__(self):
        return len(self._clients)

    def keys(self):
        return self._clients.keys()

    def items(self):
        return self._clients.items()

    @property
    def free_num(self):
        return sum([1 if not client.in_use else 0 \
                    for client in self._clients.values()])

    def add(self, client):
        '''添加注册引擎'''
        if client.url in self._clients:
            return False
        else: 
            self._clients[client.url] = client
            return True

    def remove(self, url):
        '''删除已经注册但失联的引擎'''
        
        del self._clients[url]

    def get_free_client(self, sim_mode):
        '''获取空闲 client'''
        free_client_num = 0
        for _, client in self._clients.items():
            if not client.in_use:
                if sim_mode == SimMode.SINGLE.value:
                    return client
                else:
                    free_client_num += 1
                    if free_client_num > self._config.single_sim_min_workers:
                        return client
        return None

    def update_state(self, url):
        self._clients[url].update_state()