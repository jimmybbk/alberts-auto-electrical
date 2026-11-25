#!/usr/bin/env python3
"""Download featured images for blog posts + gallery items into assets/.
Writes data/images.json mapping slug -> local path (empty string if failed)."""
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
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
ORIG = "https://albertsautoelectrical.com.au"


def sanitize(s, maxlen=40):
    s = urllib.parse.unquote(s)
    s = re.sub(r"[^a-z0-9-]+", "-", s.lower()).strip("-")
    return s[:maxlen].strip("-")


def basename(url):
    return posixpath.basename(urllib.parse.unquote(url))


def fetch(url, dest):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    with open(dest, "wb") as fh:
        fh.write(data)
    return len(data)


def try_download(img_url, dest):
    """Try a WordPress 1024-wide variant first to keep sizes sane."""
    candidates = []
    if "-scaled." in img_url:
        candidates.append(img_url.replace("-scaled.", "-1024x768."))
        candidates.append(img_url.replace("-scaled.", "-768x576."))
    candidates.append(img_url)
    for u in candidates:
        try:
            return fetch(u, dest), u
        except Exception:
            continue
    return 0, None


def main():
    jobs = []  # (kind, slug, image_url)
    blog = json.load(open(os.path.join(DATA, "blog.json"), encoding="utf-8"))
    gal = json.load(open(os.path.join(DATA, "gallery.json"), encoding="utf-8"))
    for b in blog:
        if b["image"]:
            jobs.append(("blog", b["slug"], b["image"]))
    for g in gal:
        if g["image"]:
            jobs.append(("gallery", g["slug"], g["image"]))

    mapping = {}

    def work(job):
        kind, slug, url = job
        base = basename(url)
        ext = os.path.splitext(base)[1] or ".jpg"
        subdir = "blog" if kind == "blog" else "gallery-items"
        dest_dir = os.path.join(ROOT, "assets", "img", subdir)
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, f"{sanitize(slug)}{ext}")
        try:
            size, used = try_download(url, dest)
            if size:
                rel = posixpath.join("assets", "img", subdir, os.path.basename(dest))
                return (kind, slug, rel, used)
        except Exception as e:  # noqa: BLE001
            print("FAIL", slug, e)
        return (kind, slug, "", url)

    with cf.ThreadPoolExecutor(12) as ex:
        for kind, slug, rel, used in ex.map(work, jobs):
            mapping[f"{kind}:{slug}"] = rel
            if not rel:
                print("hotlink fallback:", slug)

    with open(os.path.join(DATA, "images.json"), "w", encoding="utf-8") as fh:
        json.dump(mapping, fh, indent=1)
    ok = sum(1 for v in mapping.values() if v)
    print(f"downloaded {ok}/{len(jobs)} images")


if __name__ == "__main__":
    main()
