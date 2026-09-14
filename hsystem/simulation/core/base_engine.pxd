# cython:language_level=3
# distutils: language=c++
from simulation.core.base cimport Heap, Bag
from simulation.core.entity cimport Router
from simulation.core.message cimport MESSAGE

cdef class DispatchEngine(Router):
    cdef public str name
    cdef public db
    cdef public _raise_error_flag
    cdef public bint _is_activated
    cdef public double _epoch
    cdef public double _tick
    cdef public Heap _cron
    cdef public _tracer
    cdef public double _begin_real_tick
    cdef public double _begin_sim_tick
    cdef public double _upper_tick
    cdef public double _ratio_assess_real_tick
    cdef public double _ratio_assess_sim_tick
    cdef public double _ratio_assess
    cdef public bint _is_pause
    cdef public bint _is_terminated
    cdef public bint _is_probe
    cdef public _ratio
    cdef public double _step_end_tick
    cdef public double _end_tick
    cdef public _starter
    cdef public _terminater
    cdef public list _manipulator
    cdef public dict cache
    cdef public list _threads

    cpdef set_start_epoch(self, str start_epoch)
    cpdef set_ratio(self, ratio)
    cpdef set_ratio_inf(self)
    cpdef set_end_time(self, float time)
    cpdef pause_continue(self)
    cpdef set_probe(self)
    cpdef set_starter(self, starter)
    cpdef set_terminater(self, terminater)
    cpdef add_threading(self, thread, args=*, bint deamon=*)
    cpdef activate(self)
    cpdef terminate(self)
    cpdef update(self, int delta=*)
    cpdef activate_board(self, bint console=*, bint log=*)

cdef class BaseEngine(DispatchEngine):
    cdef public str dir_path
    cdef public str root_path
    cdef public dict sim_config
    cdef public dict render_config
    cdef public dict symbol_dict
    cdef public dict checkbox_dict
    cdef public bint _is_started
    cdef public bint _updating
    cdef public env
    cdef public _proj
    cdef public list env_effects
    cdef public Bag _units
    cdef public dict _name_units
    cdef public list _networks
    cdef public ids
    cdef public lock
    cdef public redis_conn
    cdef public bint is_redis_used
    cdef public bint is_redis_log
    cdef public set _redis_created_ids
    cdef public set _redis_destroyed_ids
    cdef public dict first_found_time_dict
    cdef public strikechain_list
    cdef public set strikechain_id_set
    cdef public post_web_statistic_single_data
    cdef public web_client
    cdef public str user_name
    cdef public str logpath
    cdef public bint web_show
    cdef public dict push_data
    cdef public terminate_result
    cdef public list shape_marker_data
    cdef public simserver
    cdef public bint use_web
    cdef public str web_ip
    cdef public new_thread
    cdef public int sequence_number
    cdef public int entity_code
    cdef public dict entity_name_to_code_dict
    cdef public udp_socket
    cdef public dict render_data
    cdef public int render_index
    cdef public cmd_collections

    cpdef _register_class(self)
    cpdef _clear_class(self)
    cpdef save(self, str path=*)
    cpdef list actives(self)
    cpdef list networks(self)
    cpdef unit(self, int id)
    cpdef list units(self, fun=*)
    cpdef units_add(self, unit)
    cpdef update_proj(self)
    cpdef set_ratio(self, ratio)
    cpdef assemble(self)
    cpdef implement(self)
    cpdef check(self)
    cpdef start(self)
    cpdef kill(self)
    cpdef register_statistic_func(self, func)
    cpdef stop_update(self)
    cpdef restart_update(self)
    cpdef update(self, int delta=*)
    cpdef activate_redis(self, str host=*, int port=*)
    cpdef activate_udp(self, host, port, float interval=*, bint new_thread=*)
    cpdef activate_nats(self, host, port, bint new_thread= *)
    cpdef push_render_event(self, event)
    cpdef push_render_events(self)
    cpdef push_top_box_msg(self, str msg)
    cpdef push_phases_msg(self, str curr_phase, list all_phases)
    cpdef get_entity_symbol_id(self, entity)
    # 分支推演流程相关函数被跳过了
    cpdef xy2lnglat(self, x, y)
    cpdef lnglat2xy(self, lng, lat)
    cpdef get_xy(self, a, b, str coordinate_system=*)
    cpdef get_waypoints(self, list xyz_points=*, list xy_points=*, list lnglat_points=*, height=*)
    cpdef float sim_interval(self, float real_interval=*)
    cpdef next_render_fun(self, str name, str func, args=*, delay=*, delay_ms=*)
    cpdef message_handle(self, MESSAGE message)

    cpdef list _gen_web_render_data(self)
    cpdef _save_command_msg(self, msg)
    cpdef list _gen_web_event_texts(self)
    cpdef dict get_simlation(self)
    cpdef float engine_time(self)