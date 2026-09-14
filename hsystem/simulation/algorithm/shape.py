# import shapely as sh
# from shapely.geometry import Polygon
# from shapely.geometry.polygon import LinearRing
from shapely import geometry

import numpy as np

from .. import algorithm as alg


class Symbol(dict):
    """ 可视化绘制标记数据结构.

    Attributes
    ----------
    mode : Flag/Marker/Text/Line/Lines/Polygon/Polygons七种
    type_ : 类型名，如Radar、Ship等
    model : 平台或组件model
    name : 平台或组件name
    group : 角色，如RED、BLUE等
    text : 单独显示的文字
    icon: 图标名字，针对Flag和Marker
    x : x坐标
        当mode为时，为一个点
        当mode为Line/Polygon时，为list列表，但mode=Polygon时首末点不必重合
        当mode为Lines/Polygons时，为嵌套list列表
    y : y坐标，类似x
    lng: 经度，后续自动计算
    lat: 纬度，后续自动计算
    z : z坐标，类似x
    az : 方位
    color : 线的颜色
    line_width : 线的粗细
    alpha ： 线的透明度  
    fill_color : 填充颜色，如果为None，不填充
    fill_alpha : 填充透明度，如果为None，则以alpha为准
    marker_id : marker标识，和matplotlib保持一致
    """
    def __init__(self, **args):
        super().__init__({"mode":"", "type_":"", "model":"", "pos_type": "", "name":"", "group":"", "text":"", "icon":"",
                    "x":None, "y":None, "lng":None, "lat":None, "z":None, "az":None, "speed": None,
                    "color":None, "line_width":1, "alpha":None, "fill_color":None, "fill_alpha":None, "country":"",
                    "batch_no":"", "pmodel":"", "pitch":None, "r1": None, "r2": None, "az1": None, "az2": None,
                    "platform": None, "class_": None})
        self.update(args)


class Symbol3D(dict):
    """ 可视化绘制标记数据结构.

    Attributes
    ----------
    id: 唯一识别符
    mode : Flag/Marker/Text/Line/Polygon/Cylinder/Ellipsoid
    type_ : 类型名，如Radar、Ship等
    model : 平台或组件model
    name : 平台或组件name
    group : 角色，如RED、BLUE等
    text : 单独显示的文字
    icon: 图标名字，针对Flag和Marker
    x : x坐标
        当mode为Flag/Marker/Text/Cylinder/Ellipsoid时，为一个点
        当mode为Line/Polygon时，为list列表，但mode=Polygon时首末点不必重合
    y : y坐标，类似x
    lng: 经度，后续自动计算
    lat: 纬度，后续自动计算
    z : z坐标，类似x
    az : 方位角
    pitch: 俯仰角
    gamma: 滚转角
    kwargs: {}, 如果是Cylinder，包括top_radius, bottom_radius, height
                在bigemap中，bottom的圆心为参考点，正上放置
                在此处，以bigemap中的为准
                如果是Ellipsoid，包括outXradius, outYradius, outZradius,
                                inXradius, inYradius, inZradius,
                                clock_begin, clock_end,
                                cone_begin, cone_end
                在bigemap中，clock以正东为起始方向，逆时针；cone以正上为0，正下180度，超过180度则折回
                在此处，clock以正北为起始方向，顺时针；cone正上为90度，正下为-90度，并限制在-90到90之间，由地图服务端做转换
    color : 线的颜色
    line_width : 线的粗细
    alpha ： 线的透明度  
    fill_color : 填充颜色，如果为None，不填充
    fill_alpha : 填充透明度，如果为None，则以alpha为准
    """
    def __init__(self, **args):
        super().__init__({"id":None, "mode":"", "type_":"", "model":"", "name":"", "group":"", "text":"", "icon":"",
                    "x":None, "y":None, "lng":None, "lat":None, "z":None, "az":None, "pitch":0, "gamma":0,
                    "kwargs": {},
                    "color":None, "line_width":1, "alpha":None, "fill_color":None, "fill_alpha":None})
        self.update(args)


