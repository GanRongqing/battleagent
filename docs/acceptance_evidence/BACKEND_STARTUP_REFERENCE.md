# Backend Startup Reference

`hsystem/simserver/base_server.py` CLI args (source lines 1116-1120):
- `--ip` (default 0.0.0.0)
- `--port` (default 6000)
- `--min_simserver_port` (default 6001)
- `--simserver_num` (default 5)
- `--only_start_simserver` (default False)

Spawn: `base_server` launches `sim_server.py --port <p> --baseserver_ip <ip>` (line 1110).

Canonical start (as used in this environment): `/tmp/opencode/start_services.sh`:
```
base_server.py --simserver_num 3   (PYTHONPATH=.:..:../simulation)
pomdp_api/main.py                   (SIM_HOST=127.0.0.1, :8000)
```
