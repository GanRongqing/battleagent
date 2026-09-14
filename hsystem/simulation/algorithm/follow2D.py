import numpy as np
from numba import jit


@jit(nopython=True)
def angle_theta(vect: np.ndarray):
    """
    计算xy平面航向角 

    Args:
        vect (np.ndarray): 1*3的np.ndarray向量

    Returns:
        float: 与(1,0)的夹角，单位：角度制，[0,360]
    """
    theta = np.arctan2(vect[0, 1], vect[0, 0])
    theta = (theta*180/np.pi) % 360
    return theta
