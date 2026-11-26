#!/usr/bin/env python3
"""Full-site audit. Usage: python tools/audit.py [BASE_URL]

BASE_URL defaults to the local dev server; pass the GitHub Pages URL to
audit the deployed site with the same checks.

The page list comes from .build-manifest.json (exactly what the last build
produced). Every relative link/asset is resolved the way a browser does it:
urljoin() against the page's OWN url (pages live at <route>/index.html).
Redirect stubs are followed to their target, which must be 200 and must not
point back at itself. Also checks titles/meta/H1 on real pages, every
sitemap URL, and the 404 page."""
import concurrent.futures as cf
import html as hm
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8471").rstrip("/")
IS_LOCAL = urllib.parse.urlparse(BASE).hostname in ("localhost", "127.0.0.1")

REF_RE = re.compile(r'(href|src|data-full)="([^"]+)"')
STUB_RE = re.compile(r'http-equiv="refresh" content="0; url=([^"]+)"')


def safe(url):
    # percent-encode anything non-ASCII without double-encoding existing %XX
    return urllib.parse.quote(url, safe="/:%?=&#$,@+;~!*'()[]")


TRANSIENT = {0, 429, 500, 502, 503, 504}   # CDN/origin hiccups, not site defects


def fetch(url, attempts=4):
    """GET with retries on transient server errors. 404s are returned at once."""
    code, body = 0, b""
    for i in range(attempts):
        try:
            req = urllib.request.Request(safe(url), headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            code, body = e.code, e.read()
        except Exception as e:  # noqa: BLE001
            code, body = 0, str(e).encode()
        if code not in TRANSIENT:
            return code, body
        time.sleep(1.0 + i)  # backoff, then retry
    return code, body


with open(".build-manifest.json", encoding="utf-8") as fh:
    MANIFEST = json.load(fh)
PAGE_PATHS = MANIFEST["pages"]
STUB_PATHS = MANIFEST["stubs"]
STUB_SET = set(STUB_PATHS)
print(f"base: {BASE}")
print(f"build manifest: {len(PAGE_PATHS)} pages, {len(STUB_PATHS)} redirect stubs")


def url_of(path):
    # manifest paths are public URL paths and may already be percent-encoded
    return BASE + "/" + urllib.parse.quote(path, safe="/%")


def fetch_page(path):
    url = url_of(path)
    code, body = fetch(url)
    return path, url, code, body


problems = {"page": [], "links": [], "assets": [], "redirects": [], "content": [], "sitemap": [], "404": []}
targets = {}        # resolved absolute url -> (kind, page path, raw ref)
stub_targets = []   # (path, resolved redirect target)
page_html = {}

with cf.ThreadPoolExecutor(12) as ex:
    crawled = list(ex.map(fetch_page, PAGE_PATHS + STUB_PATHS))

for path, url, code, body in crawled:
    label = "/" + path
    if code != 200:
        problems["page"].append(f"PAGE FAIL {code} {label}")
        continue
    html = body.decode("utf-8", "replace")
    m = STUB_RE.search(html)
    if m:
        if path not in STUB_SET:
            problems["redirects"].append(f"UNEXPECTED REDIRECT on a real page {label}")
        stub_targets.append((path, urllib.parse.urljoin(url, hm.unescape(m.group(1)))))
        continue
    if path in STUB_SET:
        problems["redirects"].append(f"STUB WITHOUT REDIRECT {label}")
        continue
    page_html[path] = html
    refs = list(REF_RE.findall(html))                # (attribute, value)
    for ss in re.findall(r'srcset="([^"]*)"', html):   # every candidate URL in srcset
        refs += [("srcset", c.strip().split(" ")[0]) for c in ss.split(",") if c.strip()]
    for kind, ref in refs:
        if ref.startswith(("mailto:", "tel:", "javascript:")) or ref.startswith("#") or ref == "":
            continue
        if ref.startswith(("http://", "https://", "//")):
            # A resource LOADED from another host is a hotlink (it breaks if that
            # site changes or goes down). Ordinary links are fine, and the Google
            # Maps embed on the contact page is intentional.
            external_resource = kind != "href" and not ref.startswith("https://www.google.com/maps")
            if external_resource:
                problems["assets"].append(f"HOTLINK {label} -> {ref[:100]}")
            continue
        resolved = urllib.parse.urljoin(url, hm.unescape(ref).split("#")[0]).split("#")[0]
        kind = "assets" if re.search(r"\.(css|js|png|jpe?g|webp|ico|svg|woff2?)(\?|$)", resolved, re.I) else "links"
        targets.setdefault(resolved, (kind, label, ref))

n_links = sum(1 for v in targets.values() if v[0] == "links")
n_assets = sum(1 for v in targets.values() if v[0] == "assets")
print(f"unique resolved targets: {n_links} links + {n_assets} assets")


def check_target(item):
    url, (kind, label, ref) = item
    code, _ = fetch(url)
    if code != 200:
        return kind, f"FAIL {code}  on {label}  ->  {ref}   (= /{urllib.parse.unquote(url)[len(BASE) + 1:]})"
    return kind, None


with cf.ThreadPoolExecutor(12) as ex:
    for kind, msg in ex.map(check_target, sorted(targets.items())):
        if msg:
            problems[kind].append(msg)


def check_stub(item):
    path, target = item
    if urllib.parse.unquote(target) == urllib.parse.unquote(url_of(path)):
        return f"REDIRECT LOOP  /{path} -> {target[len(BASE) + 1:]}"
    code, _ = fetch(target)
    if code != 200:
        return f"REDIRECT DEAD {code}  /{path} -> {target[len(BASE) + 1:]}"
    return None


with cf.ThreadPoolExecutor(12) as ex:
    for msg in ex.map(check_stub, stub_targets):
        if msg:
            problems["redirects"].append(msg)

for path, html in page_html.items():
    label = "/" + path
    t = re.search(r"<title>([^<]*)</title>", html)
    if not t or not t.group(1).strip():
        problems["content"].append(f"NO TITLE {label}")
    d = re.search(r'<meta name="description" content="([^"]*)"', html)
    if not d or len(d.group(1).strip()) < 20:
        problems["content"].append(f"THIN/NO META DESC {label}")
    if "<h1" not in html:
        problems["content"].append(f"NO H1 {label}")

# sitemap: strip the site's own path prefix so the same file maps onto any base
with open("sitemap.xml", encoding="utf-8") as fh:
    locs = re.findall(r"<loc>([^<]+)</loc>", fh.read())
prefix = min((urllib.parse.urlparse(l).path for l in locs), key=len)  # home, e.g. /alberts-auto-electrical/


def check_sm(loc):
    path = urllib.parse.urlparse(loc).path
    rel = path[len(prefix):]
    code, _ = fetch(BASE + "/" + rel)
    return None if code == 200 else f"SITEMAP FAIL {code} /{rel}"


with cf.ThreadPoolExecutor(12) as ex:
    for msg in ex.map(check_sm, locs):
        if msg:
            problems["sitemap"].append(msg)
unq_prefix = urllib.parse.unquote(prefix)
sm_rel = set()
for loc in locs:
    p = urllib.parse.unquote(urllib.parse.urlparse(loc).path)
    sm_rel.add(p[len(unq_prefix):] if p.startswith(unq_prefix) else p)
missing_from_sitemap = sorted(p for p in PAGE_PATHS if p and urllib.parse.unquote(p) not in sm_rel)
for p in missing_from_sitemap:
    problems["sitemap"].append(f"NOT IN SITEMAP /{p}")

# 404 page: must load and must be self-contained (absolute refs only)
code, body = fetch(BASE + "/404.html")
page404 = body.decode("utf-8", "replace")
if code != 200:
    problems["404"].append(f"404.html returns {code}")
rel_refs = [r for _, r in REF_RE.findall(page404) if not r.startswith(("http://", "https://", "mailto:", "tel:", "#"))]
if rel_refs:
    problems["404"].append(f"404.html has relative refs (breaks at arbitrary URLs): {rel_refs[:3]}")
if not IS_LOCAL:
    code, body = fetch(BASE + "/this-page-does-not-exist-audit/")
    if code != 404 or "dead wire" not in body.decode("utf-8", "replace"):
        problems["404"].append(f"unknown URL returns {code} without the custom 404 page")

total = sum(len(v) for v in problems.values())
print("=" * 70)
print(f"real pages checked : {len(page_html)}   (redirect stubs: {len(stub_targets)})")
print(f"link targets       : {n_links}")
print(f"asset targets      : {n_assets}")
print(f"sitemap urls       : {len(locs)}")
print("=" * 70)
for k, v in problems.items():
    print(f"\n## {k}: {len(v)}")
    for line in v[:20]:
        print("  " + line)
    if len(v) > 20:
        print(f"  ... and {len(v) - 20} more")
print(f"\nTOTAL PROBLEMS: {total}")
sys.exit(1 if total else 0)