class PolygonShape(geometry.Polygon):
    # 修改名称防止和其他库冲突
    def plot(self, ax, *args, **kwargs):
        x, y = self.exterior.xy
        ax.plot(x, y, *args, **kwargs)

    def fill(self, ax, *args, **kwargs):
        x, y = self.exterior.xy
        ax.fill(x, y, *args, **kwargs)

    def fillSymbol(self, **kwargs):
        x, y = self.exterior.xy
        symbol = Symbol(mode="Polygon", x=list(x), y=list(y))
        symbol.update(kwargs)
        return symbol


def gen_shape(center, r0, r1, az1=0, az2=360):
    if r0 == 0 and (az2-az1)%360 == 0:
        return Circle(center, r1)
    if r0 == 0:
        return Sector(center, r1, az1, az2)
    if (az2-az1)%360 == 0:
        return CircleRing(center, r0, r1)
    return SectorRing(center, r0, r1, az1, az2)


class Circle(geometry.Polygon):
    def __init__(self, center, r):
        assert r > 0
        self.center = center
        self.r = r
        degrees = np.array(range(0, 360, 3), dtype=np.float64)
        x = center[0] + r * np.sin(np.deg2rad(degrees))
        y = center[1] + r * np.cos(np.deg2rad(degrees))
        points = list(zip(x, y))
        super().__init__(points)

    def plot(self, ax, *args, **kwargs):
        # import pdb; pdb.set_trace()
        x, y = self.exterior.xy
        ax.plot(x, y, *args, **kwargs)

    def fill(self, ax, *args, **kwargs):
        x, y = self.exterior.xy
        ax.fill(x, y, *args, **kwargs)

    def fillSymbol(self, **kwargs):
        x, y = self.exterior.xy
        symbol = Symbol(mode="Polygon", x=list(x), y=list(y))
        symbol.update(kwargs)
        return symbol


class Sector(geometry.Polygon):
    def __init__(self, center, r, az1, az2):
        assert r > 0
        self.center = center
        self.r = r
        self.az1 = az1
        self.az2 = az2 if az2 > az1 else az2 + 360
        assert self.az2 != self.az1
        n = int(np.ceil(self.az2-self.az1) + 2) // 3
        degrees = np.linspace(self.az1, self.az2, n)
        x = center[0] + r * np.sin(np.deg2rad(degrees))
        y = center[1] + r * np.cos(np.deg2rad(degrees))
        x = x.tolist()
        y = y.tolist()
        x.append(center[0])
        y.append(center[1])
        points = list(zip(x, y))
        super().__init__(points)

    def plot(self, ax, *args, **kwargs):
        x, y = self.exterior.xy
        ax.plot(x, y, *args, **kwargs)

    def fill(self, ax, *args, **kwargs):
        x, y = self.exterior.xy
        ax.fill(x, y, *args, **kwargs)

    def fillSymbol(self, **kwargs):
        x, y = self.exterior.xy
        symbol = Symbol(mode="Polygon", x=list(x), y=list(y))
        symbol.update(kwargs)
        return symbol


