""" 操控平台运动模型
"""
import math
from turtle import st
from typing import Tuple, List

import numpy as np
import pandas
import pyproj
from numba import jit

from .. import algorithm as alg


@jit(nopython=True)
def velocity(speed, acoords, bcoords):
    """calculate speed on each axises. 三维"""
    # acoords = np.array(acoords)
    # bcoords = np.array(bcoords)
    # delta = np.array(bcoords - acoords)
    delta = bcoords - acoords
    if delta[0] == 0:
        if delta[1] == 0:
            vx = 0
            vy = 0
            vz = speed
        else:
            vx = 0
            vy = np.sign(delta[1])*np.sqrt(speed**2 / (1 + (delta[2] / delta[1])**2))
            vz = vy * delta[2] /  delta[1]
    else:
        vx =np.sign(delta[0])*np.sqrt(speed**2 / (1 + (delta[1] / delta[0])**2 + (delta[2] / delta[0])**2))
        vy = vx * delta[1] / delta[0]
        vz = vx * delta[2] / delta[0]
    vec = np.array([vx, vy, vz])
    # assert np.isclose(np.sqrt(np.sum(vec ** 2)), speed) == True
    return vec


def velocity2(speed, acoords, bcoords):
    """calculate speed on each axises. 二维"""
    acoords = np.array(acoords)
    bcoords = np.array(bcoords)
    delta = np.array(bcoords - acoords)
    if delta[0] == 0:
            vx = 0
            vy = speed
    else:
        vx =np.sign(delta[0])* np.sqrt(speed**2 / (1 + (delta[1] / delta[0])**2))
        vy = vx * delta[1] / delta[0]
    vec = np.array([vx, vy])
    assert np.isclose(np.sqrt(np.sum(vec ** 2)), speed) == True
    return vec

@jit(nopython=True)
def velocity3(speed, acoords, bcoords):
    delta = bcoords - acoords
#     l=np.linalg.norm(delta)
    l = alg.geo.norm3d(delta)
    if l == 0:
        return np.array([0.,0.,0.])
    v=speed/l * delta
    return  v

def v_change_az(velocity, az):
    '''改变速度方向,二维/三维均可'''
    az_rad = az * np.pi / 180
    vxy = np.sqrt(velocity[0]**2 + velocity[1]**2)
    vx = vxy * np.sin(az_rad)
    vy = vxy * np.cos(az_rad)
    v = velocity.copy()
    v[0] = vx
    v[1] = vy
    return v

def speed2vel(speed, az):
    az_rad = az * np.pi / 180
    vx = speed * np.sin(az_rad)
    vy = speed * np.cos(az_rad)
    return np.array([vx, vy, 0], dtype=np.float64)

def waypsgenerate(ship_corrds, foe_corrds, N, H, v):

    ship_corrds = np.array(ship_corrds, dtype=float)
    foe_corrds = np.array(foe_corrds, dtype=float)

    dis_vector = foe_corrds - ship_corrds

    waypoints = np.zeros((len(N), 3))
    stagevelocity = np.zeros(len(N))

    if sum(N) != 1:
        RuntimeError('Stage Divied Error!')

    for i in range(len(N)):
        if i>=1:
            N[i] = N[i-1] + N[i]

    waypoints[0,:] = ship_corrds
    waypoints[0,2] = H[0]
    stagevelocity[0] = v[0]
    for i in range(1,len(H)):
        waypoints[i,:] = ship_corrds + dis_vector * N[i-1]
        waypoints[i,2] = H[i]
        stagevelocity[i] = v[i]

    return waypoints, stagevelocity


def turnPointsCal(coords, course, theta, center=None, radius=None, clockwise=True):
    '''转弯参数解算，生成圆周位置列表
    coords:实体当前位置
    course:实体当前航向
    theta:拟转弯角度
    center:转弯中心点位置，静态
    radius:转弯半径
    clockwise:是否顺时针
    '''
    clockwise = 1 if clockwise else -1
    if center is not None:
        radius = alg.geo.distance(coords[:2], center[:2])
    elif radius is not None:
        _az = course + 90 * clockwise
        center = alg.geo.reckon(coords, radius, _az)
    else:
        raise RuntimeError("radius and center are None")
    az0 = alg.geo.azimuth(center, coords) # 从圆心指向起始转弯点的方位角
    points = []
    for t in range(int(theta)):
        az1 = az0 + t * clockwise
        coords = alg.geo.reckon(center, radius, az1)
        points.append(coords)
    return points


