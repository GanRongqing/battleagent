#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""resource_detector.py — container-aware CPU/Memory detection for the parallel evaluation runner.

Detects the CPU quota/mem limit that the CONTAINER is actually allowed to use (not just host logical
CPUs): os.sched_getaffinity, cpuset, cgroup v1/v2 quotas, and cgroup memory limits.
"""
import os


def _read(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except Exception:
        return None


def _affinity_cores():
    try:
        return len(os.sched_getaffinity(0))
    except Exception:
        return os.cpu_count() or 1


def _cpuset_cores():
    v = _read("/sys/fs/cgroup/cpuset.cpus.effective") or _read("/sys/fs/cgroup/cpuset/cpuset.cpus")
    if not v:
        return None
    n = 0
    for part in v.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-"); n += int(b) - int(a) + 1
        else:
            n += 1
    return n or None


def _cgroup_cpu_quota():
    # cgroup v2
    v = _read("/sys/fs/cgroup/cpu.max")
    if v:
        parts = v.split()
        if len(parts) == 2:
            if parts[0] == "max":
                return None
            return max(1, int(int(parts[0]) / int(parts[1])))
    # cgroup v1
    q = _read("/sys/fs/cgroup/cpu/cpu.cfs_quota_us")
    p = _read("/sys/fs/cgroup/cpu/cpu.cfs_period_us")
    if q and p and int(q) > 0:
        return max(1, int(int(q) / int(p)))
    return None


def _cgroup_mem_limit():
    v = _read("/sys/fs/cgroup/memory.max")           # v2
    if v and v != "max":
        return int(v)
    v = _read("/sys/fs/cgroup/memory/memory.limit_in_bytes")  # v1
    if v and int(v) < (1 << 62):
        return int(v)
    return None


def _mem_available():
    try:
        for line in open("/proc/meminfo"):
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024
    except Exception:
        pass
    return None


def detect():
    host_cpu = os.cpu_count() or 1
    affinity = _affinity_cores()
    cpuset = _cpuset_cores()
    quota = _cgroup_cpu_quota()
    candidates = [host_cpu, affinity] + ([cpuset] if cpuset else []) + ([quota] if quota else [])
    effective_cpu = max(1, min(candidates))
    mem = _cgroup_mem_limit() or _mem_available() or (1 << 40)
    avail = _mem_available() or mem
    return {
        "host_logical_cpu": host_cpu,
        "affinity_cpu": affinity,
        "cpuset_cpu": cpuset,
        "cgroup_cpu_quota": quota,
        "effective_cpu_cores": effective_cpu,
        "cgroup_memory_limit": mem,
        "mem_available": avail,
        "effective_memory_limit": min(mem, avail),
    }


def plan(effective_cpu, effective_mem, cpu_per_episode=1.0, ram_per_episode=1.2e9, reserve_cpu=0.0):
    """Suggested max safe workers. cpu_per_episode/ram_per_episode measured by benchmark if available."""
    by_cpu = int(max(1, (effective_cpu - reserve_cpu) // cpu_per_episode))
    by_mem = int(max(1, (effective_mem * 0.8) // ram_per_episode))
    return max(1, min(by_cpu, by_mem))


if __name__ == "__main__":
    import json
    d = detect()
    d["max_safe_workers(cpu=1/ep)"] = plan(d["effective_cpu_cores"], d["effective_memory_limit"])
    print(json.dumps(d, indent=2))
