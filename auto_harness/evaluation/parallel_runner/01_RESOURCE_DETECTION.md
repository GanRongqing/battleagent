# 01 — RESOURCE DETECTION
Detects the CONTAINER's usable resources (never the bare host count):
- `os.cpu_count()` (host logical), `os.sched_getaffinity(0)`, cpuset
- cgroup v2 `cpu.max` / cgroup v1 `cpu.cfs_quota_us`,`cpu.cfs_period_us`
- cgroup v2 `memory.max` / v1 `memory.limit_in_bytes`; `/proc/meminfo` MemAvailable
Effective = min(host, affinity, cpuset, quota).

Observed on this server:
```
host_logical_cpu        = 96
affinity_cpu            = 96
cpuset_cpu              = 96
cgroup_cpu_quota        = 9      <- binding constraint
effective_cpu_cores     = 9
cgroup_memory_limit     = 48 GiB
effective_memory_limit  = 48 GiB
max_safe_workers        = 9      (cpu=1 core/episode, ram budget 0.8*limit)
```
`--workers auto` selects `max_safe_workers`, additionally capped by the number of runnable jobs.