def path8PointsCal(coords, course, az, center=None, radius=None, clockwise=True):
    '''8字型机动(两个圆)参数解算，生成位置列表
    coords:实体当前位置
    course:实体当前航向
    az:第二个圆的圆心相对于第一个圆的圆心的方位角
    center:第一个圆的转弯中心点位置，静态
    radius:第一个圆的转弯半径
    clockwise:第一个圆转弯时是否顺时针
    '''
    clockwise = 1 if clockwise else -1
    if center is not None:
        radius = alg.geo.distance(coords[:2], center[:2])
    elif radius is not None:
        _az = course + 90 * clockwise
        center = alg.geo.reckon(coords, radius, _az)
    else:
        raise RuntimeError("radius and center are None")
    #计算从当前位置到第一个圆与第二个圆相交的位置之间的点
    az = az % 360
    az0 = alg.geo.azimuth(center, coords) #从圆心指向起始转弯点的方位角
    if clockwise == 1:
        theta = alg.geo.angle_diff2(az, az0)
    else:
        theta = alg.geo.angle_diff2(az0, az)
    points = []
    for t in range(int(theta)):
        az1 = az0 + t * clockwise
        coords = alg.geo.reckon(center, radius, az1)
        points.append(coords)
    #计算第二个圆的位置点
    center2 = alg.geo.reckon(center, 2*radius, az)#第二个圆的圆心
    for t in range(360):
        az2 = (az+180) - t * clockwise
        coords = alg.geo.reckon(center2, radius, az2)
        points.append(coords)
    #计算从第一个圆与第二个圆相交的位置之间的点到起点之间的位置点
    for t in range(int(theta), 360):
        az1 = az0 + t * clockwise
        coords = alg.geo.reckon(center, radius, az1)
        points.append(coords)
    return points

def path0PointsCalOld(coords, course, az, center=None, radius=None, clockwise=True):
    clockwise = 1 if clockwise else -1
    length = 150 * 1000
    _az = course + 90 * clockwise
    center = alg.geo.reckon(coords, radius, _az)

    points = []
    for t in range(180):
        az1 = az + t * clockwise
        coords = alg.geo.reckon(center, radius, az1)
        points.append(coords)

    center2 = alg.geo.reckon(center, length, az+270)#第二个圆的圆心
    for t in range(180):
        az2 = az+180 + t * clockwise
        coords = alg.geo.reckon(center2, radius, az2)
        points.append(coords)

    coords = alg.geo.reckon(center, radius, az)
    points.append(coords)   

    return points


def path0PointsCal(coords, course, az, length, width, center=None, radius=None, clockwise=True, init_dis=None):
    '''跑道型型机动(两个圆)参数解算，生成位置列表'''
    clockwise = 1 if clockwise else -1
    init_coords = coords.copy()
    radius = width / 2
    new_length = length - width
    points = []
    if init_dis is None:
        _az = course + 90 * clockwise
        center = alg.geo.reckon(coords, radius, _az)
        _az1 = az
        if np.sin((course-az)*clockwise*np.pi/180)>=0:
            _az1 = _az1 + 180
        center2 = alg.geo.reckon(center, new_length, _az1)#第二个圆的圆心

        range1 = int(az - course) * clockwise
        while range1 <= 0:
            range1 += 180

        for t in range(range1):
            az1 = course - 90 * clockwise + t * clockwise
            coords = alg.geo.reckon(center, radius, az1)
            points.append(coords)

        for t in range(180):
            az2 = course - 90 * clockwise + clockwise * range1 + t * clockwise
            coords = alg.geo.reckon(center2, radius, az2)
            points.append(coords)

        for t in range(180 - range1):
            az1 = course - 90 * clockwise + clockwise * range1 + 180 * clockwise + t * clockwise
            coords = alg.geo.reckon(center, radius, az1)
            points.append(coords)
    else:
        assert init_dis <= new_length
        points.append(init_coords)
        coords1 = alg.geo.reckon(init_coords, init_dis*clockwise, az)
        points.append(coords1)
        sign = np.sign(init_dis)
        _az1 = az
        if clockwise:
            _az1 = _az1 + 180
        if init_dis < 0:
            _az1 = _az1 + 180
        center1 = alg.geo.reckon(coords1, radius, _az1 - 90)
        center2 = alg.geo.reckon(center1, new_length, _az1 - 90 + 90 * clockwise) # 第二个圆的圆心

        for t in range(180):
            az1 = _az1 + 90 + t * clockwise
            coords = alg.geo.reckon(center1, radius, az1)
            points.append(coords)

        for t in range(180):
            az1 = _az1 + 90 + 180 * clockwise + t * clockwise
            coords = alg.geo.reckon(center2, radius, az1)
            points.append(coords)
            
        points.append(init_coords)

    return points

