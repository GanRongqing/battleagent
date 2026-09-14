# cython:language_level=3
# distutils: language=c++
from simulation.core.entity cimport Entity, FSM, Router
from simulation.core.base cimport Node, Bag
from simulation.core.message cimport Cmd, Msg, Task, Event, MsgTrack, HEAD, MESSAGE

cdef class Attribute(Node):
    cdef public db

    cpdef bint has_attr(self, str attr)

cdef class Unit(Router):
    cdef Bag _components
    cdef dict _name_comps
    cdef  _model_comps
    cdef bint _is_assembled
    cdef bint _is_implemented
    cdef bint _is_checked

    cpdef employ(self, component)
    cpdef component(self, id)
    cpdef comp_by_name(self, str name)
    cpdef comps_by_model(self, str name)
    cpdef list components(self, fun=*)
    cpdef message_handle(self, MESSAGE message)
    cpdef _send_event(self, dst, content, delay=*)
    cpdef _add_handler(self, name, handler)
    cpdef assemble(self)
    cpdef implement(self)
    cpdef check(self)
    cpdef start(self)
    cpdef kill(self)
    cpdef draw(self,ax)
    cpdef drawXz(self, ax)
    cpdef list drawSymbol(self)
    cpdef list drawSymbol3D(self)

cdef class Platform(Unit):
    cdef public Attribute attr
    cdef public str name
    cdef public str model
    cdef public group
    cdef public ptype
    cdef public country
    cdef public bint isdetectable
    cdef public home_unit
    cdef public bint is_at_home
    cdef public Bag _children
    cdef public Bag _munitions
    cdef public symbol_id

    cpdef _gen_components(self, home_unit=*)
    cpdef _gen_component(self, comp_model, home_unit=*)
    cpdef add_child(self, child, bint detectable=*)
    cpdef remove_child(self, child)
    cpdef add_munition(self, munition, bint detectable=*)
    cpdef set_move_param(self, coords, velocity, coordinate_system=*)
    cpdef _hit_handler(self, event)
    cpdef set_damage_threshold(self, damage)
    cpdef kill(self)
    cpdef implement(self)
    cpdef draw(self, ax)
    cpdef draw3D(self, ax)
    cpdef drawXz(self, ax)
    cpdef list drawSymbol(self)
    cpdef list drawSymbol3D(self)

cdef class Characteristics(Entity):
    cdef public unit
    cdef public engine
    cdef public db
    cdef public str model

cdef class Vitalities(Entity):
    cdef public unit
    cdef public engine
    cdef public Attribute threshold
    cdef public str model
    cdef public Attribute current

cdef class Network(FSM):
    cdef public Attribute attr
    cdef public str model
    cdef public set _comdevs
    cdef public dict _comdevs_linked
    cdef public str name
    cdef public dict _comdevs_send_time

    cpdef add_comdev(self, comdev)
    cpdef bint check_isin_net(self, comdev1, comdev2)
    cpdef check_connect(self, comdev1, comdev2)
    cpdef _check_linked(self)
    cpdef check(self)

cdef class Component(FSM):
    cdef public unit
    cdef public Attribute attr
    cdef public str model
    cdef public str name
    cdef public _controller
    cdef public float _paz
    cdef public float _pd
    cdef public float _ph
    cdef public _sector
    cdef public dict _redis_links

    cpdef set_pxyz(self, float px=*, float py=*, float pz=*)
    cpdef set_pdah(self, float pd=*, float paz=*, float ph=*)
    cpdef set_sector(self, list sector)
    cpdef kill(self)
    cpdef message_handle(self, MESSAGE message)
    cpdef __send_message_body(self, dst, body)
    cpdef _send_msg(self, dst, content, bint isignored=*)
    cpdef _send_cmd(self, dst, content, bint isignored=*)
    cpdef _send_event(self, dst, content, delay=*)
    cpdef _add_handler(self, name, handler)
    cpdef list _draw(self, ax=*, str mode=*)
    cpdef draw(self, ax)
    cpdef list drawSymbol(self)

