# API Version Audit

| | stable v1 | pomdp_api_v2 |
|---|---|---|
| dir | `hsystem/pomdp_api/main.py` | `pomdp_api_v2/` |
| default port | 8000 | 8001 (`pomdp_api_v2/*.py:13`) |
| upstream | `http://127.0.0.1:6000` | `http://127.0.0.1:8001` (API_URL) |
| used by stable W5 | YES | NO |

DOCUMENTATION_DRIFT: some docs mention v2/8001; the stable W5 path is v1 on :8000. Verified from source.
