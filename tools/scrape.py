#!/usr/bin/env python3
"""One-off scraper: pulls blog posts, testimonials, gallery items and
service-estimate entries from the original WordPress site into data/*.json.
Stdlib only. Content is stored as clean text; images referenced by URL."""
import concurrent.futures as cf
import html as hm
import json
import os
import re
import urllib.request

BASE = "https://albertsautoelectrical.com.au"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data")
os.makedirs(OUT, exist_ok=True)


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "replace")


def sitemap_locs(sm):
    txt = get(f"{BASE}/{sm}.xml")
    return [l for l in re.findall(r"<loc>([^<]+)</loc>", txt) if "wp-content" not in l]


def strip_tags(s):
    s = re.sub(r"<script.*?</script>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<style.*?</style>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = hm.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def balanced_div(txt, start_idx):
    depth = 0
    for m in re.finditer(r"<div\b[^>]*>|</div>", txt[start_idx:]):
        depth += -1 if m.group(0).startswith("</") else 1
        if depth == 0:
            return start_idx + m.end()
    return len(txt)


def extract_content(page):
    """Return (text, [image urls]) from the main content block.
    The car-repair-services theme renders post body as plain markup between
    the </h1> title and the single-content-footer / prev-next block."""
    m = re.search(r"</h1\s*>", page)
    start = m.end() if m else 0
    ends = [len(page)]
    for marker in ("single-content-footer", "single-nav-post", "post-tags", "side-block", "<footer"):
        i = page.find(marker, start)
        if i != -1:
            ends.append(page.rfind("<", 0, i))
    chunk = page[start:min(ends)]
    imgs = [hm.unescape(s) for s in re.findall(r'<img[^>]+(?:data-src|src)="([^"]+)"', chunk)]
    imgs = list(dict.fromkeys(s for s in imgs if "wp-content" in s))
    return strip_tags(chunk), imgs


def meta(page, prop):
    for pat in (
        r'<meta[^>]+(?:property|name)="%s"[^>]+content="([^"]+)"' % re.escape(prop),
        r'<meta[^>]+content="([^"]+)"[^>]+(?:property|name)="%s"' % re.escape(prop),
    ):
        m = re.search(pat, page)
        if m:
            return hm.unescape(m.group(1))
    return ""


def page_title(page):
    m = re.search(r"<title>([^<]+)</title>", page)
    t = hm.unescape(m.group(1)).strip() if m else ""
    return re.sub(r"\s*[-–|]\s*Albert's Auto Electrical.*$", "", t)


def slug_of(url):
    return url.rstrip("/").rsplit("/", 1)[-1]


def clean_leading(t, title):
    """Drop breadcrumb/byline preamble (theme prints 'Home / Title … admin … 0 comments')."""
    t = re.sub(r"^Home\s*/\s*", "", t)
    if t.startswith(title):
        t = t[len(title):].strip()
    m = re.search(r"\b\d+\s*comments\b", t[:300])
    if m:
        t = t[m.end():].strip()
    if t.startswith(title):
        t = t[len(title):].strip()
    return t.strip()


def scrape_blog(url):
    page = get(url)
    text, imgs = extract_content(page)
    title = page_title(page) or slug_of(url).replace("-", " ").title()
    text = clean_leading(text, title)
    img = meta(page, "og:image") or (imgs[0] if imgs else "")
    date = meta(page, "article:published_time") or ""
    m = re.search(r'<time[^>]+datetime="([^"]+)"', page)
    if not date and m:
        date = m.group(1)
    return {
        "slug": slug_of(url),
        "url": url,
        "title": title,
        "date": date,
        "image": img,
        "text": text,
        "imgs": imgs,
    }


def scrape_testimonial(url):
    page = get(url)
    text, imgs = extract_content(page)
    title = page_title(page)
    return {
        "slug": slug_of(url),
        "url": url,
        "title": title,
        "image": meta(page, "og:image"),
        "text": clean_leading(text, title),
    }


def scrape_gallery(url):
    page = get(url)
    text, imgs = extract_content(page)
    return {
        "slug": slug_of(url),
        "url": url,
        "title": page_title(page),
        "image": meta(page, "og:image") or (imgs[0] if imgs else ""),
        "text": text,
    }


def scrape_estimate(url):
    page = get(url)
    return {"slug": slug_of(url), "url": url, "title": page_title(page)}


def run(name, fn, urls, workers=10):
    out = []
    with cf.ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(fn, u): u for u in urls}
        for f in cf.as_completed(futs):
            u = futs[f]
            try:
                out.append(f.result())
            except Exception as e:  # noqa: BLE001
                print(f"FAIL {u}: {e}")
    out.sort(key=lambda d: d["slug"])
    with open(os.path.join(OUT, f"{name}.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f"{name}: {len(out)}/{len(urls)} scraped")


if __name__ == "__main__":
    blog_urls = [u for u in sitemap_locs("post-sitemap") if u.rstrip("/") != f"{BASE}/blog"]
    run("blog", scrape_blog, blog_urls)
    t_urls = sorted(set(sitemap_locs("testimonial-sitemap")) | set(sitemap_locs("car-testimonial-sitemap")))
    run("testimonials", scrape_testimonial, t_urls)
    g_urls = sitemap_locs("gallery-sitemap")
    run("gallery", scrape_gallery, g_urls)
    e_urls = sitemap_locs("service-estimate-sitemap")
    run("estimates", scrape_estimate, e_urls)