cdef class Motor(Component):
    cdef public float distance
    cdef public _coords
    cdef public _velocity
    cdef public _acce
    cdef public _prev_coords
    cdef public float _prev_course
    cdef public float _last_course
    cdef public _history_points
    cdef public _ref_unit
    cdef public _redis_push_time
    cdef public _lnglath
    cdef public _ecef_coords
    cdef public _ecef_velocity

    cpdef set_pxyz(self, float px=*, float py=*, float pz=*)
    cpdef set_pdah(self, float pd=*, float paz=*, float ph=*)
    cpdef set_sector(self, list sector)
    cpdef set_motivate_param(self, coords, velocity=*)
    cpdef set_ref_unit(self, unit)
    cpdef _move(self)
    cpdef _move_ecef(self)
    cpdef _change_speed(self, Cmd cmd)
    cpdef _change_course(self, Cmd cmd)
    cpdef _change_height(self, Cmd cmd)
    cpdef _change_velocity(self, Cmd cmd)
    cpdef change_speed(self, float speed, bint ignore=*)
    cpdef change_course(self, float az, bint ignore=*)
    cpdef change_height(self, float height, bint ignore=*)
    cpdef change_velocity(self, v, bint ignore=*)
    cpdef change_acce(self, acce, bint ignore=*)
    cpdef check(self)
    cpdef kill(self)
    cpdef draw(self, ax)
    cpdef draw3D(self, ax)
    cpdef drawXz(self, ax)
    cpdef list drawSymbol(self)

cdef class Comdev(Component):
    cdef public set _networks
    cdef public list __msgs

    cpdef add_network(self, network)
    cpdef remove_network(self, network)
    cpdef _check_connect(self, comdev)
    cpdef message_handle(self, MESSAGE message)
    cpdef _work(self)
    cpdef check(self)
    cpdef kill(self)

cdef class Driver(Component):
    cdef public str _role
    cdef public _leader
    cdef public set _subordinates
    cdef public set _companions

    cpdef set_leader(self, driver)
    cpdef _add_subordinate(self, driver)
    cpdef _remove_subordinate(self, driver)
    cpdef _update_subordinates_companions(self)
    cpdef _work(self)

cdef class Commander(Component):
    cdef public _superior_commander
    cdef public set _junior_commanders
    cdef public _intel

    cpdef add_junior_commander(self, commander)
    cpdef _send_task(self, dst, content, bint isignored=*)
    cpdef _add_handler(self, name, handler)
    cpdef _command(self)
    cpdef assemble(self)
    cpdef check(self)

cdef class Sensor(Component):
    cdef public set _processors
    cdef public bint _is_on

    cpdef add_processor(self, processor)
    cpdef add_consumer(self, consumer)
    cpdef remove_intel(self, intel)
    cpdef turn_on(self)
    cpdef turn_off(self)
    cpdef _send_track(self, track)
    cpdef _turn_on(self, cmd)
    cpdef _turn_off(self, cmd)
    cpdef _detect(self)
    cpdef _send_track(self, track)
    cpdef assemble(self)
    cpdef implement(self)
    cpdef check(self)

cdef class Munition(Platform):
    cdef public bint is_killed_with_home
    cdef public str _str_name
    cdef public foe
    cdef public strike_chain

    cpdef emit(self)
    cpdef draw(self, ax)
    cpdef draw3D(self, ax)

cdef class Lethality(Component):
    cpdef is_lethal(self, foe)

cdef class ChildPlatform(Platform):
    cdef public bint is_killed_with_home
    cdef public str _str_name

    cpdef release(self)
    cpdef draw(self, ax)
    cpdef draw3D(self, ax)

cdef class DependentPlatform(ChildPlatform):

    cpdef release(self)

cdef class FixedPlatform(Platform):
    cpdef check(self)
    cpdef draw(self, ax)
    cpdef drawXz(self, ax)
    cpdef draw3D(self, ax)
