"""树实例管理 — platform_id + platform_type → 树实例

与旧模块的 tree_manager 同名同职责（树实例工厂）。树记忆在实例内部
（blackboard），不暴露树外；执行器（BTPlatformExecutive）每个平台
持有一棵经本模块构造的树。
"""

from .base import BehaviorTree
from .harness_interface import PlatformType
from .uav_bt import build_uav_tree
from .usv_bt import build_usv_tree


def make_executive_tree(platform_id: str,
                        platform_type: PlatformType) -> BehaviorTree:
    """按平台类型构造执行器树实例"""
    if PlatformType(platform_type) == PlatformType.UAV:
        return build_uav_tree(platform_id)
    return build_usv_tree(platform_id)
