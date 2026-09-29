# REQUESTED_OPPONENT_REGISTRY.md — 4 + 5 + 6 (per user-provided provenance)

## 本机旧策略 (OLD_LOCAL = 4/4 CONFIRMED)
- B0 = black-b0-v1 `B0_RANDOM` — `opponent_profiles.py` / strategy_library; entry `scenario_builder random_waypoint`
- B1 = black-b1-v1 `B1_MULTI_AXIS` — `opponent_profiles._multi_axis_paths`
- B2 = black-b2-v1 `B2_COORDINATED_PRESSURE` — `opponent_profiles._coordinated_pressure_paths`
- B3 = black-b3-v1 `B3_ADAPTIVE` — `opponent_profiles` runtime legal replan
(These are LOCAL, not external.)

## 第一批 / 两类敌人.rar  (WAVE1)
Only `.rar` on the machine = `/root/autodl-tmp/hsystem/wang.rar`
sha256 `4518380078c182c58de44560fb5e7474c674a17d30792fd6bc3a90eb645e8824`.
It literally delivers **two** enemy types (hence "两类敌人"): `分散式` (dispersed) + `两波次` (two-wave).
- W1-1 = 分散式 (dispersed) → `external_dispersed.py` → `测试1-黑方艇分散式前进.json`
- W1-2 = 两波次 (two-wave) → `external_twowave.py` → `测试2-黑方艇两波次前进.json`
- (In the RAR the .py name and the JSON it loads are swapped; integration copies correct the mapping.)
- W1-3..W1-5 = **NOT FOUND** → Wave1 found **2 / 5** → `COUNT_MISMATCH`.
No file named `两类敌人.rar` exists anywhere on the machine; `wang.rar` is the only `.rar`.

## 第二批 / 六个策略.zip  (WAVE2 = 6/6 CONFIRMED)
Source `/root/sc2agent/六个策略.zip` + unpacked `/root/sc2agent/six_strategies/六个策略/`.
`sces.json` registers exactly 6; Black side = BLUE `usv1..30` scripted routes (audit confirmed).
- W2-1 = 横向编队-中央汇聚箭头突防 (路线1)
- W2-2 = 菱形编队-接近后扇形展开突防 (路线4)
- W2-3 = 菱形编队-两翼包抄中央突进 (路线3)
- W2-4 = 菱形编队-南北两翼镜像夹击 (路线2)
- W2-5 = 菱形编队-中央汇聚箭头突防 (路线1)
- W2-6 = 菱形编队-MUSV外侧绕行SUSV中央收缩 (路线5)
(7th file `菱形编队-右下佯攻右上突袭.py` / 路线6 is NOT registered → excluded.)
