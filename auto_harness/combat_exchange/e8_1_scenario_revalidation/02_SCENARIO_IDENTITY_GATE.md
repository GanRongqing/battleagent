# 02 — SCENARIO IDENTITY GATE (fail-closed)
`identity_gate.py <run_id> <sid> <policy>` uses **independent evidence**: the worker's **real**
`simserver/temp.py` (the scenario script the simulator actually loaded), plus the game log and result.

Checks per run:
- `EFFECTIVE_IDENTITY_VALID`: every worker's `temp.py` is a **real file** (not a symlink) and contains the
  expected `strategy_filename` for the requested scenario.
- `LOG_ATTRIBUTION_VALID`: the game log `script_name` equals the requested plan.
- `RESULT_VALID`: result `Valid == True`.
- `SCENARIO_IDENTITY_VALID = all of the above`.

Expected plan/route:
| sid | plan | route |
|---|---|---|
| W2-1 | 横向编队-中央汇聚箭头突防 | 路线1-中央汇聚箭头突防.json |
| W2-2 | 菱形编队-接近后扇形展开突防 | 路线4-接近后扇形展开突防.json |
| W2-4 | 菱形编队-南北两翼镜像夹击 | 路线2-南北两翼镜像夹击.json |
| W2-6 | 菱形编队-MUSV外侧绕行SUSV中央收缩 | 路线5-MUSV外侧绕行SUSV中央收缩.json |

Policy: **NO/UNKNOWN identity => the run is excluded from the comparison.** Multi-job parallel
invocations remain **unusable for formal experiments** until they pass this gate; E8.1 uses **one job per
invocation**.
