# -*- coding: utf-8 -*-
import sys
sys.path.insert(0,"/root/autodl-tmp/hsystem")
from agent_hybrid_coverage_bounds import AreaCoverage, AREA_X0, AREA_X1, AREA_Y0, AREA_Y1

def _centers(c):
    return [c._center(ix,iy) for (ix,iy) in c._weight]

def test_grid_inside_area():
    c=AreaCoverage()
    for x,y in _centers(c):
        assert AREA_X0-1e-6<=x<=AREA_X1+1e-6 and AREA_Y0-1e-6<=y<=AREA_Y1+1e-6,(x,y)

def test_no_northern_out_of_area_cells():
    c=AreaCoverage()
    ys=[y for _,y in _centers(c)]
    assert max(ys)<=AREA_Y1, max(ys)   # old grid reached 620km
    assert min(ys)>=AREA_Y0           # old grid had no y<80km

def test_roundtrip_cell_center():
    c=AreaCoverage()
    for x,y in [(50000,0),(200000,150000),(0,-270000),(370000,270000)]:
        ix,iy=c._cell(x,y); cx,cy=c._center(ix,iy)
        assert abs(cx-x)<=30000 and abs(cy-y)<=30000,(x,y,cx,cy)

def test_mark_and_best_unobserved_in_area():
    c=AreaCoverage()
    c.mark_covered(150000,0,0)
    out=c.best_unobserved(1000,k=5)
    assert out, "expected stale cells"
    for (cx,cy),_w in out:
        assert AREA_Y0<=cy<=AREA_Y1 and AREA_X0<=cx<=AREA_X1

def test_episode_isolation_fresh_map():
    a=AreaCoverage(); a.mark_covered(100000,0,0)
    b=AreaCoverage()
    assert b.last_covered=={} and a.last_covered

def test_c17_clamp_inherited():
    from agent_hybrid_coverage_bounds import CoverageBoundsAgentMain
    from agent_hybrid_uav_bounds import BoundedUAVManager
    m=CoverageBoundsAgentMain(use_uavs=True)
    assert isinstance(m.uav_mgr, BoundedUAVManager)
    assert isinstance(m.coverage, AreaCoverage)

def _all():
    fns=[v for k,v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    p=0
    for f in fns:
        try: f(); p+=1
        except Exception as e: print("FAIL",f.__name__,repr(e))
    print(f"passed={p}/{len(fns)}"); return p==len(fns)
if __name__=="__main__": sys.exit(0 if _all() else 1)
