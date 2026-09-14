"""behavior_tree 端口接入包 — 行为树决策库（经 POMDP API 端口驱动）

契约与实现:
  harness_interface.py   端口 ↔ 执行器接口契约（TaskCommand/ActionRequest/
                         PlatformExecutive/BTActionAdapter，纯标准库）
  status.py              行为树三态 + 引擎事实常量（可经任务 constraints 覆盖）
  base.py                节点定义（Node/Behavior/Sequence/Selector/BehaviorTree，含 memory）
  blackboard.py          黑板（树内共享记忆）
  helpers.py             树内工具与通用行为（safety_hold/hold/条件）
  usv_bt.py              USV 最小真实树（拦截锁定/打击/待命）
  uav_bt.py              UAV 最小真实树（协同锁定/态势更新/返航补能）
  bt_bridge.py           ExecutionContext ↔ Blackboard 唯一翻译处（网络职责为 0）
  tree_manager.py        树实例工厂（platform_id + platform_type → 树）

驱动:
  bt_port_agent.py       本地驱动 — 纯 HTTP 客户端（默认分配器 →
                         /bt/task → /bt/actions → /apply），不直连 gRPC
  bt_port_runner.py      服务器驱动 — 同管线但用 agent_hybrid_v5 分配器
                         （部署在远程 hsystem 根目录时 import 该模块）

本包不再包含直连 gRPC 的旧路径（原 bt_agent/sim_direct/bt_bridge/旧树），
行为树只经 POMDP API 端口接入。
"""
