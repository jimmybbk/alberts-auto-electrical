#!/usr/bin/env python3
"""Diagnostic: list generated-looking directories that the current build
does NOT produce (stale output from older builds). Read-only."""
import json
import os
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)


def _win_long(p):
    if os.name == "nt":
        return "\\\\?\\" + os.path.abspath(p)
    return p


def ls(p):
    """listdir that copes with >260-char paths on Windows."""
    try:
        return os.listdir(_win_long(p))
    except OSError as e:  # noqa: BLE001
        return ["<ERR %s>" % e]


m = json.load(open(".build-manifest.json", encoding="utf-8"))
current = {urllib.parse.unquote(p).strip("/") for p in m["pages"] + m["stubs"]}
current.discard("")


def is_generated_dir(full):
    """A build output dir holds exactly one file: index.html."""
    try:
        return set(os.listdir(_win_long(full))) == {"index.html"}
    except OSError:
        return False


stale = []
for name in ls("."):
    if name in (".git", "tools", "data", "assets"):
        continue
    full = os.path.join(".", name)
    if os.path.isdir(full) and urllib.parse.unquote(name) not in current and is_generated_dir(full):
        stale.append(name)
for parent in ("blog", "gallery", "testimonial", "service-estimate", "serve"):
    for name in ls(parent):
        full = os.path.join(parent, name)
        if os.path.isdir(full) and urllib.parse.unquote(parent + "/" + name) not in current and is_generated_dir(full):
            stale.append(parent + "/" + name)

print(f"current routes in manifest: {len(current)}")
print(f"stale generated dirs: {len(stale)}")
for s in stale:
    print("  ", s[:90])

# raw-name pass: the comparison above decodes names, which hides
# percent-encoded twins of live pages — list those literally.
twins = [n for n in ls(".") if "%" in n and os.path.isdir(n)]
for parent in ("blog", "gallery", "testimonial", "service-estimate", "serve"):
    twins += [parent + "/" + n for n in ls(parent) if "%" in n and os.path.isdir(os.path.join(parent, n))]
print(f"dirs with a literal % in their name: {len(twins)}")
for t in twins:
    print("  ", t[:90])
