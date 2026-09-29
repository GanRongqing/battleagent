#!/usr/bin/env python
"""extract_archives.py — extract incoming archives into incoming_opponents/extracted/<wave>/<sha16>/.
Never overwrites repo files; never executes contained scripts."""
import hashlib, os, subprocess, sys
INC="/root/sc2agent/incoming_opponents"
def sha(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for b in iter(lambda:f.read(65536),b""): h.update(b)
    return h.hexdigest()
def main():
    for wave in ("wave1","wave2"):
        root=os.path.join(INC,wave)
        for dp,_,fs in os.walk(root):
            for fn in fs:
                p=os.path.join(dp,fn); ext=os.path.splitext(fn)[1].lower()
                if ext not in (".rar",".zip",".7z",".tar",".gz",".tgz"): continue
                dest=os.path.join(INC,"extracted",wave,sha(p)[:16]); os.makedirs(dest,exist_ok=True)
                try:
                    if ext==".rar": subprocess.run(["unrar","x","-y",p,dest+"/"],check=False,capture_output=True)
                    elif ext==".zip": subprocess.run(["unzip","-o","-q",p,"-d",dest],check=False,capture_output=True)
                    elif ext in (".tar",".gz",".tgz"): subprocess.run(["tar","-xf",p,"-C",dest],check=False,capture_output=True)
                    elif ext==".7z": subprocess.run(["7z","x","-y","-o"+dest,p],check=False,capture_output=True)
                    print("extracted",p,"->",dest)
                except Exception as e:
                    print("extract-fail",p,e)
if __name__=="__main__": main()
