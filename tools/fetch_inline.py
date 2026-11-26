#!/usr/bin/env python3
"""Download blog inline content images locally and write
data/inline_images.json mapping every original URL variant -> local path.
Dedupes size variants (-491x491 / -1024x1024) of the same base image."""
import concurrent.futures as cf
import json
import os
import posixpath
import re
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
DEST = os.path.join(ROOT, "assets", "img", "inline")
os.makedirs(DEST, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def base_of(u):
    return re.sub(r"-\d+x\d+(?=\.[a-z]+$)", "", u)


def size_of(u):
    m = re.search(r"-(\d+)x(\d+)(?=\.[a-z]+$)", u)
    return int(m.group(1)) * int(m.group(2)) if m else 0


def sanitize(url):
    base = posixpath.basename(urllib.parse.unquote(base_of(url)))
    stem = re.sub(r"[^a-z0-9-]+", "-", base.lower()).strip("-")[:60].strip("-")
    if len(stem) < 4:
        import hashlib
        stem = "img-" + hashlib.md5(base_of(url).encode()).hexdigest()[:10]
    ext = os.path.splitext(base)[1] or ".jpg"
    return stem + ext


def main():
    blog = json.load(open(os.path.join(DATA, "blog.json"), encoding="utf-8"))
    featured = json.load(open(os.path.join(DATA, "images.json"), encoding="utf-8"))

    # group every URL variant by base; prefer the largest variant for download
    groups = {}
    for b in blog:
        for u in b.get("imgs") or []:
            groups.setdefault(base_of(u), []).append(u)

    # reuse already-downloaded featured images when the base matches
    mapping = {}   # full url -> local
    done = {}      # base -> local
    for k, v in featured.items():
        if v:
            done.setdefault(base_of(v), v)

    todo = [b for b in groups if b not in done]
    print(f"unique inline images: {len(groups)} | already local: {len(done)} | to fetch: {len(todo)}")

    def work(base):
        best = max(groups[base], key=size_of)
        dest = os.path.join(DEST, sanitize(best))
        rel = "assets/img/inline/" + os.path.basename(dest)
        for cand in (best, *[u for u in groups[base] if u != best]):
            try:
                req = urllib.request.Request(cand, headers=UA)
                with urllib.request.urlopen(req, timeout=60) as r:
                    data = r.read()
                if len(data) < 1000:
                    continue
                with open(dest, "wb") as fh:
                    fh.write(data)
                return base, rel
            except Exception:
                continue
        return base, ""

    with cf.ThreadPoolExecutor(12) as ex:
        for base, rel in ex.map(work, todo):
            done[base] = rel
            if not rel:
                print("FAILED:", base[-50:])

    for base, variants in groups.items():
        for u in variants:
            if u in done:
                mapping[u] = done[u]
            elif base in done and done[base]:
                mapping[u] = done[base]

    with open(os.path.join(DATA, "inline_images.json"), "w", encoding="utf-8") as fh:
        json.dump(mapping, fh, indent=1)
    ok = sum(1 for v in mapping.values() if v)
    print(f"mapped {ok}/{len(mapping)} inline refs to local files")


if __name__ == "__main__":
    main()
