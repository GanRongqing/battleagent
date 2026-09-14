# cython:language_level=3
# distutils: language=c++
from simulation.core.base cimport Node
from simulation.core.message cimport MESSAGE

cdef class Entity(Node):
    cdef bint _isactive
    cdef dict __dict__

    cpdef assemble(self)
    cpdef implement(self)
    cpdef check(self)
    cpdef start(self)
    cpdef kill(self)
    cpdef activate(self)
    cpdef draw(self, ax)
    cpdef drawXz(self, ax)
    cpdef draw3D(self, ax)
    cpdef list drawSymbol(self)
    cpdef list drawSymbol3D(self)

cdef class Router(Entity):
    cdef public engine
    cdef dict _message_handlers

    cpdef message_handle(self, MESSAGE message)
    cpdef _add_handler(self, mcls, handler)
    cpdef _notify(self, recv, body, delay=*, delay_ms=*)
    cpdef _next(self, func, args=*, delay=*, delay_ms=*)

cdef class FSM(Router):
    cdef str _state
    cdef list _history_state
    cdef float _begin_time
    cdef int _state_update_count
    cdef dict _state_action 
    cdef _trans

    cpdef state_update(self)
    cpdef _change_state(self, str new_state)
    cpdef _dispatch(self, double when)
    cpdef _add_transfer(self, str state, str new_state, condition)
    cpdef implement(self)
    cpdef start(self)