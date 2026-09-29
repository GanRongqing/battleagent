#!/usr/bin/env python
"""inventory_incoming.py — recursively inventory incoming_opponents/{wave1,wave2}.
Writes INCOMING_INVENTORY.csv next to the module. Read-only; never executes artifacts."""
import csv, hashlib, os, sys
INC = "/root/sc2agent/incoming_opponents"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "INCOMING_INVENTORY.csv")
EXTS = {".rar",".zip",".7z",".tar",".gz",".tgz",".py",".json",".yaml",".yml",".toml",".csv",".db",".sqlite",".txt",".md"}
def sha(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for b in iter(lambda:f.read(65536),b""): h.update(b)
    return h.hexdigest()
def main():
    rows=[]
    for wave in ("wave1","wave2"):
        root=os.path.join(INC,wave)
        for dp,_,fs in os.walk(root):
            for fn in fs:
                p=os.path.join(dp,fn); ext=os.path.splitext(fn)[1].lower()
                if ext not in EXTS: continue
                parent=os.path.basename(dp) if dp!=root else ""
                rows.append({"wave":wave,"original_path":os.path.relpath(p,INC),"file_type":ext,
                             "size":os.path.getsize(p),"mtime":int(os.path.getmtime(p)),
                             "sha256":sha(p),"archive_parent":parent,"status":"RAW"})
    os.makedirs(os.path.dirname(OUT),exist_ok=True)
    with open(OUT,"w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["wave","original_path","file_type","size","mtime","sha256","archive_parent","status"])
        w.writeheader(); w.writerows(rows)
    print(f"INCOMING_INVENTORY.csv rows={len(rows)}")
    return rows
if __name__=="__main__": main()
