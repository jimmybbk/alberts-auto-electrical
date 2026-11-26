#!/usr/bin/env python3
"""Full-site audit: crawls every generated page, checks
1. every internal link resolves (200)
2. every local asset reference exists on disk; no hotlinks to the original site
3. content sanity on real pages (redirect stubs are exempt)
4. every sitemap URL resolves"""
import concurrent.futures as cf
import os
import re
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
BASE = "http://localhost:8471"

pages = []
for dirpath, dirnames, filenames in os.walk("."):
    dirnames[:] = [d for d in dirnames if d not in (".git", "tools", "node_modules", "data")]
    if "index.html" in filenames:
        rel = os.path.relpath(dirpath, ".").replace("\\", "/").replace("./", "")
        pages.append(rel)
pages = sorted(set(pages))
print(f"pages found: {len(pages)}")


def page_url(route):
    # always percent-encode non-ASCII path segments
    return BASE + "/" + urllib.parse.quote(route + "/" if route else "")  # route from disk is decoded


def fetch_status(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception as e:  # noqa: BLE001
        return 0, str(e).encode()


problems = {"links": [], "assets": [], "content": [], "sitemap": []}
all_links = set()
asset_refs = set()
page_html = {}
stubs = set()

for route in pages:
    code, body = fetch_status(page_url(route))
    page_html[route] = body
    if code != 200:
        problems["links"].append(f"PAGE FAIL {code} /{route}/")
        continue
    html = body.decode("utf-8", "replace")
    if 'http-equiv="refresh"' in html:
        stubs.add(route)  # redirect stub: exempt from content checks
        continue
    for m in re.finditer(r'(?:href|src|data-full)="([^"]+)"', html):
        u = m.group(1)
        if u.startswith(("http://", "https://", "mailto:", "tel:", "#", "javascript:")):
            if u.startswith(("http://", "https://")) and "albertsautoelectrical.com.au" in u:
                problems["assets"].append(f"HOTLINK /{route}/ -> {u[:100]}")
            continue
        if u.startswith("//"):
            continue
        path = u.split("#")[0]
        if not path:
            continue
        if re.search(r"\.(css|js|png|jpg|jpeg|webp|ico|svg)$", path, re.I):
            asset_refs.add((route, path))
        else:
            all_links.add((route, path))

print(f"unique internal links: {len(all_links)} | asset refs: {len(asset_refs)} | stubs: {len(stubs)}")


def resolve_local(route, path):
    # every page lives at <route>/index.html, so its directory IS the route
    base_dir = route if route else "."
    full = os.path.normpath(os.path.join(".", base_dir, path))
    return full


for route, path in sorted(asset_refs):
    full = resolve_local(route, urllib.parse.unquote(path))
    if not os.path.isfile(full):
        problems["assets"].append(f"MISSING ASSET /{route}/ -> {path}")


def check_link(item):
    route, path = item
    if path.startswith("assets/"):
        url = BASE + "/" + urllib.parse.quote(path)
    else:
        base_dir = os.path.dirname(route)
        joined = os.path.normpath(os.path.join(base_dir, path)).replace("\\", "/").lstrip("./")
        joined = urllib.parse.unquote(joined)  # normalize, then encode once
        if "." in os.path.basename(joined):
            url = BASE + "/" + urllib.parse.quote(joined)
        else:
            url = BASE + "/" + urllib.parse.quote(joined + "/")
    code, _ = fetch_status(url)
    if code != 200:
        return f"LINK FAIL {code} /{route}/ -> {path}"
    return None


with cf.ThreadPoolExecutor(16) as ex:
    for r in ex.map(check_link, sorted(all_links)):
        if r:
            problems["links"].append(r)

for route, body in page_html.items():
    if route in stubs:
        continue
    html = body.decode("utf-8", "replace")
    if not html.strip():
        continue
    t = re.search(r"<title>([^<]*)</title>", html)
    title = t.group(1).strip() if t else ""
    if not title:
        problems["content"].append(f"NO TITLE /{route}/")
    d = re.search(r'<meta name="description" content="([^"]*)"', html)
    if not d or len(d.group(1).strip()) < 20:
        problems["content"].append(f"THIN/NO META DESC /{route}/")
    if "<h1" not in html:
        problems["content"].append(f"NO H1 /{route}/")

with open("sitemap.xml", encoding="utf-8") as fh:
    sm = fh.read()
locs = re.findall(r"<loc>([^<]+)</loc>", sm)
print(f"sitemap urls: {len(locs)}")


def check_sm(u):
    code, _ = fetch_status(u)
    return None if code == 200 else f"SITEMAP FAIL {code} {u}"


with cf.ThreadPoolExecutor(16) as ex:
    for r in ex.map(check_sm, locs):
        if r:
            problems["sitemap"].append(r)

total = sum(len(v) for v in problems.values())
print("=" * 60)
for k, v in problems.items():
    print(f"\n## {k}: {len(v)}")
    for line in v[:25]:
        print("  " + line)
    if len(v) > 25:
        print(f"  … and {len(v) - 25} more")
print(f"\nTOTAL PROBLEMS: {total}")