class CircleRing(geometry.Polygon):
    def __init__(self, center, r1, r2):
        assert r2 > r1 > 0
        self.center = center
        self.r1 = r1
        self.r2 = r2
        degrees = np.array(range(360), dtype=np.float64)
        x = center[0] + r1 * np.sin(np.deg2rad(degrees))
        y = center[1] + r1 * np.cos(np.deg2rad(degrees))
        points = list(zip(x, y))
        ring = geometry.polygon.LinearRing(points)
        degrees = np.array(range(360), dtype=np.float64)
        x = center[0] + r2 * np.sin(np.deg2rad(degrees))
        y = center[1] + r2 * np.cos(np.deg2rad(degrees))
        points = list(zip(x, y))
        super().__init__(points, [ring])

    def plot(self, ax, *args, **kwargs):
        x2, y2 = self.exterior.xy
        x1, y1 = self.interiors[0].xy
        ax.plot(x2, y2, *args, **kwargs)
        ax.plot(x1, y1, *args, **kwargs)

    def fill(self, ax, *args, **kwargs):
        x2, y2 = self.exterior.xy
        x1, y1 = self.interiors[0].xy
        x = x2.tolist() + x1[::-1].tolist() + [x2[0]]
        y = y2.tolist() + y1[::-1].tolist() + [y2[0]]
        ax.fill(x, y, *args, **kwargs)

    def fillSymbol(self, **kwargs):
        x2, y2 = self.exterior.xy
        x1, y1 = self.interiors[0].xy
        x = x2.tolist() + x1[::-1].tolist() + [x2[0]]
        y = y2.tolist() + y1[::-1].tolist() + [y2[0]]
        symbol = Symbol(mode="Polygon", x=list(x), y=list(y))
        symbol.update(kwargs)
        return symbol


class SectorRing(geometry.Polygon):
    def __init__(self, center, r1, r2, az1, az2):
        assert r2 > r1 > 0, "r1:{},r2:{}".format(r1,r2)
        self.center = center
        self.r1 = r1
        self.r2 = r2
        self.az1 = az1
        self.az2 = az2 if az2 > az1 else az2 + 360
        assert self.az2 != self.az1
        n = int(np.ceil(self.az2-self.az1) + 2)
        degrees = np.linspace(self.az1, self.az2, n)
        x1 = center[0] + r1 * np.sin(np.deg2rad(degrees))
        y1 = center[1] + r1 * np.cos(np.deg2rad(degrees))
        x2 = center[0] + r2 * np.sin(np.deg2rad(degrees))
        y2 = center[1] + r2 * np.cos(np.deg2rad(degrees))
        x1 = x1.tolist(); y1 = y1.tolist()
        x2 = x2.tolist(); y2 = y2.tolist()
        x = x1[::-1] + x2
        y = y1[::-1] + y2
        points = list(zip(x, y))
        super().__init__(points)

    def plot(self, ax, *args, **kwargs):
        x, y = self.exterior.xy
        ax.plot(x, y, *args, **kwargs)

    def fill(self, ax, *args, **kwargs):
        x, y = self.exterior.xy
        ax.fill(x, y, *args, **kwargs)

    def fillSymbol(self, **kwargs):
        x, y = self.exterior.xy
        symbol = Symbol(mode="Polygon", x=list(x), y=list(y))
        symbol.update(kwargs)
        return symbol


def gen_shape(center,r1, r2, az1=0, az2=360):
    if r1 <= 0:
        if az1 == 0 and az2 == 360:
            shp = alg.shape.Circle(center, r2)
        else:
            shp = alg.shape.Sector(center, r2, az1, az2)
    else:
        if az1 == 0 and az2 == 360:
            shp = alg.shape.CircleRing(center, r1, r2)
        else:
            shp = alg.shape.SectorRing(center, r1, r2, az1, az2)
    return shp


