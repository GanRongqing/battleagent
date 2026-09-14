import warnings
warnings.filterwarnings("error", category=RuntimeWarning)

import numpy as np 
import numpy.linalg as nl
import scipy as sp
from numba import jit

from .. import algorithm as alg


@jit(nopython=True)
def detect_near_bound(h, Ha, low_angle, up_angle, Rs):
    """
    """
    up_rad = np.deg2rad(up_angle)
    low_rad = np.deg2rad(low_angle)
    if h >= Ha:
        dd = np.sqrt((Rs+h)**2-((Rs+Ha)*np.cos(up_rad))**2) - (Rs+Ha)*np.sin(up_rad)         
    else: 
        dd = -np.sqrt((Rs+h)**2-((Rs+Ha)*np.cos(low_rad))**2) + (Rs+Ha)*np.sin(-low_rad)
    if h > dd:
        pp = 0
    else:
        pp = np.sqrt(dd**2-h**2)
    return dd, pp


@jit(nopython=True)
def detect_far_bound(h, Ha, low_angle, max_dis, Rs):
    """
    """
    low_rad = np.deg2rad(low_angle)
    if h < 0 : h = 0
    d1 = np.sqrt(2*Rs) * (np.sqrt(Ha) + np.sqrt(h))
    d2 = np.sqrt((Rs+h)**2-((Rs+Ha)*np.cos(low_rad))**2) + (Rs+Ha)*np.sin(-low_rad)
    dd = min(d1, d2, max_dis)
    if h > dd:
        pp = 0
    else:
        pp = np.sqrt(dd**2-h**2)
    return dd, pp


# @jit(nopython=True) # 使用加速导致用 C 运算可能导致上溢出
def detect_A0(d, fake_find_pro, find_pro, rcs):
    A0 = d**4 * (np.log(fake_find_pro) / np.log(find_pro) - 1) / rcs
    return A0


# @jit(nopython=True)
def detect_prob(d, fake_find_pro, A0, rcs):
    prob = fake_find_pro**(1 / (1 + A0 * rcs / (d**4)))
    return prob


# @jit(nopython=True)
def detect_d_by_prob(prob, fake_find_pro, A0, rcs):
    d = (A0*rcs/(np.log(fake_find_pro)/np.log(prob)-1))**0.25
    return d


def detect_coef(d0, rcs0):
    """
    """
    coef = d0 * rcs0**(-0.25)
    return coef

@jit(nopython=True)
def detect_d_by_coef(coef, rcs):
    """
    """
    d = coef * rcs**(0.25)
    return d


@jit(nopython=True)
def detect_dis(h, Ha, coef):
    """
    """
    radius = 4.12 * coef * (np.sqrt(Ha) + np.sqrt(h)) * 1000
    return radius
 

def coords_add_error(coords, disDelta, azDelta, coords0):
    dis = alg.geo.distance(coords[:2], coords0[:2])
    az = alg.geo.azimuth(coords0[:2], coords[:2])
    newDis = dis + disDelta
    newAz = az + azDelta
    xy = alg.geo.reckon(coords0[:2], newDis, newAz)
    newCoords = coords.copy()
    newCoords[0] = xy[0]
    newCoords[1] = xy[1]
    return newCoords


def velocity_add_error(velocity, speedDelta, courseDelta):
    sp = np.linalg.norm(velocity[:2])
    course = alg.geo.azimuth([0, 0], velocity[:2])
    newSp = sp + speedDelta
    newCourse = course + courseDelta
    vxy = alg.geo.reckon([0, 0], newSp, newCourse)
    newV = velocity.copy()
    newV[0] = vxy[0]
    newV[1] = vxy[1]
    return newV


