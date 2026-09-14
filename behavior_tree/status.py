"""行为树三态 + 引擎事实常量"""

from enum import Enum

# ============================================================================
# 三态
# ============================================================================


class Status(str, Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


# ============================================================================
# 引擎事实常量（默认值，可经 TaskCommand.constraints 覆盖）
# ============================================================================

STANDOFF_DEFAULT_M = 35_000.0   # 接近机动目标距离：进入传感与武器作用圈
GOTO_RANGE_M = 10_000.0         # UAV 飞赴任务点到达判定半径
LAND_RANGE_M = 5_000.0          # UAV 返航至母舰附近后转入降落请求的距离
USV_APPROACH_SPEED = 20.0       # USV 接近速度 (m/s)
USV_ORBIT_SPEED = 20.0          # USV 环绕 standoff 速度 (m/s)
USV_PATROL_SPEED = 20.0         # USV 待命/巡逻速度 (m/s)
UAV_CRUISE_SPEED = 100.0        # UAV 巡航速度 (m/s)
UAV_TAKEOFF_COURSE = 90.0       # UAV 起飞航向（度）
UAV_LAND_SPEED_LIMIT = 100.0    # 引擎降落前提: speed < 100（cmd_uav_land 硬性要求）
UAV_LAND_APPROACH_SPEED = 60.0  # 降落前减速目标速度（>此速度先减速，保证 land 时稳定 <100）