#####下属几个函数弃而未用
def cruise_round(center=[0, 0, 0], center_speed=[0, 0, 0], locate=[0, 0, 0], locate_speed=[0, 0, 0], r=0):
    """依参考点圆周运动仿真模块
        data : array : [0, 1, 2]
            0 : center : xyz
            1 : location : xyz
            2 : speed : xyz
        return : acce : xyz
    """
    def get_length(data):
        return np.linalg.norm(data)
    rela_locate = np.array(locate) - np.array(center)
    speed = np.array(locate_speed) - np.array(center_speed)
    speed_2 = np.cross(rela_locate, speed)
    rela_locate_l = get_length(rela_locate)
    speed_2 = get_length(speed_2)**2 / rela_locate_l **3
    xx, yy, zz = rela_locate
    acce_x = -speed_2 / rela_locate_l * xx
    acce_y = -speed_2 / rela_locate_l * yy
    acce_z = -speed_2 / rela_locate_l * zz
    acce = np.array([acce_x, acce_y, acce_z], dtype=float)
    if rela_locate_l > r:
        return  acce * 1.3
    elif rela_locate_l < r:
        return acce * 0.97
    else:
        return acce

def oval_cal(center:Tuple[float,float,float]=None, az:Tuple[float,float,float]=None, clockwise:bool=True) -> List[Tuple]:
    """生成固定区域内的椭圆位置列表

    Args:
        center(tuple[float,float,float]): 中心点位置坐标(x,y,h)
        az(tuple[float,float,int]): 区域长,宽，角度
        clockwise(bool):是否顺时针
    """
    t = np.arange(0, 2 * np.pi, 0.2)
    # 生成椭圆点
    x = np.cos(t) * (az[0] /2)
    y = np.sin(t)* (az[1] / 2)
    rotAngle = az[2] * np.pi / 180
    # 旋转角度
    xx = np.cos(rotAngle) * x + np.sin(rotAngle) * y
    yy = -np.sin(rotAngle) * x + np.cos(rotAngle) * y
    # 添加偏移量
    xxx = xx + center[0]
    yyy = yy + center[1]

    if clockwise:
        xxx = xxx[::-1]
        yyy = yyy[::-1]
    res = []
    for i in range(len(xxx)):
        res.append(np.array([xxx[i], yyy[i],center[2]]))
    return res


def rectangular_circle_cal(width,length,speed,period,coords) -> List:
    '''
        计算矩形上的点

        Args:
            width(float): 矩形的宽
            length(float): 矩形的长
            speed(float): 速度
            period(int): 周期
            coords(tuple): 方位
    '''
    points = []
    num = math.floor(abs(width) / (speed * period))
    for i in range(num):
        y = coords[1] + speed * period * i
        points.append([coords[0], y, coords[2]])
    points.append([coords[0], coords[1] + width, coords[2]])

    num = math.floor(abs(length) / (speed * period))
    for i in range(num):
        x = coords[0] + speed * period * i
        points.append([x, coords[1] + width, coords[2]])
    points.append([coords[0] + length, coords[1] + width, coords[2]])

    num = math.floor(abs(width) / (speed * period))
    for i in range(num):
        y = coords[1] + width - speed * period * i
        points.append([coords[0] + length, y, coords[2]])
    points.append([coords[0] + length, coords[1], coords[2]])

    num = math.floor(abs(width) / (speed * period))
    for i in range(num):
        x = coords[0] + length - speed * period * i
        points.append([x, coords[1], coords[2]])
    points.append([coords[0], coords[1], coords[2]])
    return points

def pointsCal(coords, speed, points):
    '''
    '''
    plan = []
    t = 0
    delta = 0
    start = coords
    for point in points:
        t += delta
        v = alg.drive.velocity(speed, start, point)
        delta = alg.geo.distance(start, point)/speed
        start = point
        plan.append((t, v))
    t += delta
    plan.append((t, v))
    return plan


def turnCal(coords, course, speed, theta, center=None, radius=None, clockwise=True):
    '''转弯参数解算，生成时刻和对应的三维速度列表
    coords:实体当前位置
    course:实体当前航向
    speed:拟转弯速度
    theta:拟转弯角度
    center:转弯中心点位置，静态
    radius:转弯半径
    clockwise:是否顺时针
    '''
    clockwise = 1 if clockwise else -1
    az0 = course - 90 * clockwise # 从圆心指向起始转弯点的方位角
    if center is not None:
        radius = alg.geo.distance(coords[:2], center[:2])
    elif radius is not None:
        az = course + 90 * clockwise
        center = alg.geo.reckon(coords[:2], radius, az)
    else:
        raise RuntimeError("radius and center are None")
    az0 = alg.geo.azimuth(center, coords) # 从圆心指向起始转弯点的方位角
    plan = []
    time = radius * theta / 180 * np.pi / speed
    for t in range(int(time)):
        dis = speed * t
        cnt_theta = dis / radius / np.pi * 180
        az1 = az0 + cnt_theta * clockwise
        v_az = az1 + 180 - 90 * clockwise
        velocity = alg.geo.polar2coords(speed, v_az)
        plan.append((t, velocity))
    return plan