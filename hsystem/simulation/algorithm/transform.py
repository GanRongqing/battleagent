""" 惯性坐标系坐标变换
角度单位均为弧度
"""
import numpy as np
from scipy.optimize import root

from .. import algorithm as alg


def ned2enu(x, y, z):
    return y, x, -z


def enu2ned(x, y, z):
    return y, x, -z


def enu2fire(x, y, z):
    """enu坐标转发射坐标

    假设发射系X轴指向东
    """
    return x, z, -y


def fire2enu(x, y, z):
    """发射坐标转enu坐标

    假设发射系X轴指向东
    """
    return x, -z, y


def euler2quaternion(phi, theta, psi, base="ned"):
    """
    """
    if base == "ned":
        pass
    elif base == "enu":
        phi = -phi
        theta = - theta
        psi = - (np.pi-psi)
        raise RuntimeError("不确定对不对")
    elif base == "fire": #y轴指天
        theta = psi
        psi = -theta
        phi =  phi + np.pi/2.0
        raise RuntimeError("似乎不对")
    e0 = np.cos(psi/2.)*np.cos(theta/2.)*np.cos(phi/2.)+np.sin(psi/2.)*np.sin(theta/2.)*np.sin(phi/2.)
    e1 = np.cos(psi/2.)*np.cos(theta/2.)*np.sin(phi/2.)-np.sin(psi/2.)*np.sin(theta/2.)*np.cos(phi/2.)
    e2 = np.cos(psi/2.)*np.sin(theta/2.)*np.cos(phi/2.)+np.sin(psi/2.)*np.cos(theta/2.)*np.sin(phi/2.)
    e3 = np.sin(psi/2.)*np.cos(theta/2.)*np.cos(phi/2.)-np.cos(psi/2.)*np.sin(theta/2.)*np.sin(phi/2.)
    return e0, e1, e2, e3


def quaternion2euler(e0, e1, e2, e3):
    """ned/enu/发射坐标系下(右手系即可)弹体的四元数变换为欧拉角,单位为弧度
    !!!该公式与三个角的定义紧密相关，只使用于ned坐标系，但不适用enu和发射坐标系
    """
    # e0 = e.item(0)
    # e1 = e.item(1)
    # e2 = e.item(2)
    # e3 = e.item(3)
    phi = np.arctan2(2.*(e0*e1+e2*e3),(e0**2+e3**2-e1**2-e2**2))
    temp = 2.*(e0*e2-e1*e3)
    if temp > 1.0: # 避免一点点的溢出
        theta = np.pi/2.0
    elif temp < -1.0: # 避免一点点的溢出
        theta = -np.pi/2.0
    else:
        theta = np.arcsin(temp)
    psi = np.arctan2(2.*(e0*e3+e1*e2),(e0**2+e1**2-e2**2-e3**2))
    return phi, theta, psi #单位为弧度


def quaternion2rotmat(e0, e1, e2, e3):
    """将四元数转换为旋转矩阵rotmat

    可以通过rotmat@np.array([[x],[y],[z]])进行旋转,即为左乘旋转矩阵，转置则为右乘旋转矩阵
    该旋转为将弹体坐标系中的点坐标变换为惯性坐标系中的点坐标(或者也可以理解为将惯性坐标系中的点按对应的欧拉角所描述的旋转)
    如果将惯性坐标系中的点坐标变换为弹体坐标系中的点坐标，即逆变换，则左乘逆矩阵即可，同时因旋转矩阵为正交阵，逆矩阵时原矩阵的转置
    从四元数的视角，则是由四元数的共轭四元数(e0, -e1, -e2, -e3)生成的旋转矩阵即为拟矩阵
    """
    rotmat = np.array([
            [e1**2+e0**2-e2**2-e3**2, 2*(e1*e2-e3*e0), 2*(e1*e3+e2*e0)],
            [2*(e1*e2+e3*e0), e2**2+e0**2-e1**2-e3**2, 2*(e2*e3-e1*e0)],
            [2*(e1*e3-e2*e0), 2*(e2*e3+e1*e0), e3**2+e0**2-e1**2-e2**2]])
    return rotmat

