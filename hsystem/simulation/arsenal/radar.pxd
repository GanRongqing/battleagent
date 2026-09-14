# cython:language_level=3
# distutils: language=c++
from ..core.arch cimport Sensor

cdef class Radar(Sensor):
    cdef _fake_find_pro
    cdef _A0
    cdef _coef
    cdef dict _dis_formula
    cdef dict _dis_sigma
    cdef _prev_h
    cdef dict _found_target_tracks
    cdef dict _jammers
    cdef set _found_with_log_track
    cdef int _redis_count_id
    cdef list border_color

    cpdef set_sector(self, list sector)
    cpdef bint acquire(self, foe)
    cpdef float _cal_near_dis(self, foe=*, dict foe_params=*)
    cpdef float _cal_far_dis(self, foe=*, dict foe_params=*)
    cpdef float _cal_dis_by_formula(self, foe=*, dict foe_params=*)
    cpdef float _cal_dis_by_coef(self, foe=*, dict foe_params=*)
    cpdef float _cal_jam_dis_by_formula(self, foe=*, dict foe_params=*, float jammed_coef=*)
    cpdef float _cal_pro_by_formula(self, foe)
    cpdef float _cal_jam_dis_fixed(self, az_foe, pitch_foe, foe)
    cpdef _update_interp(self)
    cpdef _update_jammers(self)
    cpdef set _search(self)
    cpdef _detect(self)
    cpdef turn_on(self)
    cpdef turn_off(self)
    cpdef kill(self)
    cpdef _jam_radar_handler(self, event)
    cpdef implement(self)
    cpdef check(self)
    cpdef _render_range_update(self)
    cpdef _render(self)
    cpdef list _draw(self, ax=*, str mode=*)
    cpdef drawXz(self, ax)
    cpdef draw3D(self, ax)
    cpdef list drawSymbol(self)

cdef class GuiderBasedRadar(Radar):
    cdef public dict _guiding
    cdef _pre_guiding
    cdef set _commanders

    cpdef turn_on(self)
    cpdef _render(self)
    cpdef turn_off(self)
    cpdef add_commander(self, commander)
    cpdef pre_load(self, foe)
    cpdef cancel_pre_load(self, foe)
    cpdef load(self, foe, int num)
    cpdef release(self, foe)
    cpdef load_ms(self, foe, ms)
    cpdef set _guide(self)
    cpdef _attack_handler(self, event)
    cpdef _send_guider_info(self)
    cpdef implement(self)
    cpdef check(self)
    cpdef draw(self, ax)

cdef class RadarWithGuider(GuiderBasedRadar):
    cpdef set _search(self)
    cpdef implement(self)
    cpdef check(self)
    cpdef _render(self)