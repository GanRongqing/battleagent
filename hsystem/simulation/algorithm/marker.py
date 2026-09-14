import numpy as np
from simulation.algorithm.shape import Symbol
from matplotlib.path import Path


def rot(verts, az):
    rad = az / 180 * np.pi
    verts = np.array(verts)
    rotMat = np.array([[np.cos(rad), -np.sin(rad)], [np.sin(rad), np.cos(rad)]])
    transVerts = verts.dot(rotMat)
    return transVerts

planeIconMat = np.array([[-0.866, 0.5],
                        [0, 1],
                        [0, 2],
                        [0, 1],
                        [0.866, 0.5],
                        [0, 1],
                        [0, -1],
                        [0.866, -1.5],
                        [0, -1],
                        [-0.866, -1.5],
                        [0, -1],
                        [0, 1]])

shipIconMat = np.array([[-0.5, 0],
                        [0, 0.5],
                        [0.5, 0],
                        [0.5, -1],
                        [-0.5, -1],
                        [-0.5, 0]])

submarineIconMat = np.array([[-0.5, 0.5],
                            [0.5, 0.5],
                            [0.5, -0.5],
                            [0.5, -1],
                            [-0.5, -0.5],
                            [-0.5, 0.5]])

baseIconMat = np.array([[-0.5, 0.5],
                        [0.5, 0.5],
                        [0.5, -0.5],
                        [-0.5, -0.5],
                        [-0.5, 0.5]])


windIconMat = np.array([[0, 0.5],
                        [0, -0.5],
                        [-0.5, -0.5],
                        [0, -0.5],
                        [0, 0],
                        [-0.5, 0],
                        [0, 0],
                        [0, 0.5]])


class IconMarker(Path):
    def __init__(self, icon, az):
        if icon == "Plane":
            verts = planeIconMat.copy()
        elif icon == "Ship":
            verts = shipIconMat.copy()
        elif icon == "Submarine":
            verts = submarineIconMat.copy()
        elif icon == "Base":
            verts = baseIconMat.copy()
        elif icon == "Wind":
             verts = windIconMat.copy()
        vertices = rot(verts, az)
        super().__init__(vertices)

class ShapeMarker(Symbol):
    def __init__(self, **args):
        args.update({'mode': 'Marker'})
        assert 'marker_id' in args, 'marker_id 不能为空'
        super().__init__(**args)

if __name__ == '__main__':
    marker_data = {"name":"test", "group":'RED', "text":"", "icon":"",
                                "lng": 0.1 , "lat": 0.1, "az": 0,
                                'marker_id': 'D'}
    print(ShapeMarker(**marker_data))