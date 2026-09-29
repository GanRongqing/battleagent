#!/usr/bin/env python
"""build_import_manifest.py — emit OPPONENT_ARTIFACT_MANIFEST.json per validated opponent.
Deterministic bundle hash over entrypoint+config+route/scenario+behaviour files."""
import hashlib, json, os
def bundle_hash(files):
    h=hashlib.sha256()
    for p in sorted(files):
        if os.path.exists(p):
            h.update(open(p,"rb").read())
    return h.hexdigest()
def build(wave, short_id, original_name, source_files, entrypoint, scenario_id="", route_id="",
          config=None, deps=None, black_side_verified=False, hidden_truth_access=False):
    return {"wave":wave,"short_id":short_id,"original_name":original_name,"source_files":source_files,
            "entrypoint":entrypoint,"scenario_id":scenario_id,"route_id":route_id,"config":config or {},
            "artifact_sha256":bundle_hash(source_files),"dependencies":deps or [],
            "black_side_verified":black_side_verified,"hidden_truth_access":hidden_truth_access,
            "import_status":"STATIC_VALIDATED" if black_side_verified else "QUARANTINED"}
if __name__=="__main__":
    print("build_import_manifest: library only (no artifacts present)")