def rotatexyz_quaternion(mat, e0, e1, e2, e3):
    """通过四元数进行坐标旋转

    该旋转为将弹体坐标系中的点坐标变换为惯性坐标系中的点坐标(或者也可以理解为将惯性坐标系中的点按对应的欧拉角所描述的旋转)
    如果将惯性坐标系中的点坐标变换为弹体坐标系中的点坐标，即逆变换，则将输入的四元数取共轭即(e0, -e1, -e2, -e3)即可
    
    mat: N*3的矩阵,其列分别表示x,y,z
    e0, e1, e2, e3:四元数
    """
    rot = quaternion2rotmat(e0, e1, e2, e3)
    res = mat @ rot.T
    return res


def rotmat_rotate_x(theta):
    """
    将某物体在右手系中的坐标顺时针旋转theta的变换矩阵，变换矩阵左乘该坐标
    或将某物体在右手系中的坐标逆时针旋转theta的变换矩阵，变换矩阵右乘该坐标
    """
    rotmat = np.array([[1, 0, 0],
                    [0, np.cos(theta), np.sin(theta)],
                    [0, -np.sin(theta), np.cos(theta)]])
    return rotmat
    
def rotmat_rotate_y(theta):
    rotmat = np.array([[np.cos(theta), 0, -np.sin(theta)],
                    [0, 1, 0],
                    [np.sin(theta), 0, np.cos(theta)]])
    return rotmat

def rotmat_rotate_z(theta):
    rotmat = np.array([[np.cos(theta), np.sin(theta), 0],
                    [-np.sin(theta), np.cos(theta), 0],
                    [0, 0, 1]])
    return rotmat

def rotmat_xyz2x1y1z1(theta2, psi, gamma):
    return rotmat_rotate_x(gamma)@rotmat_rotate_z(theta2)@rotmat_rotate_y(psi)

def euler2rotmat(theta2, psi, gamma):
    return rotmat_xyz2x1y1z1(theta2, psi, gamma)

def rotmat2euler(rotmat):
    theta2 = np.arctan2(rotmat[0,1], np.sqrt(rotmat[1,1]**2+rotmat[2,1]**2))
    psi = np.arctan2(-rotmat[0,2], rotmat[0,0])
    gamma = np.arctan2(-rotmat[2,1], rotmat[1,1])
    return theta2, psi, gamma

def rotmat_xyztox2y2z2tox3y3z3tox1y1z1(alpha, beta, gamma_v, theta, psi_v):
    return rotmat_rotate_z(alpha)@rotmat_rotate_y(beta)@rotmat_rotate_x(gamma_v)@rotmat_rotate_z(theta)@rotmat_rotate_y(psi_v)

def cal_theta2_psi_gamma(alpha, beta, gamma_v, theta, psi_v):
    rotmat = rotmat_xyztox2y2z2tox3y3z3tox1y1z1(alpha, beta, gamma_v, theta, psi_v)
    theta2, psi, gamma = rotmat2euler(rotmat)
    return theta2, psi, gamma

def rotmat_x2y2z2tox3y3z3tox1y1z1(alpha, beta, gamma_v):
    return rotmat_rotate_z(alpha)@rotmat_rotate_y(beta)@rotmat_rotate_x(gamma_v)

def rotmat2rad_x2y2z2tox3y3z3tox1y1z1(rotmat):
    alpha = np.arctan2(-rotmat[1,0], rotmat[0,0])
    beta = np.arctan2(rotmat[2,0], np.sqrt(rotmat[0,0]**2+rotmat[1,0]**2))
    gamma_v = np.arctan2(-rotmat[2,1], rotmat[2,2])
    return alpha, beta, gamma_v
    
def cal_alpha_beta_gamma_v(theta2, psi, gamma, theta, psi_v):
    rotmat = rotmat_xyz2x1y1z1(theta2, psi, gamma)
    rotmat2 = rotmat_rotate_z(theta)@rotmat_rotate_y(psi_v)
    rotmat1 = rotmat@rotmat2.T # rotmat = rotmat1@rotmat2
    alpha, beta, gamma_v = rotmat2rad_x2y2z2tox3y3z3tox1y1z1(rotmat1)
    return alpha, beta, gamma_v

