# BT ↔ Harness Interface — E2E Trace

- scenario: 5+5 vs 10 combat USV, B0_RANDOM
- platform: `white_usv4`
- task_id: `white_usv4_black_usv9_intercept`
- target_id: `black_usv9`
- submit ack: **ACCEPTED**

## tick 1

- tick_id=1  root_status=SUCCESS  branch=engage

- context.safety_feedback (used this tick): (none)

- action_requests:
  - white_usv4 ENGAGE_TARGET target=black_usv9 course=None
  - white_usv4 ORBIT_TARGET target=black_usv9 course=92.59855312463097
- /apply payload:
  - [lock] white_usv4 锁定 black_usv9
  - [move] white_usv4 移动 target_speed=20.0 target_course=92.6
- /apply result: `2 个动作: 2 成功, 0 跳过`
- task_feedback: phase=engage target=black_usv9 visible=True need_reallocation=False reason=none

## tick 2

- tick_id=2  root_status=SUCCESS  branch=engage

- context.safety_feedback (used this tick): {"white_usv4 锁定 black_usv9": "ACCEPTED", "white_usv4 移动 target_speed=20.0 target_course=92.6": "ACCEPTED"}

- action_requests:
  - white_usv4 ENGAGE_TARGET target=black_usv9 course=None
  - white_usv4 ORBIT_TARGET target=black_usv9 course=92.61478181129436
- /apply payload:
  - [lock] white_usv4 锁定 black_usv9
  - [move] white_usv4 移动 target_speed=20.0 target_course=92.6
- /apply result: `2 个动作: 1 成功, 1 跳过`
- task_feedback: phase=engage target=black_usv9 visible=True need_reallocation=False reason=none

## tick 3

- tick_id=3  root_status=SUCCESS  branch=hold

- context.safety_feedback (used this tick): {"white_usv4 锁定 black_usv9": "REJECTED", "white_usv4 移动 target_speed=20.0 target_course=92.6": "ACCEPTED"}

- action_requests:
  - white_usv4 HOLD target=black_usv9 course=None
- /apply payload:
  - [move] white_usv4 移动 target_speed=20.0 target_course=90.0
- /apply result: `1 个动作: 1 成功, 0 跳过`
- task_feedback: phase=hold target=black_usv9 visible=False need_reallocation=False reason=safety_rejected

