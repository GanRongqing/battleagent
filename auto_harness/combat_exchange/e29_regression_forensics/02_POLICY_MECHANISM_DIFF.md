# 02 — POLICY MECHANISM DIFF
| policy | USV no-target | UAV recon | boundary safety | split screen |
|---|---|---|---|---|
| C10 | GLOBAL→screen(SCREEN_X=120k), NORMAL→east | broad search | none | no |
| C19 | GLOBAL screen redir→press east | broad | none | no |
| C25 | press east (C19) | fleet-tethered (front+30km) | none | no |
| C27 | press east | fleet-tethered | **BoundaryAwareSafety (USV+UAV, hardcoded W2 area)** | no |
| C30 | C27 | C27 | C27 | **name-index%3==0 → screen(120k)** |
`universal_safety.py`: `AREA=(0,370400,-277800,277800)`, `CENTER=(185200,0)`; for every USV/UAV move, if predicted next position is outside this box → rewrite course toward CENTER.
Scale scenarios (`scenario_builder`) deploy White at **y∈[375000,435000] km**, x≈0.6 km — entirely OUTSIDE the hardcoded box.
