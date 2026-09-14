import numpy as np 
import scipy.spatial
from numba import jit
import shapely.geometry as sg

from .. import algorithm as alg

# 似乎无用
# def start(acoords, bcoords, d):
#     delta = np.array(bcoords - acoords)
#     ratio = d / distance(acoords, bcoords)
#     point = bcoords - ratio * delta
#     return point[0], point[1]


def quadratic(a, b, c):
    """ Quadratic equation with one unknown solver (a*x^2 + b*x + c = 0). """
    l = _quadratic_cal(a,b,c)
    if l is None:
        return []
    return l

@jit(nopython=True)
def _quadratic_cal(a, b, c):
    """ Quadratic equation with one unknown solver (a*x^2 + b*x + c = 0). """
    delta = b**2 - 4*a*c
    if abs(a) < 0.0000001:    
        return [-c / b] if abs(b) > 0.0000001 else None 
    elif abs(delta) < 0.0000001:
        return [-b / 2 / a]
    elif delta > 0:
        sqr = np.sqrt(delta)
        return [(-b + sqr) / 2 / a, (-b - sqr) / 2 / a]
    else:
        return None

@jit(nopython=True)
def quadratic1(a, b, c):
    """ Quadratic equation with one unknown solver (a*x^2 + b*x + c = 0). """
    # 只能用于 chase 函数, 无根情况返回了负值
    delta = b**2 - 4*a*c
    if abs(a) < 0.0000001:    
        return np.array([-c / b], dtype=np.float64) if abs(b) > 0.0000001 else np.array([-1], dtype=np.float64)
    elif abs(delta) < 0.0000001:
        return  np.array([-b / 2 / a], dtype=np.float64)
    elif delta > 0:
        sqr = np.sqrt(delta)
        return np.array([(-b + sqr) / 2 / a, (-b - sqr) / 2 / a], dtype=np.float64)
    else:
        return np.array([-1], dtype=np.float64)

@jit(nopython=True)
def perpfoot(a, b, c):
    """ Perpendicular foot from point c to line (a, b). 
    
    a: numpy.ndarray
    b: numpy.ndarray
    c: numpy.ndarray
    """
    if np.linalg.norm(a-b) < alg.EPSILON:
        return a 
    else:
        alpha = np.dot(b - a, c - a) / np.dot(b - a, b - a)
        return (1 - alpha)*a + alpha*b


@jit(nopython=True)
def distance(acoords, bcoords):
    """ The Euclidean distance between acoords and bcoords. """
    # return scipy.spatial.distance.euclidean(acoords, bcoords)
    return np.linalg.norm(acoords-bcoords) #比scipy中的距离函数更快一些，大约快1倍

def path_length(points):
    """输入路径点，计算路径的长度。
        使用时需要包含 单元的当前坐标

    Args:
        points (np.array): 坐标点的numpy数组

    Returns:
        float: 路径的长度
    """
    num = len(points)
    if num < 2:
        return 0
    else:
        ret = 0
        for i in range(1, num):
            ret += np.linalg.norm(points[i]-points[i-1])
        return ret


@jit(nopython=True)
def norm3d(arr):
    """ 计算三维向量的模(L2范数) """
    return np.sqrt(arr[0]**2+arr[1]**2+arr[2]**2)

def polar2coords(dis, az, pitch=0):
    """ 由距离、方位、俯仰计算点坐标 """
    az_rad = az * np.pi / 180
    pitch_rad = pitch * np.pi / 180
    z = dis * np.sin(pitch_rad)
    xy = dis * np.cos(pitch_rad)
    x = xy * np.sin(az_rad)
    y = xy * np.cos(az_rad)
    return np.array([x, y, z])


def polar_to_coords(center, distance, theta, phi=0):   
    """ 球坐标转换成直角坐标

    Args:
        theta: 表示与X轴逆时针夹角
    """
    theta, phi = map(lambda x: x * np.pi / 180.0, (theta, phi))
    x = distance * np.cos(phi) * np.cos(theta)
    y = distance * np.cos(phi) * np.sin(theta)
    z = distance * np.sin(phi)
    coords = np.array(center) + np.array([x, y, z])
    return coords


@jit(nopython=True)
def theta(coords):
    """ 计算向量coords与x轴的夹角，度 """
    az = np.arctan2(coords[1], coords[0])/np.pi*180
    if az < 0:
        az += 360
    return az