def merge(targets_loc:list, targets_rcs:list, missile_loc:list, ang_resol:float, dis_resol:float, lamda:float):
    """
    """
    num = len(targets_loc)
    map_dic2 = {}
    map_dic = {}
    old = [i for i in range(num)]
    for i in range(num):
        map_dic2[i]= [i]
    targets_loc = np.array(targets_loc)
    missile_loc = np.array(missile_loc)
    dis_tar_loc = list(map(nl.norm,missile_loc - targets_loc))

    angles = np.ones((num,num))*np.inf
    distances = np.ones((num,num))*np.inf
    total = np.ones((num,num))*np.inf
    for i in range(num):
        for j in range(i):
            cos_theta = np.inner(targets_loc[i]-missile_loc,targets_loc[j]-missile_loc)/(dis_tar_loc[i]*dis_tar_loc[j])
            if cos_theta >=1 :
                angles[i][j] = 0
            elif cos_theta <= -1:
                angles[i][j] = 180
            else:
                angles[i][j] = 180*np.arccos(cos_theta)/np.pi
            # angles[i][j] = 180*np.arccos(np.inner(targets_loc[i]-missile_loc,targets_loc[j]-missile_loc)/(dis_tar_loc[i]*dis_tar_loc[j]))/np.pi
            distances[i][j] = abs(dis_tar_loc[i]-dis_tar_loc[j])
            if angles[i][j] <= ang_resol and  distances[i][j] <= dis_resol:
                total[i][j] = lamda*angles[i][j]+(1-lamda)*distances[i][j] 
            else :
                total[i][j] = np.inf

    while total.min() != np.inf:
        x,y =  np.unravel_index(total.argmin(),total.shape)
        total[y] = np.inf
        total[:,y] = np.inf
        angles[y] = np.inf
        angles[:,y] = np.inf
        distances[y] = np.inf
        distances[:,y] = np.inf 
        targets_loc[x] += (targets_loc[y]-targets_loc[x])*(1-targets_rcs[x]/(targets_rcs[x]+targets_rcs[y]))
        dis_tar_loc[x] = nl.norm(missile_loc - targets_loc[x])
        targets_rcs[x] += targets_rcs[y]
        map_dic2[x] += map_dic2[y]
        map_dic2.pop(y)
        old.remove(y)

        for j in old:
            cos_theta = np.inner(targets_loc[x]-missile_loc,targets_loc[j]-missile_loc)/(dis_tar_loc[x]*dis_tar_loc[y])
            if j == x:
                continue
            if j - x < 0:
                if cos_theta >=1 :
                    angles[j][x] = 0
                elif cos_theta <= -1:
                    angles[j][x] = 180
                else:
                    angles[j][x] = 180*np.arccos(cos_theta)/np.pi
                distances[j][x] = abs(dis_tar_loc[x]-dis_tar_loc[j])
                if angles[j][x]< ang_resol and distances[j][x] < dis_resol:
                    total[j][x] = lamda*angles[j][x]+(1-lamda)*distances[j][x]
                else:
                    total[j][x] = np.inf
            else:
                if cos_theta >=1 :
                    angles[x][j] = 0
                elif cos_theta <= -1:
                    angles[x][j] = 180
                else:
                    angles[x][j] = 180*np.arccos(cos_theta)/np.pi
                distances[x][j] = abs(dis_tar_loc[x]-dis_tar_loc[j])
                if angles[x][j] < ang_resol and distances[x][j] < dis_resol:
                    total[x][j] = lamda*angles[x][j]+(1-lamda)*distances[x][j]
                else:
                    total[x][j] = np.inf

    new_targets_loc = []
    new_targets_rcs = []
    for p in old:
        new_targets_loc.append(targets_loc[p])
        new_targets_rcs.append(targets_rcs[p])
    #构造字典
    map_list = list(map_dic2.keys())
    map_dic = {}
    for i in range(len(map_list)):
        map_dic[i] = map_dic2[map_list[i]]
    return new_targets_loc, new_targets_rcs, map_dic


def seeker_indicate_az(t_coords, m_coords, m_velocity, track_horizontal_angle, search_horizontal_angle):
    """
    """
    assert track_horizontal_angle <= search_horizontal_angle < 180
    is_in = True
    course = alg.geo.azimuth(np.array([0, 0, 0]), m_velocity) # 弹体方位角
    search_left = course-search_horizontal_angle
    search_right = course+search_horizontal_angle

    indicate_az = alg.geo.azimuth(m_coords, t_coords)
    if alg.geo.in_angle_range2(indicate_az, np.array([search_left, search_right])):
        left = indicate_az-track_horizontal_angle
        right = indicate_az+track_horizontal_angle
        if not alg.geo.in_angle_range2(left, np.array([search_left, search_right])):
            left = search_left
        if not alg.geo.in_angle_range2(right, np.array([search_left, search_right])):
            right = search_right        
    else:
        is_in = False
        ang1 =  alg.geo.angle_diff2(indicate_az, search_right)
        ang2 =  alg.geo.angle_diff2(search_left, indicate_az)
        if ang1 < ang2:
            indicate_az = search_right
            right = search_right
            left = search_right-track_horizontal_angle
        else:
            indicate_az = search_left
            left = search_left
            right = search_left+track_horizontal_angle
    return indicate_az, left, right, is_in


