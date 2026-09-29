# 00 — Deep Wave Artifact Search Scope

Trigger: user asserts Wave1(5)/Wave2(6) ARE on this machine; prior MISSING verdict treated as a
possible FALSE NEGATIVE. Method: multi-path reverse lookup — NOT name-only.

Checklist executed:
1. mounted filesystem inventory (mount/df/findmnt)
2. all archives inventory (rar/zip/7z/tar/tgz/bz2/xz)
3. nested archive scan (up to depth-3 listing)
4. directory cluster scan (~5 / ~6 sibling .py/.json)
5. untracked/ignored git scan
6. git all branches / stash / reflog
7. shell history scan (/root/.bash_history, /home/coder/.bash_history)
8. recent-file timeline scan (Sep 13–17 delivery window)
9. static Black-side signature scan (black_movement|opponent_profile|get_black_targets|WaypointsMotor|...)
10. Claude Code session logs + paste-cache, opencode prompt-history
