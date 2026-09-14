""" 算法模型
"""
EPSILON = 1e-6   #epsilon,接近零的极小数

# 非常奇怪，必须在此处（或者在仿真脚本处）引入下述几个包，否则会报错
# RuntimeWarning: numpy.ufunc size changed, may indicate binary incompatibility. Expected 192 from C header, got 216 from PyObject
import numpy as np
import pandas
from scipy.optimize import root
import scipy.spatial
import scipy.interpolate
import networkx
import warnings
import timeit
warnings.filterwarnings("error", category=RuntimeWarning)

from . import geometry as geo
from . import transform as trf
from . import shape as shape
from . import drive
from . import marker
from . import detection
from . import geodesy as geod
from . import follow2D as fol2d # 应用其中求航向的函数


class TestTime:
    def __init__(self):
        self.begin_time = 0
    
    def __enter__(self):
        self.begin_time = timeit.default_timer()
        
    def __exit__(self, exc_ty, exc_val, tb):
        end_time = timeit.default_timer()
        print(f"耗时:{end_time-self.begin_time}s")