@jit(nopython=True)
def azimuth(coords1, coords2):
    """ 计算目标coord2对于本体coord1的方位角，度

    Args:
        coords1: list or np.ndarray, 2维或3维
        coords2: list or np.ndarray, 2维或3维
    
    Returns:
        方位角: 度
    """
    xx0 = coords2[0] - coords1[0]
    xx1 = coords2[1] - coords1[1]
    az = np.arctan2(xx0, xx1)/np.pi*180
    if az < 0:
        az += 360
    return az


@jit(nopython=True)
def pitch(coords1, coords2):
    """计算目标coords2对于本体coords1的俯仰角，度
    
    Args:
        coords1: np.ndarray, 3维
        coords2: np.ndarray, 3维

    Returns:
        俯仰角: 度 
    """
    vector = coords2 - coords1 
    xy = np.linalg.norm(vector[:2])
    theta = np.arctan(vector[2]/xy) # 与z轴的顺时针夹角，但xy恒为正
    return np.rad2deg(theta)

@jit(nopython=True)
def angle_add(az1, az2, rad=False):
    res = az1 + az2
    if rad:
        thres = 2 * np.pi
    else:
        thres = 360.0
    while res > thres:
        res -= thres
    while res < 0:
        res += thres
    return res

@jit(nopython=True)
def angle_add_mat(az1, az2, rad=False):
    res = az1 + az2
    if rad:
        thres = 2 * np.pi
    else:
        thres = 360.0
    while np.any(res > thres):
        res[np.where(res > thres)] -= thres
    while np.any(res < 0):
        res[np.where(res < 0)] += thres
    return res

def get_xy_reckon(xy,dis,az):
    """
    基于xy 根据距离方位计算新的点
    Args:
        xy(list): xy坐标
        dis(float): 单位KM
        az(float): 单位-度

    Returns:
            新的点坐标，只有x,y
    """
    az_rad = az * np.pi / 180
    x1 = xy[0]+dis*np.cos(az_rad)
    y1 = xy[1]+dis*np.sin(az_rad)
    return x1,y1

@jit(nopython=True)
def reckon(coords, dis, az):
    """根据距离方位计算新的点

    Args:
        coords (np.array): 坐标，二维、三维均可
        dis (float): 单位m
        az (float): 单位-度

    Returns:
        np.array: 新的点坐标，只有x,y
    """
    az_rad = az * np.pi / 180
    new_coords = coords.copy()
    new_coords[0] += dis*np.sin(az_rad)
    new_coords[1] += dis*np.cos(az_rad)
    return new_coords

# @jit(nopython=True)
# numba/np/arrayobj.py 中 np_repeat函数中没有axis参数, 后面在考虑优化
def reckon_mat(coords, dis, az):
    """ 根据距离方位计算新的点, dis 和 az 可以为数组
    
    Returns:
        输出点的维度与输入一致
    """
    az_rad = az * np.pi / 180
    new_coords = np.expand_dims(coords, axis=0).repeat(dis.shape[0], axis=0)
    new_coords[:,0] += np.multiply(dis, np.sin(az_rad))
    new_coords[:,1] += np.multiply(dis, np.cos(az_rad))
    return new_coords

@jit(nopython=True)
def TCL(ci, ri, vi, cj, rj, vj):
    """ Returns the predicted collision time (Time-to-CoLlision).

    Args:
        ci(np.ndarray): sphere i center coordinates.
        ri(float): sphere i radius.
        vi(np.ndarray): sphere i velocity. 
        cj(np.ndarray): sphere j center coordinates.
        rj(float): sphere j radius.
        vj(np.ndarray): sphere j velocity. 
    
    Returns:
        -1.0: collision won't happen.
        0.0: two sphere are overlapping. 
        secs: collision time
    """
    s = cj - ci 
    v = vj - vi 
    r = rj + ri

    c = np.dot(s, s) - r*r 
    if c <= 0:      # overlapping  
        return 0.0 

    a = np.dot(v, v) 
    if a < alg.EPSILON: # relative static
        #print("relative static !!!")
        return -1.0   

    b = np.dot(s, v) 
    if b >= 0:      # moving far away
        #print("moving far away!!!")
        return -1.0   

    d = b*b - a*c  
    if d < 0:       # no real root
        #print(b,a,c,ri,rj,"no real root!!!")
        return -1.0   

    # return the earliest collsion time
    return (-b - np.sqrt(d)) / a  


