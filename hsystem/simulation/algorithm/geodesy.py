import numpy as np
import pyproj

GEOD = pyproj.Geod(ellps="WGS84")


def range_(from_, to, unit="m"):
    # 获取两点间里程（单位：米或海里）
    forward_az, back_az, dist = GEOD.inv(from_[0], from_[1], to[0], to[1])
    if unit == "nmile":
        dist = dist/1852.0
    return dist


def bearing(from_,to):
    # 获取目标位置相对于参考位置的方位（单位：度）
    forward_az, back_az, dist = GEOD.inv(from_[0], from_[1], to[0], to[1])
    return forward_az


def get_point_from_bearing(longitude, latitude, bearing, distance, unit="m"):
    # 通过相对一点的方位、距离获取另一点的经纬度坐标。
    if unit == "nmile":
       distance = distance * 1852.0
    outlon, outlat, back_az = GEOD.fwd(longitude, latitude, bearing, distance)
    return outlon, outlat


def get_circle_from_point(longitude, latitude, radius, numpoints, unit="m"):
    # 获取以某点为中心指定半径的圆上均匀分布点的经纬度值
    if unit == "nmile":
        radius = radius * 1852.0
    azs = np.linspace(0, 360, numpoints)
    lons = []
    lats = []
    for az in azs:
        _lon, _lat, back_az = GEOD.fwd(longitude, latitude, az, radius)
        lons.append(_lon)
        lats.append(_lat)
    return lons, lats