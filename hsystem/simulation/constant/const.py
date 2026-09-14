class _const():
    class ConstantError(Exception): pass

# 注释代码因为无法被pikcle打包 改写成下面代码
# class _const():
#     class ConstantError(Exception): pass
#
#     def __setattr__(self, key, value):
#         if key in self.__dict__:
#             raise self.ConstantError('can not change const %s .' % key)
#         if not key.isupper():
#             raise self.ConstantError('const name %s must upper.' % key)
#         self.__dict__[key] = value
#
#     def __getstate__(self):
#         return {
#             '__dict__': self.__dict__,
#         }
#
#     def __setstate__(self, state):
#         self.__dict__ = state['__dict__']
#
# import sys
# sys.modules[__name__] = _const()
# from simulation.constant import const
#
#
# const.ALPH = .2


class Const:
    def __init__(self):
        self.ALPH = 2

const = Const()