class Rectangle(geometry.polygon.Polygon):
    @classmethod
    def gen_ref_rect(cls, ref, az, r1, r2, clockwise, width):
        """根据相对参考点的位置生成矩形
        ref:参考位置
        az:方位角，与Y轴的顺时针夹角
        r1:在方位线上矩形边的起点
        r2:在方位线上矩形边的终点
        clockwise:矩形另一边相对方位线是在顺时针一侧还是逆时针一侧,
            1 or clock:顺时针
            -1 or counterclock:逆时针
        width:矩形另一边的长度
        """
        assert r2 > r1 > 0
        if clockwise == "clock":
            tag = 1
        elif clockwise == "counterclock":
            tag = -1
        else:
            tag = clockwise

        x1 = ref[0] + r1 * np.sin(np.deg2rad(az))
        y1 = ref[1] + r1 * np.cos(np.deg2rad(az))
        x2 = ref[0] + r2 * np.sin(np.deg2rad(az))
        y2 = ref[1] + r2 * np.cos(np.deg2rad(az))
        x3 = x2 + width * np.sin(np.deg2rad(az + 90*tag))
        y3 = y2 + width * np.cos(np.deg2rad(az + 90*tag))     
        x4 = x1 + width * np.sin(np.deg2rad(az + 90*tag))
        y4 = y1 + width * np.cos(np.deg2rad(az + 90*tag))
        rect =  cls([[x1,y1], [x2, y2], [x3, y3], [x4, y4]])
        return rect

    @classmethod
    def gen_center_rect(cls, center, length, width, az):
        """根据矩形中心点位置生成矩形
        ref:参考位置
        length: 长边
        width: 短边
        az:长边方位角，与Y轴的顺时针夹角
        """
        x0 = center[0]
        y0 = center[1]
        x1, y1 = alg.rotation.rotate_theta(x0 + length / 2, y0 + width / 2, az-90, x0, y0)
        x2, y2 = alg.rotation.rotate_theta(x0 + length / 2, y0 - width / 2, az-90, x0, y0)
        x3, y3 = alg.rotation.rotate_theta(x0 - length / 2, y0 - width / 2, az-90, x0, y0)
        x4, y4 = alg.rotation.rotate_theta(x0 - length / 2, y0 + width / 2, az-90, x0, y0)
        rect =  cls([[x1,y1], [x2, y2], [x3, y3], [x4, y4]])
        return rect

    def __init__(self, points):
        super().__init__(points)

    def plot(self, ax, *args, **kwargs):
        x, y = self.exterior.xy
        ax.plot(x, y, *args, **kwargs)

    def fill(self, ax, *args, **kwargs):
        x, y = self.exterior.xy
        ax.fill(x, y, *args, **kwargs)

    def fillSymbol(self, **kwargs):
        x, y = self.exterior.xy
        symbol = Symbol(mode="Polygon", x=list(x), y=list(y))
        symbol.update(kwargs)
        return symbol


def cal_radius(polygon):
    """ 计算多边形(shapely.geometry.Polygon)的半径(最长)
    """
    dis_lst = []
    centroid =  np.array(polygon.centroid.coords[0])
    for coords in polygon.exterior.coords:
        dis = alg.geo.distance(coords, centroid)
        dis_lst.append(dis)
    return max(dis_lst)

    

def draw_cone(dis, angle, pitchvector):
    """画导引头椎体（近似）

    Args:

    Returns:
        X,Y,Z:三维坐标，可直接用plt.plot_wireframe/plot_surface绘制
    """
    sector = alg.shape.Sector([0, 0], dis, 0, angle)
    xx, zz = sector.exterior.xy
    xx = np.array(xx)
    zz = np.array(zz)
    X, Y, Z = alg.shape.rotate_by_z(xx, zz)
    m, n = X.shape
    N = m * n
    X1 = X.reshape(N, 1)
    Y1 = Y.reshape(N, 1)
    Z1 = Z.reshape(N, 1)
    mat1 = np.c_[X1,Y1,Z1]

    # 先变换俯仰角
    xy = np.linalg.norm(vector[:2])
    theta = np.arctan2(xy, vector[2]) # 与z轴的顺时针夹角，但xy恒为正
    rot = alg.trf.rotmat_rotate_x(theta)
    # 再变换偏航角
    psi = np.arctan2(vector[0], vector[1]) # 与y轴顺时针夹角
    rot = alg.trf.rotmat_rotate_z(psi) @ rot

    mat2 = mat1 @  rot.T

    X2 = mat2[:,0].reshape(m, n)
    Y2 = mat2[:,1].reshape(m, n)
    Z2 = mat2[:,2].reshape(m, n)
    return X2, Y2, Z2


