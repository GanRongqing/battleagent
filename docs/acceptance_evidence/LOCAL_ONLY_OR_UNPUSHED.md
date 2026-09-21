# LOCAL_ONLY_OR_UNPUSHED

Files/dirs present in the working tree (`/root/autodl-tmp/hsystem`) but NOT present in the git repo (`githsysys`):

| auto_harness/phase2a_lateral_coverage | in_working_tree=True | in_repo=False | UNPUSHED |
| auto_harness/phase2b_forward_sweep | in_working_tree=True | in_repo=False | UNPUSHED |
| auto_harness/phase3_assignment_engagement | in_working_tree=True | in_repo=False | UNPUSHED |
| auto_harness/phase4_track_freshness | in_working_tree=True | in_repo=False | UNPUSHED |
| auto_harness/phase5_lock_transition_audit | in_working_tree=True | in_repo=False | UNPUSHED |
| auto_harness/phase6_oracle_decomposition | in_working_tree=True | in_repo=False | UNPUSHED |
| auto_harness/phase7_oracle_guided | in_working_tree=True | in_repo=False | UNPUSHED |
| evaluation | in_working_tree=True | in_repo=False | UNPUSHED |
| oracle_visibility_adapter.py | in_working_tree=True | in_repo=False | UNPUSHED |
| agent_hybrid_w5_translog.py | in_working_tree=True | in_repo=False | UNPUSHED |
| agent_hybrid_w5_tracklog.py | in_working_tree=True | in_repo=False | UNPUSHED |
| agent_hybrid_oracle.py | in_working_tree=True | in_repo=False | UNPUSHED |
| agent_hybrid_w8_containment.py | in_working_tree=True | in_repo=True | OK |
| agent_hybrid_w8_fwdsw.py | in_working_tree=True | in_repo=False | UNPUSHED |
| agent_hybrid_w8_latcov.py | in_working_tree=True | in_repo=False | UNPUSHED |
| external_opponents | in_working_tree=True | in_repo=False | UNPUSHED |
| b0_v2 | in_working_tree=True | in_repo=True | OK |
| docs/team_sync | in_working_tree=True | in_repo=True | OK |
| docs/acceptance_evidence | in_working_tree=True | in_repo=False | UNPUSHED |

Note: hsystem is not a git repo; the repo (githsysys) is a periodically rsynced copy. Any phase produced after the last sync is UNPUSHED.