def seeker_indicate_pitch(t_coords, m_coords, m_velocity, track_pitch_angle, search_pitch_angle):
    """
    """
    assert track_pitch_angle <= search_pitch_angle < 90
    is_in = True
    elevation = alg.geo.pitch(np.array([0, 0, 0]), m_velocity) # 弹体俯仰角
    search_low = elevation - search_pitch_angle
    search_up = elevation + search_pitch_angle

    indicate_pitch = alg.geo.pitch(m_coords, t_coords)
    if alg.geo.in_angle_range(indicate_pitch, [search_low, search_up]):
        low = indicate_pitch-track_pitch_angle
        up = indicate_pitch+track_pitch_angle
        if not alg.geo.in_angle_range(low, [search_low, search_up]):
            low = search_low
        if not alg.geo.in_angle_range(up, [search_low, search_up]):
            up = search_up
    else:
        is_in = False
        ang1 =  alg.geo.angle_diff2(indicate_pitch, search_up)
        ang2 =  alg.geo.angle_diff2(search_low, indicate_pitch)
        if ang1 < ang2:
            indicate_pitch = search_up
            up = search_up
            low = search_up - track_pitch_angle
        else:
            indicate_pitch = search_low
            low = search_low
            up = search_low + track_pitch_angle
    return indicate_pitch, low, up, is_in


def ship_line(seeker_coords, ship_coords, ship_course, ship_length, ship_width):
    """ 计算视场线
    """
    slope = np.sqrt(ship_width**2+ship_length**2)
    ang = np.rad2deg(np.arctan(ship_width/ship_length))
    az = alg.geo.azimuth(ship_coords, seeker_coords)
    ang_x = alg.geo.angle_diff2(az, ship_course)
    if 0 < ang_x < 90:
        theta = ang_x+ang
    elif 90 < ang_x < 180:
        theta = ang_x-ang
    elif 180 < ang_x < 270:
        theta = ang_x-180+ang
    else:
        theta = ang_x-180-ang
    x = 0.5*slope*np.sin(np.deg2rad(theta))
    x1, y1 = alg.rotation.rotate_theta(x, 0, az)
    x2, y2 = alg.rotation.rotate_theta(-x, 0, az)
    x1 += ship_coords[0]
    x2 += ship_coords[0]
    y1 += ship_coords[1]
    y2 += ship_coords[1]
    return x1, y1, x2, y2


def blind_segment(seeker, seeker_left, seeker_right, left_point, right_point, x1, y1, x2, y2):
    """
    """
    az_left = alg.geo.azimuth(seeker[:2], left_point)
    az_right = alg.geo.azimuth(seeker[:2], right_point)
    sign_left = alg.geo.in_angle_range2(az_left, np.array([seeker_left, seeker_right]))
    sign_right = alg.geo.in_angle_range2(az_right, np.array([seeker_left, seeker_right]))
    sign_seeker_left = alg.geo.in_angle_range2(seeker_left, np.array([az_left, az_right]))
    sign_seeker_right = alg.geo.in_angle_range2(seeker_right, np.array([az_left, az_right]))
    if not (sign_left or sign_right or sign_seeker_left or sign_seeker_right):
        return None
    dis = 1000 # 任意的正数即可
    if sign_seeker_left:
        left_point = alg.geo.reckon(seeker[:2], dis, seeker_left)
    if sign_seeker_right:
        right_point = alg.geo.reckon(seeker[:2], dis, seeker_right)
    # 计算左边和右边水平交点
    is_cross_left, cross_left, t1_left, t2_left = alg.geo.line_cross_line(*seeker[:2], *left_point,
                                                                            x1, y1, x2, y2)
    is_cross_right, cross_right, t1_right, t2_right = alg.geo.line_cross_line(*seeker[:2], *right_point,
                                                                            x1, y1, x2, y2)
    if cross_left is None or cross_right is None:
        return None
    if t1_left < 0 or t1_right < 0:
        return None
    if t2_right < 0 or t2_left > 1:
        return None
    assert t2_left <= t2_right
    t2_left = max(0, t2_left)
    t2_right = min(1, t2_right)
    cross_left[0] = x1 + (x2-x1)*t2_left
    cross_left[1] = y1 + (y2-y1)*t2_left
    cross_right[0] = x1 + (x2-x1)*t2_right
    cross_right[1] = y1 + (y2-y1)*t2_right
    return t2_left, t2_right, cross_left, cross_right