def draw_tetrahedron(dis, horizontal_angle, pitch_angle, vector=None, indicate_az=None, indicate_pitch=None):
    """画导引头四面体（近似）

    Args:
        radius: 导引头作用距离
        horizontal_angle: 探测扇面水平角度半宽(度)
        pitch_angle: 探测扇面俯仰角度半宽(度)

    Returns:
        X,Y,Z:三维坐标，可直接用plt.plot_wireframe/plot_surface绘制
    """
    sector = alg.shape.Sector([0, 0], dis, 90-pitch_angle, 90+pitch_angle)
    xx, zz = sector.exterior.xy
    xx = np.array(xx)
    zz = np.array(zz)
    X, Y, Z = alg.shape.rotate_by_z(xx, zz, begin=-horizontal_angle, end=horizontal_angle)
    m, n = X.shape
    X = np.c_[np.zeros((m, 1)), X, np.zeros((m, 1))]
    Y = np.c_[np.zeros((m, 1)), Y, np.zeros((m, 1))]
    Z = np.c_[np.zeros((m, 1)), Z, np.zeros((m, 1))]
    n += 2
    N = m * n
    X1 = X.reshape(N, 1)
    Y1 = Y.reshape(N, 1)
    Z1 = Z.reshape(N, 1)
    mat1 = np.c_[X1,Y1,Z1]

    if vector is not None:
        xy = np.linalg.norm(vector[:2])
        theta = np.arctan2(xy, vector[2]) # 与z轴的顺时针夹角，但xy恒为正
        psi = np.arctan2(vector[0], vector[1]) # 与y轴顺时针夹角
    else:
        theta = np.deg2rad(90-indicate_pitch)
        psi = np.deg2rad(indicate_az)
    # 预处理，X轴90度逆时针旋转
    rot = alg.trf.rotmat_rotate_x(-np.pi/2)
    # 先变换俯仰角
    rot = alg.trf.rotmat_rotate_x(theta) @ rot
    # 再变换偏航角
    rot = alg.trf.rotmat_rotate_z(psi) @ rot
    mat2 = mat1 @  rot.T
    X2 = mat2[:,0].reshape(m, n)
    Y2 = mat2[:,1].reshape(m, n)
    Z2 = mat2[:,2].reshape(m, n)
    return X2, Y2, Z2


def vertical_rect3d_coords(angle:float, coords, length:float, height:float):
    """ 计算三维空间中垂直矩形的顶点坐标

    可用于烟幕弹作用范围的计算

    Agrs:
        angle:float            方位角(度)
        coords:list or np.ndarray 中心点坐标
        length:float           垂直矩形长度，与方位角方向垂直
        height:float           垂直矩形高度

    Returns:
        new_coords:np.ndarray        垂直矩形四角个坐标,顺序：视线方向延运动方向，左上开始顺时针
    """
    angle = np.deg2rad(angle)
    coords = np.array(coords)
    vector = np.array([-np.cos(angle), np.sin(angle), 0])
    new_coords = []
    new_coords.append(coords + vector*length/2 + np.array([0, 0, 0.5*height]))
    new_coords.append(coords - vector*length/2 + np.array([0, 0, 0.5*height]))
    new_coords.append(coords - vector*length/2 + np.array([0, 0, -0.5*height]))
    new_coords.append(coords + vector*length/2 + np.array([0, 0, -0.5*height]))
    return np.array(new_coords)


def horizontal_rect3d_coords(angle:float, coords, length:float, width:float):
    """ 计算三维空间中平面矩形的顶点坐标

    可用于表示箔条弹的形状或作用范围

    Agrs:
        angle:float               方位角(度)
        coords:list or np.ndarray 中心点坐标
        length:float              水平面长，与方位角方向垂直
        width:float               水平面宽，与方位角方向平行
        
    Returns:
        new_coords:np.ndarray        水平面四角个坐标,顺序：视线方向延运动方向，左前开始顺时针
    """
    angle = np.deg2rad(angle)
    coords = np.array(coords)
    vector = np.array([np.sin(angle), np.cos(angle), 0])
    vector2 = np.array([-np.cos(angle), np.sin(angle), 0])
    new_coords = []
    new_coords.append(coords + vector*width/2 + vector2*length/2)
    new_coords.append(coords + vector*width/2 - vector2*length/2)
    new_coords.append(coords - vector*width/2 - vector2*length/2)
    new_coords.append(coords - vector*width/2 + vector2*length/2)
    return np.array(new_coords)


