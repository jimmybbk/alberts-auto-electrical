#!/usr/bin/env python3
"""Remove stale percent-encoded duplicate directories (decoded twin must exist)."""
import os
import shutil
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
removed = kept = 0
for entry in os.listdir("."):
    if os.path.isdir(entry) and "%" in entry:
        twin = urllib.parse.unquote(entry)
        if os.path.isdir(twin):
            longp = "\\\\?\\" + os.path.abspath(entry)
            shutil.rmtree(longp)
            removed += 1
        else:
            kept += 1
            print("KEEP (no decoded twin):", entry[:60])
print(f"removed {removed} stale dirs, kept {kept}")