@jit(nopython=True)
def cal_blind_angle(H: float, h: float, d: float):
    """
    """
    if d == 0:
        return np.pi / 2
    R = 6371 * 1000 * 4 / 3
    theta = np.arctan((h - H) / d) - d / 2 / R
    return theta


def detect_blind_angle(radar: np.array, antenna_height: float, target: np.array, finterp: sp.interpolate.interp2d,
                       num: int = 30):
    """
    """
    radar[2] += antenna_height
    d = alg.geo.distance(target[:2], radar[:2])
    terrain = np.linspace(radar + 10, target, num=num)
    t_angle = cal_blind_angle(radar[2], target[2], d)
    for i in range(num):
        terrain[i, 2] = finterp(terrain[i, 0], terrain[i, 1])
        R1 = alg.geo.distance(terrain[i][:2], radar[:2])
        z_angle = cal_blind_angle(radar[2], terrain[i, 2], R1)
        if z_angle > t_angle:
            return False
    return True


@jit(nopython=True)
def _terrain_detect_angle(radar: np.array, target: np.array, terrain: np.array, num: int):
    """
    """
    d = alg.geo.distance(target[:2], radar[:2])
    t_angle = cal_blind_angle(radar[2], target[2], d)
    for i in range(num):
        R1 = alg.geo.distance(terrain[i][:2], radar[:2])
        z_angle = cal_blind_angle(radar[2], terrain[i, 2], R1)
        if z_angle > t_angle:
            return False, terrain[i]
    return True, None


@jit(nopython=True)
def cal_max_dis(Hs: float, Ht: float, H0: float, R1: float):
    """
    """
    if R1 == 0:
        return 999999
    Re = 6371 * 1000 * 4 / 3
    d1 = R1 / 2 - (H0 - Hs) * Re / R1
    if (R1 ** 2 - 2 * (H0 - Hs) * Re) ** 2 + 8 * (Ht - Hs) * (R1 ** 2) * Re < 0:
        return 0
    d2 = ((R1 ** 2 - 2 * (H0 - Hs) * Re) ** 2 + 8 * (Ht - Hs) * (R1 ** 2) * Re) ** 0.5 / 2 / R1
    return d1 + d2


@jit(nopython=True)
def _terrain_detect_distance(radar: np.array, target: np.array, terrain: np.array, num: int):
    """
    """
    d = alg.geo.distance(radar[:2], target[:2])
    for i in range(num):
        R1 = alg.geo.distance(terrain[i][:2], radar[:2])
        Rt = cal_max_dis(radar[2], target[2], terrain[i, 2], R1)
        if d > Rt:
            return False, terrain[i]
    return True, None


def detect_max_distance(radar: np.array, antenna_height: float, target: np.array, finterp,
                        num: int = 30):
    """
    """
    radar[2] += antenna_height
    terrain = np.linspace(radar + 10, target, num=num)
    d = alg.geo.distance(target[:2], radar[:2])
    for i in range(num):
        terrain[i, 2] = finterp(terrain[i, 0], terrain[i, 1])
        R1 = alg.geo.distance(terrain[i][:2], radar[:2])
        Rt = cal_max_dis(radar[2], target[2], terrain[i][2], R1)
        # import pdb;pdb.set_trace()
        if d > Rt:
            return False
    return True


def _get_visual_point(radar, origin, terrain, num_r):
    points = np.linspace(origin, radar, num_r, endpoint=False)
    points[:, 2] = origin[2]
    if num_r == 0 or num_r == 1:
        return origin
    for p in range(0, len(points) - 1):
        is_visual, _ = _terrain_detect_distance(radar, points[p], terrain, num_r)
        if is_visual:
            return points[p]
    return points[-1]


def _get_visual_line(radar, direction_unit_vec, terrain, h_list, r_list, dis_interval):
    visual_line = []
    h_num = len(h_list)
    for h in range(h_num):
        num = int(r_list[h] / dis_interval)
        target_new = r_list[h] * direction_unit_vec + np.array([radar[0], radar[1], 0])
        target_new[2] = h_list[h]
        is_visual, point = _terrain_detect_distance(radar, target_new, terrain, num)
        if is_visual:
            visual_line.append(target_new)
        else:
            length = np.linalg.norm(np.array([radar[0], radar[1], 0]) - np.array([point[0], point[1], 0]))
            num_r = int(length / dis_interval)
            point[2] = h_list[h]
            visual_line.append(_get_visual_point(radar, point, terrain, num_r))
    return visual_line