def  rotate_by_z(x, z, begin=0, end=360):
    """将曲线环绕z轴旋转形成曲面,x,z均为等长的一维数组
    
    Args:
        x,z： x,z坐标，要求y为0，x>0
        begin: 起始角度，与Y轴的顺时针夹角，度
        end: 终止角度，与Y轴的顺时针夹角，度
    """
    assert end > begin
    N = int(end-begin)
    theta = np.linspace(np.deg2rad(begin), np.deg2rad(end), N)
    mat_x = np.sin(theta)
    mat_y = np.cos(theta)
    x = x.reshape(len(x),1)
    mat_x = mat_x.reshape((1, len(mat_x)))
    mat_y = mat_y.reshape((1, len(mat_y)))
    X = x @ mat_x
    Y = x @ mat_y
    Z = z.repeat(N).reshape((len(z), N))
    return X, Y, Z


def in_area(locate, areas):
    """点在闭合区域内判定仿真模块
        在区域内
        locate : array : [x, y, (z)]
        areas : array：[]
    """
    locate =locate[0:2]
    if isinstance(areas, dict):
        areas = [areas]
    # print('areas', areas)
    for area in areas:
        if area['type'] == 'sector':
            """
            sector: 扇形
                r1: int 大半径
                r2: int 小半径
                center: [x, y] 中心位置
                course: int 航向角，正北顺时针[0,360)
                angle: int 角范围
                part：str :[left, right, both]
                可选1： angle=0
                start_angle: int 开始角
                end_angle: int 结束角
            """
            distance = np.array(locate[0:2], dtype=float) - np.array(area["center"][0:2], dtype=float)
            dis = np.linalg.norm(distance)
            if dis > area['r1'] or dis < area['r2']: # r1>r2
                continue
            # print(area, locate)
            if area['angle'] == 0: # end>start
                area['course'] = (area['start_angle'] + area['end_angle']) / 2
                area['angle'] =(area['end_angle'] - area['start_angle']) / 2
            xx, yy = locate[0: 2] - area['center'][0:2]
            # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
            course_angle = area['course'] / 180 * np.pi
            x0 = np.sin(course_angle)
            y0 = np.cos(course_angle)
            cos_theta = (xx * x0 + yy * y0)/(xx**2 + yy**2)**0.5
            if cos_theta < np.cos(area['angle']*np.pi/180):
                continue
            is_left = xx * y0 - yy * x0
            if area['part'] == "left" and is_left < 0:
                continue
            elif area['part'] == 'right' and is_left > 0:
                continue
            else:
                return True

            # locate_angle = np.arctan2(yy, xx)
            # locate_angle = (locate_angle / np.pi * 180 ) % 360
            # locate_angle = 90 - locate_angle
            # rela_angle = locate_angle - area['course']
            # # print('rela_angle' ,rela_angle)
            # if abs(rela_angle) > area['angle']:
            #     continue
            
        elif area['type'] == 'circle':
            """
            circle : 圆形
                r: int 半径
                center: [x, y] 中心
                [r2]: int 内半径

            """
            distance = [area['center'][0] - locate[0], area['center'][1] - locate[1]]
            distance = np.linalg.norm(distance)
            if distance < area['r']:
                if 'r2' in  area.keys():
                    if distance > area['r2']:
                        return True
                    else:
                        continue
                else:
                    return True
            else:
                continue
        elif area['type'] == 'ellipse':
            """
            ellipse : 椭圆形
                points : [[x,y],[x,y]] 两个圆心
                distance ： 距圆心距离和
            """
            try:
                dis1 = np.linalg.norm(area['points'][0] - locate)
                dis2 = np.linalg.norm(area['points'][1] - locate)
            except BaseException:
                pdb.set_trace()
            if dis1 + dis2 < area['distance']:
                return True
        else:
               continue
    return False

