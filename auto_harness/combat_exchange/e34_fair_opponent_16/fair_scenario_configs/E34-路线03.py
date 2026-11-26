from sim_script.scenario.adaptation import (
    build_simulation,
    configure_matplotlib,
    run_simulation,
)


configure_matplotlib()

import simulation.core as core
import simulation.utilities as utl


@utl.check.check_sim
def sim(
    simserver=None,
    engine_name="20250803水面所仿真2",
    web_ip=None,
    gengtu_ip=None,
    user_name="admin",
    render_config=None,
    checkbox_dict=None,
    logtag=None,
):
    return build_simulation(
        core,
        engine_name=engine_name,
        area_filename="台岛东南部海域.json",
        strategy_filename="路线03-双翼回旋中路穿插.json",
        anchor=__file__,
        simserver=simserver,
        web_ip=web_ip,
        user_name=user_name,
        render_config=render_config,
        checkbox_dict=checkbox_dict,
        logtag=logtag,
        formation_mode="horizontal_30",
    )


if __name__ == "__main__":
    run_simulation(sim, "台岛东南部海域-横向编队-双翼回旋中路穿插")