def cal_visual_circle(radar: np.array, finterp: sp.interpolate.interp2d, antenna_height: float = 0,
                      dis_interval: float = 100, height_interval: float = 100, angle_num: int = 180,
                      max_dis: float = 20 * 1000, max_height: float = 1000):
    """
    """
    assert max_dis >= max_height, "最大探测高度超过最大探测距离"
    assert max_dis >= 0 and max_height >= 0, "最大探测高度或最大探测距离不能为负数或0"
    radar[2] += antenna_height
    h_list = np.linspace(0, max_height, int(max_height / height_interval) + 1)  # 可以改成参数
    visual_coords = []
    directions = np.linspace(0, 2 * np.pi, angle_num, endpoint=True)  # 可以改成参数
    targets = np.zeros((angle_num, 3))
    targets[:, 0] = np.cos(directions)
    targets[:, 1] = np.sin(directions)
    target_h = h_list - radar[2]
    r_list = np.cos(np.arcsin(target_h / max_dis)) * max_dis
    for n in range(angle_num):
        terrain = np.linspace(radar + targets[n] * dis_interval,
                              radar + targets[n] * dis_interval * int(max_dis / dis_interval),
                              int(max_dis / dis_interval))
        terrain[:, 2] = np.array(list(map(finterp, terrain[:, 0], terrain[:, 1])))[:, 0]
        visual_coords.append(_get_visual_line(radar, targets[n], terrain, h_list, r_list, dis_interval))
    return np.array(visual_coords)


def cal_height_circle(radar: np.array, height: float, finterp: sp.interpolate.interp2d, antenna_height: float = 0,
                      angle_num: int = 180, dis_interval: float = 100, max_dis: float = 20 * 1000):
    """
   """

    assert max_dis >= height, "探测高度超过最大探测距离"
    assert max_dis >= 0 and height >= 0, "探测高度或最大探测距离不能为负数或0"
    radar[2] += antenna_height
    h_list = [height]  # 可以改成参数
    visual_coords = []
    directions = np.linspace(0, 2 * np.pi, angle_num, endpoint=True)  # 可以改成参数
    targets = np.zeros((angle_num, 3))
    targets[:, 0] = np.cos(directions)
    targets[:, 1] = np.sin(directions)
    target_h = h_list - radar[2]
    r_list = np.cos(np.arcsin(target_h / max_dis)) * max_dis
    for n in range(angle_num):
        terrain = np.linspace(radar + targets[n] * dis_interval,
                              radar + targets[n] * dis_interval * int(max_dis / dis_interval),
                              int(max_dis / dis_interval))
        terrain[:, 2] = np.array(list(map(finterp, terrain[:, 0], terrain[:, 1])))[:, 0]
        visual_coords.append(_get_visual_line(radar, targets[n], terrain, h_list, r_list, dis_interval))
    return np.array(visual_coords)


def cal_height_point(radar: np.array, height: float, angle: float, finterp: sp.interpolate.interp2d,
                     antenna_height: float = 0, dis_interval: float = 100, max_dis: float = 20 * 1000):
    """
    """
    assert max_dis >= height, "探测高度超过最大探测距离"
    assert max_dis >= 0 and height >= 0, "探测高度或最大探测距离不能为负数或0"
    radar[2] += antenna_height
    h_list = np.array([height])  # 可以改成参数
    direction = np.deg2rad(angle)
    targets = np.zeros(3)
    targets[0] = np.cos(direction)
    targets[1] = np.sin(direction)
    target_h = h_list - radar[2]
    r_list = np.cos(np.arcsin(target_h / max_dis)) * max_dis
    terrain = np.linspace(radar + targets * dis_interval, radar + targets * dis_interval * int(max_dis / dis_interval),
                          int(max_dis / dis_interval))
    terrain[:, 2] = np.array(list(map(finterp, terrain[:, 0], terrain[:, 1])))[:, 0]
    point = _get_visual_line(radar, targets, terrain, h_list, r_list, dis_interval)[0]
    return point


def ellipse_radius(a, c, theta):
    """
    """
    if a <= c:
        return np.zeros_like(theta)
    x = (a**2-c**2)/(a-c*np.cos(np.deg2rad(theta)))
    return x

def multi_sonar_envelope(active, passives, a, az):
    """
    """
    out = []
    for passive in passives:
        c = 0.5 * alg.geo.distance(active, passive)
        _az = alg.geo.azimuth(active, passive)
        theta = (az - _az) % 360
        res =ellipse_radius(a, c, theta)
        out.append(res)
    return np.max(np.array(out), axis=0)