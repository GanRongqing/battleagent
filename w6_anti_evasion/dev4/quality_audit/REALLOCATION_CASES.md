# Reallocation Cases (live, trail-audited)

| Event | Seed | Type | Platform | Old | New | Reason | Dest ETA s | Lead ETA s | persist≥300 | Dead | Verdict |
|---|---|---|---|---|---|---|---:|---:|---|---|---|
| e0 | 4001 | REALLOC_FREE | white_usv1 | – | black_usv1 | BREAKTHROUGH_URGENT | 17550 | – | yes | no | GOOD |
| e1 | 4003 | REALLOC_FREE | white_usv7 | – | black_usv20 | BETTER_INTERCEPTOR | 4360 | 6788 | yes | no | GOOD |
| e2 | 4003 | REALLOC_FREE | white_usv8 | – | black_usv20 | BETTER_INTERCEPTOR | 4597 | 6352 | yes | no | GOOD |
| e3 | 4002 | REALLOC_FREE | white_usv8 | – | black_usv1 | BREAKTHROUGH_URGENT | 15825 | 10434 | yes | no | GOOD |
| e4 | 4002 | REALLOC_FREE | white_usv3 | – | black_usv1 | BREAKTHROUGH_URGENT | 16697 | 10200 | yes | no | GOOD |
| e5 | 4002 | REALLOC_FREE | white_usv8 | – | black_usv1 | BREAKTHROUGH_URGENT | 15846 | 10189 | no | no | BAD (late, sim~21.5k) |
| e6 | 4002 | REALLOC_FREE | white_usv3 | – | black_usv1 | BREAKTHROUGH_URGENT | 17168 | 9932 | no | no | BAD (late, sim~21.7k) |

Notes: all events are FREE additions to imminent corridors (no SOFT release / handoff fired in
these 5 draws). No hard-commit violation, no execution override, no death within 600 s.
