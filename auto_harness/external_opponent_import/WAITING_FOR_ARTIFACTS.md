# WAITING_FOR_ARTIFACTS

Please place the original delivered files into:
- `/root/sc2agent/incoming_opponents/wave1/`  (expect 5)
- `/root/sc2agent/incoming_opponents/wave2/`  (expect 6)

Requirements:
- keep original file names
- keep original directory structure
- keep the original archives too
- do NOT rename anything
- do NOT pre-modify strategy code

After arrival the pipeline runs:
1. inventory  2. extract  3. static classify  4. entrypoint recovery
5. Black identity validation  6. exact 5+6 gate  7. 11 smoke episodes
8. artifact freeze  9. 75-episode ACE generalization (seeds 42001-42005)