def cal2_alpha_beta_gamma_v(theta2, psi, gamma, theta, psi_v):
    beta = np.arcsin(np.cos(theta)*(np.cos(gamma)*np.sin(psi-psi_v)+np.sin(theta2)*np.sin(gamma)*np.cos(psi-psi_v)) 
            - np.sin(theta)*np.cos(theta2)*np.sin(gamma)) # (2-55)
    alpha = np.arcsin((np.cos(theta)*(np.sin(theta2)*np.cos(gamma)*np.cos(psi-psi_v)-np.sin(gamma)*np.sin(psi-psi_v))
            - np.sin(theta)*np.cos(theta2)*np.cos(gamma))/np.cos(beta)) # (2-56)
    
    sin_gamma_v = (np.cos(alpha)*np.sin(beta)*np.sin(theta2) - np.sin(alpha)*np.sin(beta)*np.cos(gamma)*np.cos(theta2)
            + np.cos(beta)*np.sin(gamma)*np.cos(theta2))/np.cos(theta)
    if sin_gamma_v > 1.0:
        gamma_v = np.pi/2.0
    elif sin_gamma_v < -1.0:
        gamma_v = -np.pi/2.0
    else:
        gamma_v = np.arcsin(sin_gamma_v) # (2-57)
    return alpha, beta, gamma_v


def formula2_37(alpha, beta, gamma_v, theta, X, Y, Z, P, mass, g=9.8):
    ax = (P*np.cos(alpha)*np.cos(beta) - X - mass*g*np.sin(theta))/mass
    ay = (P*(np.sin(alpha)*np.cos(gamma_v)+np.cos(alpha)*np.sin(beta)*np.sin(gamma_v)) 
                + Y*np.cos(gamma_v) - Z*np.sin(gamma_v) - mass*g*np.cos(theta))/mass
    az = (P*(np.sin(alpha)*np.sin(gamma_v)-np.cos(alpha)*np.sin(beta)*np.cos(gamma_v))
                + Y*np.sin(gamma_v) + Z*np.cos(gamma_v))/mass
    return ax, ay, az


def formula2_37_inverse(ax, ay, az, alpha0, beta0, gamma_v0, theta, X, Y, Z, P0, mass, g=9.8):
    """X,Y,Z不能为0，否则有无穷多个解
    
    同时，因常常求不出解，因此把推力也加上输出,仍然解不出，看来此方法不行
    """    
    a = mass*ax + X + mass*g*np.sin(theta)
    b = mass*ay + mass*g*np.cos(theta)
    c = mass*az

    P = np.linalg.norm(np.array([ax, ay, az]))*mass

    # P*np.cos(alpha)*np.cos(beta) - a == 0
    # P*np.sin(alpha) - b*np.cos(gamma_v) - c*np.sin(gamma_v) + Y == 0
    # P*np.cos(alpha)*np.sin(beta) - b*np.sin(gamma_v) + c*np.cos(gamma_V) - Z == 0

    def fun(x):
        # x = [alpha, beta, gamma_v, P]
        f = [
        P*np.cos(x[0])*np.cos(x[1]) - a,
        P*np.sin(x[0]) - b*np.cos(x[2]) - c*np.sin(x[2]) + Y,
        P*np.cos(x[0])*np.sin(x[1]) - b*np.sin(x[2]) + c*np.cos(x[2]) - Z
        ]
        return f
    def jac(x):
        # x = [alpha, beta, gamma_v, P]
        jac = np.array([
            [-P*np.sin(x[0])*np.cos(x[1]), -P*np.cos(x[0])*np.sin(x[1]), 0],
            [P*np.cos(x[0]), 0, b*np.sin(x[2])-c*np.cos(x[2])],
            [-P*np.sin(x[0])*np.sin(x[1]), P*np.cos(x[0])*np.cos(x[1]), -b*np.cos(x[2])-c*np.sin(x[2])]
        ])
        return jac
    # 计算结果可能不唯一，因此要给一个初始值
    sol = root(fun, [alpha0, beta0, gamma_v0], jac=jac, method='hybr')
    try:
        assert sol.success is True
    except:
        import pdb; pdb.set_trace()
    alpha, beta, gamma_v = sol.x
    return alpha, beta, gamma_v, P

    # _a = c**2/(b**2) + 1
    # _b = 2*(a-Z)*c/(b**2)
    # _c = (a-Z)**2/(b**2) - 1
    # roots = alg.geo.quadratic(_a, _b, _c)
    # print(f"root:{roots}")
    # root = [t for t in roots if -1<=t<=1]
    # gamma_v = np.arccos(root[0])
    # alpha = np.arcsin((b*np.cos(gamma_v)+c*np.sin(gamma_v)-Y)/P)
    # beta = np.arccos(a/P/np.cos(alpha))
    # return alpha, beta, gamma_v





