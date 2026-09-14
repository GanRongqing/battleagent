class _CLASS(dict):

    def register(self, cls):
        self.update({cls.__name__: cls})

CLASS = _CLASS()

from . import base, entity, message, arch, log, enums, special_effect, base_engine, engine, tzb_engine
# from . import engine_base as engine
# from . import engine
# from . import base_engine