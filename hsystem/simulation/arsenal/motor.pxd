# cython:language_level=3
# distutils: language=c++
from ..core.arch cimport Motor

cdef class RandomMotor(Motor):
    cpdef _move(self)

cdef class DurationMotor(Motor):
    cdef float _duration
    cdef _upper_tick
    cdef _end_tick

    cpdef _set_duration(self, float duration)
    cpdef _clear_duration(self)

cdef class WaypointsMotor(DurationMotor):
    cdef public _waypoints
    cdef public list _speeds
    cdef public list _events
    cdef public int _num_waypoint
    cdef public int _current_waypoint_id
    cdef public int _next_waypoint_id

    cpdef _set_waypoints(self, waypoints, list speeds=*, speed=*, list events=*)
    cpdef _clear_waypoints(self)
    cpdef _move(self)
    cpdef list _draw(self, ax=*, str mode=*)

cdef class ManeuverMotor(WaypointsMotor):
    cdef public _maneuver_cmds
    cdef public _current_maneuver_cmd
    cdef public bint _completed_end_cmd
    cdef public bint _is_frozen

    cpdef _velocity_begin(self, cmd)
    cpdef _speed_begin(self, cmd)
    cpdef _speed_end(self, cmd)
    cpdef _course_begin(self, cmd)
    cpdef _acce_begin(self, cmd)
    cpdef _acce_end(self, cmd)
    cpdef _turn_begin(self, cmd)
    cpdef _waypoints_begin(self, cmd)
    cpdef _waypoints_end(self, cmd)
    cpdef _begin_maneuver_cmd(self)
    cpdef _end_maneuver_cmd(self, bint normal=*)
    cpdef clear_current_cmd(self)
    cpdef clear_cmds(self, bint is_clear_current=*)
    cpdef add_maneuver_cmd(self, cmd)
    cpdef insert_maneuver_cmd(self, cmd, bint rightnow=*)
    cpdef freeze(self)
    cpdef unfreeze(self)
    cpdef _move(self)
    cpdef _oval_begin(self,cmd)
    cpdef _oval_end(self,cmd)
    cpdef _lineCircle_begin(self,cmd)
    cpdef _lineCircle_end(self,cmd)
    cpdef _rectangularCircle_begin(self,cmd)
    cpdef _rectangularCircle_end(self,cmd)

cdef class _PlaneMotor(ManeuverMotor):
    cdef bint _send_rtb

    cpdef get_next_mode(self)
    cpdef _Climb_begin(self, cmd)
    cpdef _Climb_end(self, cmd)
    cpdef _Turn_begin(self, cmd)
    cpdef _FlyOnCourse_begin(self, cmd)
    cpdef _FlyOnCourse_end(self, cmd)
    cpdef _ReturnToBase_begin(self, cmd)
    cpdef _ReturnToBase_end(self, cmd)
    cpdef _Decline_begin(self, cmd)
    cpdef _Advance_begin(self, cmd)
    cpdef _Advance_end(self, cmd)

cdef class FixedWingMotor(_PlaneMotor):
    cpdef _TakeOff_begin(self, cmd)
    cpdef _TakeOff_end(self, cmd)
    cpdef _LandOn_begin(self, cmd)
    cpdef _LandOn_end(self, cmd)
    cpdef _Hover_begin(self, cmd)
    cpdef _Hover_end(self, cmd)

cdef class RotaryWingMotor(_PlaneMotor):
    cpdef _TakeOff_begin(self, cmd)
    cpdef _TakeOff_end(self, cmd)
    cpdef _LandOn_begin(self, cmd)
    cpdef _LandOn_end(self, cmd)
    cpdef _Hover_begin(self, cmd)

cdef class ShipMotor(ManeuverMotor):
    cdef public bint is_back

    # cpdef _Init_motion(self, dll_path)
    cpdef _Advance_begin(self, cmd)
    cpdef _Advance_end(self, cmd)
    cpdef _Back_begin(self, cmd)
    cpdef _Back_end(self, cmd)
    cpdef _Turn_begin(self, cmd)
    cpdef _Turn_end(self, cmd)
    cpdef _SailOnCourse_begin(self, cmd)
    cpdef _SailOnCourse_end(self, cmd)

cdef class SubmarineMotor(ManeuverMotor):
    cpdef _Rise_begin(self, cmd)
    cpdef _Rise_end(self, cmd)
    cpdef _Dive_begin(self, cmd)
    cpdef _Dive_end(self, cmd)
    cpdef _Advance_begin(self, cmd)
    cpdef _Advance_end(self, cmd)
    cpdef _Back_begin(self, cmd)
    cpdef _Back_end(self, cmd)
    cpdef _Turn_begin(self, cmd)
    cpdef _Turn_end(self, cmd)
    cpdef _SailOnCourse_begin(self, cmd)
    cpdef _SailOnCourse_end(self, cmd)