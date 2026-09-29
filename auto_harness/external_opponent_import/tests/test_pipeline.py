#!/usr/bin/env python
"""test_pipeline.py — self-checks for the import pipeline (no artifacts required)."""
import json, os, sys
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.join(HERE,"..")
def test_schemas_valid_json():
    for s in ("opponent_artifact.schema.json","opponent_registry.schema.json"):
        json.load(open(os.path.join(ROOT,"schemas",s)))
def test_tools_present():
    need=["inventory_incoming.py","extract_archives.py","classify_artifacts.py","recover_entrypoints.py",
          "validate_black_identity.py","build_import_manifest.py","run_black_smoke.py","freeze_artifact.py",
          "build_eval_registry.py"]
    for t in need:
        assert os.path.exists(os.path.join(ROOT,"tools",t)), t
def test_registry_scaffold_shape():
    reg=json.load(open(os.path.join(ROOT,"external_wave_registry.json")))
    assert reg["wave1"]==[] and reg["wave2"]==[]
    assert reg["gate"]=="WAITING_FOR_EXTERNAL_ARTIFACTS"
if __name__=="__main__":
    ts=[v for k,v in sorted(globals().items()) if k.startswith("test_")]
    import traceback; fail=0
    for t in ts:
        try: t(); print("PASS",t.__name__)
        except Exception as e: fail+=1; print("FAIL",t.__name__,e)
    print("="*40); print("PASS" if not fail else "FAIL",f"{len(ts)-fail}/{len(ts)}"); sys.exit(1 if fail else 0)