@jit(nopython=True)
def is_collided(mc, mv, period, tc, tv=np.array([0, 0, 0]), coef=5.0):
    """ 碰撞检测

    计算在未来period时间内，m和t是否发生碰撞

    Args:
        mc: 我方位置
        mv: 我方速度
        period: 我方的更新周期(s)
        tc: 目标位置
        tv: 目标速度
        coef: 碰撞检测系数，似乎最小可设为0.5，待研究; 默认为5，确保碰撞
    Returns:
        在未来_period时间内是否碰撞
    """
    # assert period > 0
    _period = coef * period
    m_speed = np.linalg.norm(mv)
    t_speed = np.linalg.norm(tv)
    # r = (m_speed + t_speed) * period * coef
    mr = m_speed * _period * coef
    tr = t_speed * _period * coef
    t = alg.geo.TCL(mc, mr, mv, tc, tr, tv)
    return (0 <= t <= _period)


def line_cross_line(x1, y1, x2, y2, u1, v1, u2, v2):
    """ 计算两条线段之间的交点
    
    Args:
        x1, y1, x2, y2: 线段1
        u1, v1, u2, v2: 线段2

    Returns:
        is_cross: 是否相交
        cross: 交点，可能不在线段上，None为无交点(即平行)
        t1: 以线段1为单位距离，交点距线段1起点的距离，负则反方向，None为无交点(即平行)
        t2: 以线段2为单位距离，交点距线段2起点的距离，负则反方向，None为无交点(即平行)
    """
    is_cross = False
    cross = None
    t1 = None
    t2 = None
    s = (y2-y1)*(u2-u1) - (x2-x1)*(v2-v1)
    if abs(s) > alg.EPSILON:
        t1 = ((v1-y1)*(u2-u1) - (u1-x1)*(v2-v1)) / s
        t2 = -((y1-v1)*(x2-x1) - (x1-u1)*(y2-y1)) / s
        cross_x = x1 + (x2-x1)*t1
        cross_y = y1 + (y2-y1)*t1
        cross = [cross_x, cross_y]
        if 0 <= t1 <= 1 and 0 <= t2 <= 1:
            is_cross = True
    return is_cross, cross, t1, t2


def ray_cross_curve(points, pos, az):
    """ 计算射线与曲线的交点 """

    curve = sg.LineString(points)
    P = sg.Point(pos)
    M = curve.hausdorff_distance(P)*2
    P1 = sg.Point(pos[0]+M*np.sin(az/180*np.pi), pos[1]+M*np.cos(az/180*np.pi))
    out = curve.intersection(sg.LineString([P, P1]))
    if out.geom_type == "Point": 
        dis = distance(out.coords[0], P.coords[0])
        return out.coords[0], dis
    else:
        return None
        

@jit(nopython=True)
def angle_diff(az1, az0):
    """ 角度相减，返回(-180, 180] 
    """
    az = (az1 - az0) % 360
    if az > 180:
        az -= 360
    return az


@jit(nopython=True)
def angle_diff2(az1, az0):
    """ 角度相减，返回[0, 360) 
    
    即从az0到az1的顺时针夹角
    """
    az = (az1 - az0) % 360
    return az


def in_angle_range(az, range):
    """判断az是否在顺时针劣弧角度范围range内
    """
    deg = angle_diff(range[1], range[0])
    assert deg > 0, "range必须为劣弧"
    cond1 = (0 <= angle_diff(az, range[0]) <= deg)
    cond2 = (0 <= angle_diff(range[1], az) <= deg)
    return cond1 and cond2


def in_angle_range2(az, range):
    """判断az是否在顺时针角度范围range内,不限于劣弧
    """
    deg = angle_diff2(range[1], range[0])
    cond1 = (0 <= angle_diff2(az, range[0]) <= deg)
    cond2 = (0 <= angle_diff2(range[1], az) <= deg)
    return cond1 and cond2
      

def line_cross_vertical_rect(point1:list, point2:list, rect_points:list = None):
    """ 空间中两点定义的线段是否穿过斜对角两点定义的铅垂面矩形

    Args:
        point1:list            点1坐标
        point2:list            点2坐标
        rect_points:list       铅垂面矩形(斜对角的两个点，2*3)
    输出：
        across:bool                 是否穿过
        cross_loc                   交点坐标
    """
    point1 = np.array(point1)
    point2 = np.array(point2)
    rect_points = np.array(rect_points)
    #平面方程 Px+Qy+R=0
    P = rect_points[1][1] - rect_points[0][1]
    Q = rect_points[0][0] - rect_points[1][0]
    R = rect_points[1][0]*rect_points[0][1] - rect_points[0][0]*rect_points[1][1]
    if abs(P*(point1[0] - point2[0]) + Q*(point1[1] - point2[1])) <= 1e-6:
        t = (P*point2[0] + Q*point2[1] + R) / (P*(point2[0] - point1[0]) + Q*(point2[1] - point1[1]) + 1e-6)
    else :
        t = (P*point2[0] + Q*point2[1] + R) / (P*(point2[0] - point1[0]) + Q*(point2[1] - point1[1]))
    cross_loc = np.array([point2[0] + t*(point1[0] - point2[0]), point2[1] + t*(point1[1] - point2[1]), point2[2] + t*(point1[2] - point2[2])])
    if (t >= 0 and min(rect_points[0][0], rect_points[1][0]) <= cross_loc[0] <= max(rect_points[0][0], rect_points[1][0]) 
        and min(rect_points[0][1], rect_points[1][1]) <= cross_loc[1] <= max(rect_points[0][1], rect_points[1][1]) 
        and min(rect_points[0][2], rect_points[1][2]) <= cross_loc[2] <= max(rect_points[0][2], rect_points[1][2])):
        across = True
    else:
        across = False
    return across, cross_loc


