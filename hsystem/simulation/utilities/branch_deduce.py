class BranchTriggerHandler:
    '''当前的分支推演在 engine 中处理某一种分支，不同的分支由 base_server 执行分发汇总'''

    def __init__(self, engine):
        self.engine = engine
        self._trigger_dict = dict()

    def clear(self):
        self._trigger_dict = dict()

    def activate(self, trigger_name):
        self._trigger_dict[trigger_name] = self.engine.branch_trigger_by_name(trigger_name)

    def check(self):
        for trigger_name, trigger_func in self._trigger_dict.items():
            if trigger_func(self.engine):
                self.engine.stop_update()
                self.engine.checkpoint_bytes = self.engine.save()
                self.engine.triggered_name = trigger_name
                self.engine.kill()
