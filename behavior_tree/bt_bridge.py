"""BTBridge — ExecutionContext ↔ Blackboard 唯一翻译处（网络职责为 0）

pre_tick:  ExecutionContext → Blackboard（只填黑板，不直写仿真）
post_tick: Blackboard → BTStepResult（只打包，不直写仿真）
任务键（task.*）由 submit_task 写入黑板，本桥只刷新运行时上下文。
"""

from typing import List

from .harness_interface import (
    BTStepResult, ExecutionContext, FeedbackReason, Phase, TaskFeedback,
    TaskStatus)
from .base import BehaviorTree
from .status import Status


class BTBridge:

    @staticmethod
    def pre_tick(tree: BehaviorTree, context: ExecutionContext) -> None:
        bb = tree.blackboard
        bb.set("ctx.sim_time", context.sim_time)
        bb.set("ctx.platform_state", dict(context.platform_state))
        bb.set("ctx.tracks", dict(context.tracks))
        bb.set("ctx.safety", dict(context.safety_feedback or {}))
        bb.set("ctx.controller_feedback", context.controller_feedback)

        # 目标可见性记账（lost_at / last_seen_pos 供 reacquire 使用）
        target = bb.get("task.target_id")
        bb.set("target_visible", False)
        bb.set("target_confidence", 0.0)
        if target:
            tr = (context.tracks or {}).get(target)
            if tr and tr.get("visible"):
                bb.set("target_visible", True)
                bb.set("target_confidence", float(tr.get("confidence", 1.0)))
                bb.set("last_seen_pos", tr.get("position"))
                bb.set("lost_at", None)
            elif bb.get("lost_at") is None:
                bb.set("lost_at", context.sim_time)

        # 每 tick 重置输出区
        bb.set("actions", [])
        bb.set("need_reallocation", False)
        bb.set("reason", FeedbackReason.none)
        bb.set("phase", None)
        bb.set("active_branch", None)

    @staticmethod
    def post_tick(tree: BehaviorTree, context: ExecutionContext,
                  root_status: Status) -> BTStepResult:
        bb = tree.blackboard
        # 同平台同 tick 每通道至多 1 个请求（防御性去重，树本身已保证）
        seen = set()
        actions: List = []
        for a in bb.get("actions") or []:
            if a.channel in seen:
                continue
            seen.add(a.channel)
            actions.append(a)

        feedback = TaskFeedback(
            platform_id=context.platform_id,
            task_id=bb.get("task.task_id") or "",
            status=bb.get("task.status") or TaskStatus.RUNNING,
            phase=(bb.get("phase") or Phase.hold).value,
            target_id=bb.get("task.target_id"),
            target_visible=bool(bb.get("target_visible")),
            target_confidence=float(bb.get("target_confidence") or 0.0),
            need_reallocation=bool(bb.get("need_reallocation")),
            reason_code=bb.get("reason") or FeedbackReason.none)
        return BTStepResult(
            tick_id=0, platform_id=context.platform_id,
            root_status=root_status.value, action_requests=actions,
            task_feedback=feedback, active_branch=bb.get("active_branch"))