def _cal_bins_index(xs, left, right, interval, inverse=False):
    """ 将数组放在等间隔的桶内，返回数组下标
    """
    n = int(np.ceil((right-left)/interval))
    out = [[] for _ in range(n)]
    for ind, x in enumerate(xs):
        if not inverse: 
            i = int(np.floor((x-left)/interval))
        else:
            i = int(np.floor((right-x)/interval))
        if 0 <= i < n:
            out[i].append(ind)
    return out

def cal_bins_index(xs, left, right, interval, inverse=False, overlap=False):
    """ 将数组放在等间隔的桶内，返回数组下标

    Args:
        inverse: 是否逆序
        overlap: 是否50%重叠
    """
    out1 = _cal_bins_index(xs, left, right, interval, inverse)
    if not overlap:
        return out1
    else:
        out2 = _cal_bins_index(xs, left+0.5*interval, right-0.5*interval, interval, inverse)
        n = len(out1)
        out = []
        for i in range(n-1):
            # 通过重叠合并,否则弃用重叠
            if set(out1[i]+out1[i+1]) == set(out2[i]):
                out1[i] = []
                out1[i+1] = []
            else:
                out2[i] = []
        for i in range(n-1):
            if out1[i]:
                out.append(out1[i])
            if out2[i]:
                out.append(out2[i])
        if out1[n-1]:
            out.append(out1[n-1]) # 弃用out2的最后一个（如果有）
        return out


# @jit(nopython=True)
def region_product(A):
    """
    计算区间上的系数乘积


    Parameters:
    A - numpy.array,形如[[a0,b0,c0],[a1,b1,c1],...], [ai,bi]可为任意区间，ci为对应区间上的系数


    Returns:
    返回一个numpy数组[[m0,n0,h0],[m1,n1,h1],...],其中[mi,ni]均为[0,360]上的区间，hi为区间上对应的系数

    """
    param = []  # 换算到[0, 360]上的区间及区间上系数的列表
    temp = []  # 临时
    for i in range(len(A)):
        if A[i][1] - A[i][0] >= 360:
            #             A[i][0] = 0
            #             A[i][1] = 360
            param.append([0, 360, A[i][2]])
        elif A[i][1] // 360 == A[i][0] // 360:
            #             A[i][0]= A[i][0] % 360
            #             A[i][1] = A[i][1] % 360
            param.append([A[i][0] % 360, A[i][1] % 360, A[i][2]])
        elif A[i][1] // 360 != A[i][0] // 360:
            # [A[i][0] %360, 360, A[i][2]],[0, A[i][1] % 360, A[i][2]]
            param.append([A[i][0] % 360, 360, A[i][2]])
            param.append([0, A[i][1] % 360, A[i][2]])
    for j in range(len(param)):
        temp.append(param[j][0])
        temp.append(param[j][1])

    def f(x0, a0, b0, c0):
        return c0 if a0 <= x0 <= b0 else 1

    temp = sorted(list(set(temp)))
    region = list(zip(temp[:-1], temp[1:]))  # 去重后区间
    output = [[0, region[0][0], 1]]

    for r1, r2 in region:
        coef = 1
        x = (r1 + r2) / 2
        for i in range(len(param)):
            coef *= f(x, param[i][0], param[i][1], param[i][2])
        output.append([r1, r2, coef])
    output.append([region[-1][1], 360, 1])
    for o in output:
        if o[0] % 360 == o[1] % 360:  #
            output.remove(o)
    if output[0][2] == output[-1][2]:
        output[-1][1] = output[0][1]
        output.remove(output[0])
    # output = np.array(output)
    return output
