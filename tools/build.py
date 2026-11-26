#!/usr/bin/env python3
"""Static site generator for the rebuilt Albert's Auto Electrical website.
Reproduces the ORIGINAL WordPress URL structure (about-us/, serve/<slug>/,
blog/<slug>/, testimonial/<slug>/, gallery/<slug>/, service-estimate/<slug>/…)
from data/*.json plus the hand-built core pages. Stdlib only."""
import html as hm
import json
import os
import posixpath
import re
import shutil
import urllib.parse
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SITE = "https://jimmybbk.github.io/alberts-auto-electrical"

MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def load(name):
    with open(os.path.join(ROOT, "data", name), encoding="utf-8") as fh:
        return json.load(fh)


BLOG = sorted(load("blog.json"), key=lambda b: (b.get("date") or ""), reverse=True)
TESTIMONIALS = load("testimonials.json")
GALLERY = load("gallery.json")
ESTIMATES = load("estimates.json")
try:
    IMAGES = load("images.json")
except FileNotFoundError:
    IMAGES = {}
try:
    INLINE_IMAGES = load("inline_images.json")
except FileNotFoundError:
    INLINE_IMAGES = {}

esc = hm.escape

# ---------------------------------------------------------------- links
def href(frm, to):
    """Relative href from route `frm` to directory route `to` ('' = home).

    Pages live at <frm>/index.html, so a browser resolves relative URLs
    against <frm> ITSELF — not dirname(<frm>). That is the base used here;
    getting this wrong makes every subpage link resolve one level too deep.
    """
    base = frm if frm else "."
    if to:
        return posixpath.relpath(to, base).replace("\\", "/") + "/"
    return posixpath.relpath(".", base).replace("\\", "/") + "/"


def depth(route):
    return 0 if not route else route.count("/") + 1


def pfx(route):
    return "../" * depth(route)


def asset(route, path):
    return pfx(route) + path


def img_local(kind, slug, fallback):
    local = IMAGES.get(f"{kind}:{slug}", "")
    return local or fallback


def fmt_date(iso):
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", iso or "")
    if not m:
        return ""
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if 1 <= mo <= 12:
        return f"{MONTHS[mo]} {d}, {y}"
    return iso[:10]


def paragraphs(text):
    sents = [s.strip() for s in re.split(r"(?<=[.!?\u201d])\s+", text.strip()) if s.strip()]
    paras, buf = [], []
    for s in sents:
        buf.append(s)
        if len(" ".join(buf)) > 230:
            paras.append(" ".join(buf))
            buf = []
    if buf:
        paras.append(" ".join(buf))
    return paras


def excerpt(text, n=150):
    t = text.strip()
    return (t[: n - 1].rsplit(" ", 1)[0] + "…") if len(t) > n else t


# ---------------------------------------------------------------- shared markup
ICON_PATHS = {
    "pin": '<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>',
    "phone": '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.3-3 19.5 19.5 0 0 1-6-6 19.8 19.8 0 0 1-3-8.4A2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 2 .7 2.9a2 2 0 0 1-.4 2.1L8.1 10a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.9.6 2.9.7a2 2 0 0 1 1.6 2z"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    "mail": '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-10 6L2 7"/>',
    "check": '<circle cx="12" cy="12" r="10"/><path d="m8 12 3 3 5-6"/>',
    "arrow": '<path d="M5 12h14M12 5l7 7-7 7"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "up": '<path d="m18 15-6-6-6 6"/>',
    "cart": '<circle cx="9" cy="21" r="1.6"/><circle cx="19" cy="21" r="1.6"/><path d="M2 3h3l2.6 12.4a2 2 0 0 0 2 1.6h8.9a2 2 0 0 0 2-1.6L22 7H6"/>',
}


def icon(name):
    return f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">{ICON_PATHS[name]}</svg>'


def topbar(route):
    a = lambda p: asset(route, p)
    return f'''
  <div class="topbar">
    <div class="container topbar-inner">
      <ul class="topbar-info">
        <li>{icon("pin")} 3/41 O'Connell St, Smithfield NSW 2164</li>
        <li>{icon("phone")} <a href="tel:+61421667118">0421 667 118</a></li>
        <li>{icon("clock")} Mon–Fri 9am–5pm · Sat by appointment</li>
      </ul>
      <div class="topbar-social">
        <a href="https://www.facebook.com/profile.php?id=100057614381716" aria-label="Facebook" rel="noopener" target="_blank"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M13.5 21v-8h2.7l.4-3.1h-3.1V7.9c0-.9.3-1.5 1.6-1.5h1.6V3.6c-.3 0-1.3-.1-2.4-.1-2.4 0-4 1.4-4 4.1v2.3H7.5V13h2.8v8h3.2z"/></svg></a>
        <a href="https://www.instagram.com/albertsautoelectrical/" aria-label="Instagram" rel="noopener" target="_blank"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.2" cy="6.8" r="1" fill="currentColor" stroke="none"/></svg></a>
      </div>
    </div>
  </div>'''


NAV = [
    ("home", "", "Home", None),
    ("about", "about-us", "About Us", None),
    ("services", "serve", "Services", [
        ("serve/performance-cars", "Performance Cars"),
        ("serve/classic-cars", "Classic Cars"),
        ("serve/cars-trucks-and-four-wheel-drives", "Cars, Trucks &amp; 4WDs"),
        ("serve/installation-of-a-c-units-air-con-service", "Air Conditioning"),
        ("serve/tires-wheels", "Engine Services"),
    ]),
    ("blog", "blog", "Blog", None),
    ("gallery", "gallery", "Gallery", None),
    ("testimonials", "testimonial", "Testimonials", None),
    ("locations", "locations", "Locations", None),
    ("contact", "contact-us", "Contact Us", None),
]


def nav(route, active):
    items = []
    for key, to, label, subs in NAV:
        h = href(route, to)
        classes = " ".join(c for c in (["active"] if key == active else []) + (["has-sub"] if subs else []) if c)
        cls = f' class="{classes}"' if classes else ""
        if subs:
            sub = "".join(
                f'<li><a href="{href(route, s_to)}">{s_label}</a></li>' for s_to, s_label in subs
            )
            items.append(
                f'<li{cls}><a class="parent-link" href="{h}">{label}</a>'
                f'<ul class="sub-menu">{sub}</ul></li>'
            )
        else:
            items.append(f'<li{cls}><a href="{h}">{label}</a></li>')
    return "\n".join(items)


def header(route, active):
    a = lambda p: asset(route, p)
    return f'''
  <header class="site-header">
    <div class="container header-inner">
      <a class="brand" href="{href(route, '')}">
        <img src="{a('assets/img/logo.png')}" alt="Albert's Auto Electrical logo">
        <span class="brand-name">Albert's<em>Auto Electrical</em></span>
      </a>
      <nav class="main-nav" aria-label="Main navigation">
        <ul>
{nav(route, active)}
        </ul>
      </nav>
      <a class="btn btn-solid header-cta" href="tel:+61421667118">
        {icon("phone")} 0421 667 118
      </a>
      <button class="nav-toggle" aria-label="Toggle menu" aria-expanded="false"><span></span></button>
    </div>
  </header>'''


def footer(route):
    a = lambda p: asset(route, p)
    s_items = "".join(
        f'<li><a href="{href(route, s_to)}">{s_label}</a></li>'
        for s_to, s_label in NAV[2][3]
    )
    return f'''
  <footer class="site-footer">
    <div class="container footer-grid">
      <div>
        <a class="brand" href="{href(route, '')}">
          <img src="{a('assets/img/logo.png')}" alt="Albert's Auto Electrical logo">
          <span class="brand-name">Albert's<em>Auto Electrical</em></span>
        </a>
        <p class="f-desc">Specialist auto electrical services for performance cars, classics, 4WDs, trucks and everything in between — proudly serving NSW for over 20 years.</p>
      </div>
      <div>
        <h4>Quick Links</h4>
        <div class="f-links">
          <a href="{href(route, '')}">Home</a>
          <a href="{href(route, 'about-us')}">About Us</a>
          <a href="{href(route, 'blog')}">Blog</a>
          <a href="{href(route, 'gallery')}">Gallery</a>
          <a href="{href(route, 'testimonial')}">Testimonials</a>
          <a href="{href(route, 'faq')}">FAQ</a>
          <a href="{href(route, 'pricing-coupons')}">Pricing &amp; Coupons</a>
          <a href="{href(route, 'locations')}">Locations</a>
          <a href="{href(route, 'contact-us')}">Contact Us</a>
        </div>
      </div>
      <div>
        <h4>Services</h4>
        <div class="f-links">
{s_items}
        </div>
      </div>
      <div>
        <h4>Get In Touch</h4>
        <ul class="f-contact">
          <li>{icon("pin")} 3/41 O'Connell Street, Smithfield NSW 2164</li>
          <li>{icon("phone")} <a href="tel:+61421667118">0421 667 118</a></li>
          <li>{icon("mail")} <a href="mailto:albert@albertsautoelectrical.com.au">albert@albertsautoelectrical.com.au</a></li>
          <li>{icon("clock")} Mon–Fri 9:00–5:00 · Sat by appointment · Sun closed</li>
        </ul>
      </div>
    </div>
    <div class="container footer-bottom">
      <span>© <span data-year>2026</span> Albert's Auto Electrical. All rights reserved.</span>
      <div class="socials">
        <a href="https://www.facebook.com/profile.php?id=100057614381716" aria-label="Facebook" rel="noopener" target="_blank"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M13.5 21v-8h2.7l.4-3.1h-3.1V7.9c0-.9.3-1.5 1.6-1.5h1.6V3.6c-.3 0-1.3-.1-2.4-.1-2.4 0-4 1.4-4 4.1v2.3H7.5V13h2.8v8h3.2z"/></svg></a>
        <a href="https://www.instagram.com/albertsautoelectrical/" aria-label="Instagram" rel="noopener" target="_blank"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.2" cy="6.8" r="1" fill="currentColor" stroke="none"/></svg></a>
      </div>
    </div>
  </footer>

  <a class="float-call" href="tel:+61421667118">{icon("phone")} Call Albert</a>
  <button class="to-top" aria-label="Back to top">{icon("up")}</button>'''


def page_shell(route, title, desc, active, main_html, og_image="assets/img/hero-car.png"):
    a = lambda p: asset(route, p)
    canonical = f"{SITE}/{route}/" if route else f"{SITE}/"
    og_abs = og_image if og_image.startswith("http") else SITE + "/" + og_image
    return f'''<!DOCTYPE html>
<html lang="en-AU">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(desc)}">
  <link rel="canonical" href="{canonical}">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(desc)}">
  <meta property="og:image" content="{esc(og_abs)}">
  <link rel="icon" type="image/png" href="{a('assets/img/logo.png')}">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Sora:wght@500;600;700;800&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="{a('assets/css/styles.css')}">
</head>
<body>
  <a class="skip-link" href="#main">Skip to content</a>
{topbar(route)}
{header(route, active)}

  <main id="main">
{main_html}
  </main>
{footer(route)}

  <script src="{a('assets/js/main.js')}"></script>
</body>
</html>'''


def crumbs(route, label):
    return f'''<div class="crumbs"><a href="{href(route, '')}">Home</a> <span>/</span> {label}</div>'''


def page_hero(route, label, h1, lead):
    return f'''
    <section class="page-hero">
      <div class="container">
        {crumbs(route, label)}
        <h1>{h1}</h1>
        <p>{lead}</p>
      </div>
    </section>'''


def cta_band(route, h2, p, ghost_label="Book Online", ghost_to="contact-us", solid_label="0421 667 118"):
    return f'''
    <section class="section tight" style="padding-top:0;">
      <div class="container">
        <div class="cta-band reveal">
          <div>
            <h2>{h2}</h2>
            <p>{p}</p>
          </div>
          <div class="cta-actions">
            <a class="btn btn-solid" href="tel:+61421667118">{icon("phone")} {solid_label}</a>
            <a class="btn btn-ghost" href="{href(route, ghost_to)}">{ghost_label}</a>
          </div>
        </div>
      </div>
    </section>'''


def make_redirect_stub(target, label):
    return ('<!DOCTYPE html>\n<html lang="en-AU"><head>\n'
            '<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            f'<title>Redirecting to {label} | Albert\'s Auto Electrical</title>\n'
            '<meta name="robots" content="noindex">\n'
            f'<meta http-equiv="refresh" content="0; url={target}">\n'
            f'<script>location.replace("{target}");</script>\n'
            '<style>body{font-family:system-ui,sans-serif;display:grid;place-items:center;'
            'min-height:100vh;margin:0;background:#0b0f16;color:#e9eef5;text-align:center}'
            'a{color:#2e9bff}</style>\n</head><body><div><p>This page has moved.</p>'
            f'<p><a href="{target}">Continue to {label} &rarr;</a></p></div></body></html>')


def neighbor(items, idx):
    prev_i = items[idx - 1] if idx > 0 else items[-1]
    next_i = items[(idx + 1) % len(items)]
    return prev_i, next_i


def prev_next(route, base_route, items, idx, label_fn):
    p, n = neighbor(items, idx)

    def tgt(item):
        # base_route "" means items sit at the site root (blog posts)
        return (base_route + "/" + item["slug"]) if base_route else item["slug"]

    return f'''
        <div class="pn-nav">
          <a class="pn-btn" href="{href(route, tgt(p))}">← {esc(label_fn(p))}</a>
          <a class="pn-btn" href="{href(route, tgt(n))}">{esc(label_fn(n))} →</a>
        </div>'''


# ---------------------------------------------------------------- core pages (extracted)
def extract_main(fname):
    fname = os.path.join("tools", "src", fname)
    with open(os.path.join(ROOT, fname), encoding="utf-8") as fh:
        src = fh.read()
    m = re.search(r"<main id=\"main\">\s*(.*?)\s*</main>", src, re.S)
    return m.group(1) if m else ""


LINK_MAP = {
    "index.html": "",
    "about.html": "about-us",
    "services.html#performance": "serve/performance-cars",
    "services.html#classic": "serve/classic-cars",
    "services.html#everyday": "serve/cars-trucks-and-four-wheel-drives",
    "services.html#aircon": "serve/installation-of-a-c-units-air-con-service",
    "services.html": "serve",
    "gallery.html": "gallery",
    "testimonials.html": "testimonial",
    "locations.html": "locations",
    "contact.html": "contact-us",
    "faq.html": "faq",
    "pricing-coupons.html": "pricing-coupons",
    "blog.html": "blog",
}


def rewrite(route, content):
    def link_repl(m):
        to = LINK_MAP.get(m.group(1))
        return f'href="{href(route, to)}"' if to is not None else m.group(0)

    content = re.sub(
        r'href="((?:index|about|services|gallery|testimonials|locations|contact|faq|pricing-coupons|blog)\.html(?:#[a-z]+)?)"',
        link_repl, content)
    p = pfx(route)
    content = re.sub(r'((?:src|href|data-full)=")assets/', r"\1" + p + "assets/", content)
    return content


def core_page(route, fname, title, desc, active, og_image="assets/img/hero-car.png"):
    return page_shell(route, title, desc, active, rewrite(route, extract_main(fname)), og_image)


# ---------------------------------------------------------------- new: blog
def post_card(route, b):
    img = img_local("blog", b["slug"], b["image"])
    h = href(route, b["slug"])
    d = fmt_date(b.get("date"))
    return f'''
        <article class="post-card card reveal">
          <a class="post-thumb" href="{h}" tabindex="-1" aria-hidden="true"><img src="{asset(route, img) if not img.startswith('http') else img}" alt="{esc(b['title'])}" loading="lazy"></a>
          <div class="post-teaser">
            <span class="post-date">{esc(d)}</span>
            <h3><a href="{h}">{esc(b['title'])}</a></h3>
            <p>{esc(excerpt(b.get("text", "")))}</p>
            <a class="card-link" href="{h}">Read more {icon("arrow")}</a>
          </div>
        </article>'''


def build_blog_archive():
    route = "blog"
    cards = "\n".join(post_card(route, b) for b in BLOG)
    featured = post_card(route, BLOG[0])
    main = f'''
    <section class="page-hero">
      <div class="container">
        {crumbs(route, "Blog")}
        <h1>From the workshop floor</h1>
        <p>Project builds, restorations, fixes and updates — {len(BLOG)} stories from Albert's bench, straight from our original blog.</p>
        <div class="hero-actions">
          <a class="btn btn-solid" href="tel:+61421667118">{icon("phone")} 0421 667 118</a>
          <a class="btn btn-ghost" href="{href(route, 'contact-us')}">Book Your Car In</a>
        </div>
      </div>
    </section>

    <section class="section">
      <div class="container">
        <div class="blog-tools reveal">
          <input type="search" data-blog-search placeholder="Search {len(BLOG)} projects — try “Skyline”, “rewire”, “aircon”…" aria-label="Search blog posts">
          <span class="blog-count" data-blog-count></span>
        </div>
        <div class="grid-3" data-blog-grid>
{cards}
        </div>
        <p class="no-results" data-blog-empty hidden>No projects match that search — try another word, or call us on 0421 667 118.</p>
      </div>
    </section>

    {cta_band(route, "Your car could be our next project", "See something like your build? Book it in — every car gets the same attention to detail.", "Book a Service")}'''
    return page_shell(route, "Blog | Albert's Auto Electrical — Workshop Projects & Updates",
                      "Project builds, restorations, wiring jobs and fixes from the Albert's Auto Electrical workshop in Smithfield NSW.",
                      "blog", main,
                      og_image=img_local("blog", BLOG[0]["slug"], BLOG[0]["image"]))


def build_blog_post(b, idx):
    route = b["slug"]
    img = img_local("blog", b["slug"], b["image"])
    img_tag = img if img.startswith("http") else asset(route, img)
    paras = paragraphs(b.get("text", "")) or ["This project speaks for itself — see the photos below, or call Albert on 0421 667 118 to talk about your build."]
    body = "\n".join(f"<p>{esc(p)}</p>" for p in paras)
    # inline figures: dedupe size variants of the same base photo, local only
    seen_bases = set()
    extra = []
    for i in b.get("imgs") or []:
        base = re.sub(r"-\d+x\d+(?=\.[a-z]+$)", "", i)
        if base in seen_bases:
            continue
        local = INLINE_IMAGES.get(i, "")
        if not local:
            continue  # never hotlink; skip if the download failed
        seen_bases.add(base)
        extra.append(local)
        if len(extra) >= 4:
            break
    figs = "".join(
        f'<figure class="post-fig"><img src="{asset(route, i)}" alt="{esc(b["title"])}" loading="lazy"></figure>'
        for i in extra)
    d = fmt_date(b.get("date"))
    main = f'''
    <section class="page-hero">
      <div class="container">
        {crumbs(route, '<a href="' + href(route, 'blog') + '">Blog</a>')}
        <h1 style="max-width:30ch;">{esc(b['title'])}</h1>
        <p>{esc(d)} · Albert's Auto Electrical, Smithfield NSW</p>
      </div>
    </section>

    <section class="section">
      <div class="container post-wrap">
        <figure class="post-fig main-fig reveal"><img src="{esc(img_tag)}" alt="{esc(b['title'])}"></figure>
        <div class="prose reveal">
{body}
        </div>
        {f'<div class="post-gallery reveal">{figs}</div>' if figs else ''}
        <div class="blog-cta reveal">
          <p>Want a result like this on your car?</p>
          <div class="cta-actions">
            <a class="btn btn-solid" href="tel:+61421667118">{icon("phone")} 0421 667 118</a>
            <a class="btn btn-ghost" href="{href(route, 'contact-us')}">Book a Service</a>
          </div>
        </div>
{prev_next(route, "", BLOG, idx, lambda x: x['title'])}
      </div>
    </section>'''
    desc = excerpt(b.get("text", ""), 155) or f"Workshop project at Albert's Auto Electrical — {b['title']}."
    return page_shell(route, f"{b['title']} | Albert's Auto Electrical", desc, "blog", main,
                      og_image=img if img.startswith("http") else SITE + "/" + img)


# ---------------------------------------------------------------- new: testimonials
def review_parts(text):
    services = positive = ""
    body = text
    m = re.search(r"Services:\s*(.*?)(?:Positive:|$)", text, re.S)
    if m:
        services = m.group(1).strip().rstrip(",")
    m = re.search(r"Positive:\s*(.*?)(?:$)", text, re.S)
    if m:
        positive = m.group(1).strip()
    if services or positive:
        first = re.search(r"Services:", text)
        body = text[: first.start()].strip() if first else text
    return services, positive, body


def build_testimonial_item(t, idx):
    route = "testimonial/" + t["slug"]
    services, positive, body = review_parts(t.get("text", ""))
    tags = ""
    if services:
        chips = "".join(f'<span class="chip">{esc(s.strip())}</span>' for s in services.split(",") if s.strip())
        tags += f'<div class="chips" style="margin-top:18px;">{chips}</div>'
    if positive:
        pl = ", ".join(p.strip().title() for p in positive.split(",") if p.strip())
        tags += f'<p class="t-positive"><strong>Rated for:</strong> {esc(pl)}</p>'
    name = t["title"] or t["slug"].replace("-", " ").title()
    main = f'''
    <section class="page-hero">
      <div class="container">
        {crumbs(route, '<a href="' + href(route, 'testimonial') + '">Testimonials</a>')}
        <h1>{esc(name)}</h1>
        <p>A verified 5-star Google review from an Albert's Auto Electrical customer.</p>
      </div>
    </section>

    <section class="section">
      <div class="container" style="max-width:860px;">
        <article class="t-card reveal" style="padding:38px;">
          <div class="stars" aria-label="5 star rating">{'<svg viewBox="0 0 24 24" fill="currentColor"><path d="m12 2 3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z"/></svg>' * 5}</div>
          <blockquote style="font-size:17.5px;">{esc(body) if body else "5-star Google review — thank you for trusting Albert's Auto Electrical with your vehicle."}</blockquote>
          {tags}
          <div class="t-who"><div class="t-avatar">{esc(name[0].upper())}</div><div><div class="nm">{esc(name)}</div><div class="src">Google Review</div></div></div>
        </article>
{prev_next(route, "testimonial", TESTIMONIALS, idx, lambda x: x['title'] or x['slug'])}
        <div style="text-align:center; margin-top:36px;">
          <a class="btn btn-outline" href="{href(route, 'testimonial')}">All Testimonials</a>
        </div>
      </div>
    </section>

    {cta_band(route, "Become our next 5-star review", "Book your car in and experience the service everyone's talking about.")}'''
    desc = excerpt(body, 150) if body else f"5-star Google review from {name}."
    return page_shell(route, f"Review by {name} | Albert's Auto Electrical", desc, "testimonials", main)


def build_testimonial_archive_extras(route):
    cards = []
    for t in TESTIMONIALS:
        services, positive, body = review_parts(t.get("text", ""))
        name = t["title"] or t["slug"].replace("-", " ").title()
        h = href(route, "testimonial/" + t["slug"])
        cards.append(f'''
          <a class="card reveal t-mini" href="{h}">
            <div class="stars">{'<svg viewBox="0 0 24 24" fill="currentColor"><path d="m12 2 3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z"/></svg>' * 5}</div>
            <p>{esc(excerpt(body or "5-star Google review.", 120))}</p>
            <div class="t-who"><div class="t-avatar">{esc(name[0].upper())}</div><div><div class="nm">{esc(name)}</div><div class="src">Read the full review {icon("arrow")}</div></div></div>
          </a>''')
    return f'''
    <section class="section" style="background:#fff; border-top:1px solid var(--line);">
      <div class="container">
        <div class="section-head center reveal">
          <span class="kicker">Review Archive</span>
          <h2>Every review, on the record</h2>
          <p>{len(TESTIMONIALS)} verified Google reviews — click any to read the full write-up.</p>
        </div>
        <div class="grid-3 t-mini-grid">
{''.join(cards)}
        </div>
      </div>
    </section>'''


# ---------------------------------------------------------------- new: gallery
def build_gallery_archive(route):
    tiles = []
    shown = set()
    for g in GALLERY:
        base = posixpath.basename(urllib_unquote(g.get("image") or ""))
        if base in shown:
            continue
        shown.add(base)
        img = img_local("gallery", g["slug"], g.get("image"))
        src = img if img.startswith("http") else asset(route, img)
        h = href(route, "gallery/" + g["slug"])
        name = esc(g.get("title") or g["slug"].replace("-", " ").title())
        tiles.append(f'''
          <a class="a-tile reveal" href="{h}">
            <img src="{src}" alt="{name}" loading="lazy">
            <span class="a-cap"><span class="s">Gallery</span><span class="t">{name}</span></span>
          </a>''')
    return f'''
    <section class="section" style="padding-top:64px;">
      <div class="container">
        <div class="section-head center reveal">
          <span class="kicker">Project Archive</span>
          <h2>Every photo from the original gallery</h2>
          <p>{len(tiles)} shots from the workshop — click any for its own page.</p>
        </div>
        <div class="a-grid">
{''.join(tiles)}
        </div>
      </div>
    </section>'''


def urllib_unquote(s):
    import urllib.parse
    return urllib.parse.unquote(s or "")


def build_gallery_item(g, idx):
    route = "gallery/" + g["slug"]
    img = img_local("gallery", g["slug"], g.get("image"))
    src = img if img.startswith("http") else asset(route, img)
    name = g.get("title") or g["slug"].replace("-", " ").title()
    main = f'''
    <section class="page-hero">
      <div class="container">
        {crumbs(route, '<a href="' + href(route, 'gallery') + '">Gallery</a>')}
        <h1>{esc(name)}</h1>
        <p>From the Albert's Auto Electrical project gallery.</p>
      </div>
    </section>

    <section class="section">
      <div class="container" style="max-width:900px;">
        <figure class="post-fig main-fig reveal"><img src="{src}" alt="{esc(name)}"></figure>
        <div class="blog-cta reveal">
          <p>Want your car on this wall?</p>
          <div class="cta-actions">
            <a class="btn btn-solid" href="tel:+61421667118">{icon("phone")} 0421 667 118</a>
            <a class="btn btn-ghost" href="{href(route, 'contact-us')}">Book a Service</a>
          </div>
        </div>
{prev_next(route, "gallery", GALLERY, idx, lambda x: x.get('title') or x['slug'])}
      </div>
    </section>'''
    return page_shell(route, f"{name} | Albert's Auto Electrical Gallery",
                      f"{name} — a project from the Albert's Auto Electrical workshop in Smithfield NSW.",
                      "gallery", main, og_image=img if img.startswith("http") else SITE + "/" + img)


# ---------------------------------------------------------------- new: service detail pages
def service_detail(route, kicker, h1, lead, img, badge, checks, brands=None, extra=""):
    check_html = "".join(f'<li>{icon("check")} <span>{c}</span></li>' for c in checks)
    brand_html = ""
    if brands:
        imgs = "".join(f'<img src="{asset(route, "assets/img/logo-" + b.lower() + ".png")}" alt="{b}">' for b in brands)
        brand_html = f'<div class="brand-strip"><span class="bs-label">Engine management brands we work with</span>{imgs}</div>'
    return f'''
    <section class="page-hero">
      <div class="container">
        {crumbs(route, '<a href="' + href(route, 'serve') + '">Services</a>')}
        <h1>{h1}</h1>
        <p>{lead}</p>
        <div class="hero-actions">
          <a class="btn btn-solid" href="tel:+61421667118">{icon("phone")} Get a Quote</a>
          <a class="btn btn-ghost" href="{href(route, 'contact-us')}">Book This Service</a>
        </div>
      </div>
    </section>

    <section class="service-band">
      <div class="container service-row">
        <div class="service-copy reveal">
          <span class="kicker">{kicker}</span>
          <h3>What we do</h3>
          {extra}
          <ul class="check-list">
{check_html}
          </ul>
          {brand_html}
          <div style="margin-top:28px;"><a class="card-link" href="{href(route, 'serve')}">All services {icon("arrow")}</a></div>
        </div>
        <div class="service-media reveal">
          <img src="{asset(route, img)}" alt="{esc(h1)}">
          <div class="media-badge">{icon("check")} {badge}</div>
        </div>
      </div>
    </section>

    {cta_band(route, "Get it done once, done right", "Tell us what you need — you'll get honest advice and a fair-price estimate.")}'''


def build_serve_detail(slug):
    route = "serve/" + slug
    if slug == "performance-cars":
        content = service_detail(
            route, "Service 01", "Performance Cars",
            "High-quality auto electrical services for performance cars — from street builds to full drag and circuit machines, wired to survive heat, vibration and 7,000 rpm.",
            "assets/img/workshop-wide.jpg", "Race-proven wiring",
            ["ECU supply, fitting &amp; wiring — plug-in and wire-in",
             "Engine conversions &amp; half-cut rewiring",
             "Custom and piggyback ECUs &amp; engine management upgrades",
             "Performance wiring, body &amp; engine harnesses",
             "Gauges, datalogging &amp; engine protection setups"],
            brands=["Haltech", "Fueltech", "Microtech"])
        desc = "Performance car auto electrical: ECU supply and fitting, engine management upgrades and motorsport-grade wiring in Smithfield NSW."
    elif slug == "classic-cars":
        content = service_detail(
            route, "Service 02", "Classic Cars",
            "Reliable, trustworthy auto electrical work for classics — every rewire planned, labelled and routed the way the factory wish it had.",
            "assets/img/gallery-1.jpg", "Factory-neat looms",
            ["Complete full rewires — body, engine &amp; lighting circuits",
             "Repair &amp; restoration of tired or butchered wiring",
             "Custom wiring harnesses built in-house",
             "Gauge, instrument &amp; dashboard rewiring",
             "Period-correct finishes with modern reliability"])
        desc = "Classic car rewires and custom wiring harnesses — period-correct work with modern reliability, from Albert's Auto Electrical."
    elif slug == "cars-trucks-and-four-wheel-drives":
        content = service_detail(
            route, "Service 03", "Cars, Trucks &amp; Four-Wheel Drives",
            "Reliable auto electrical services that solve everyday problems — and proper 4WD and truck accessories fitted once, fitted right.",
            "assets/img/fourby.jpg", "Tour-ready 4WD fit-outs",
            ["Batteries, alternators &amp; starter motors",
             "Diagnostics &amp; engine light faults",
             "Dual battery systems &amp; DC-DC chargers",
             "Driving lights, spotties, light bars &amp; truck lighting",
             "Electric brake controllers &amp; trailer plug wiring",
             "UHF / CB radios, reversing cameras &amp; headlights/taillights"])
        desc = "Auto electrical for cars, trucks and 4WDs: batteries, diagnostics, dual battery systems, lighting, brake controllers and more."
    elif slug == "installation-of-a-c-units-air-con-service":
        content = service_detail(
            route, "Service 04", "Installation of A/C Units &amp; Air-Con Service",
            "Keep your cool on the road — expert vehicle air-conditioning installation, servicing and repair for cars, 4WDs and trucks.",
            "assets/img/ac-install.jpg", "Ice-cold all summer",
            ["A/C system installation &amp; retrofits",
             "Air-con regas, leak testing &amp; diagnosis",
             "Compressor, condenser &amp; blower repairs",
             "Cabin air &amp; heating faults sorted"])
        desc = "Vehicle air-conditioning installation, service and repair in Smithfield NSW — stay cool with Albert's Auto Electrical."
    else:  # tires-wheels -> Engine Services (original title/content)
        content = service_detail(
            route, "Service 05", "Engine Services",
            "One of the simplest, most effective and inexpensive ways to protect the life of your car — especially its engine — is regular servicing. An oil change can really change your mood. And it will definitely change your oil.",
            "assets/img/workshop-wide.jpg", "Preventative maintenance",
            ["Oil changes &amp; filter replacements",
             "Preventative maintenance schedules",
             "30+ common vehicle repairs and growing",
             "Diagnostics before small problems become big ones"])
        desc = "Engine services and preventative maintenance at Albert's Auto Electrical — oil changes, filters and the checks that prevent breakdowns."
    return page_shell(route, page_title_for(slug), desc, "services", content)


def page_title_for(slug):
    names = {
        "performance-cars": "Performance Cars",
        "classic-cars": "Classic Cars",
        "cars-trucks-and-four-wheel-drives": "Cars, Trucks & Four-Wheel Drives",
        "installation-of-a-c-units-air-con-service": "Installation of A/C Units (Air Con Service)",
        "tires-wheels": "Engine Services",
    }
    return f"{names[slug]} | Services — Albert's Auto Electrical"


# ---------------------------------------------------------------- new: FAQ + pricing
FAQ_ITEMS = [
    ("How long will it take to complete the repairs?", "We try to complete most repairs the same day. If this is not possible, we will provide you with special transportation arrangements."),
    ("How much will it cost?", "We try to give a fair-price estimate before work begins — tell us your vehicle and symptoms, and you'll know where you stand before we turn a spanner."),
    ("Is there a warranty on the repairs?", "Albert's Auto Electrical stands behind its workmanship — quality repairs backed by our guarantee. Call us to discuss the specifics of your job."),
    ("Do I have an option to pickup and deliver my vehicle?", "Yes — arrangements can be made for pickup and delivery of your vehicle. Mention it when you book."),
    ("What types of vehicles do you service?", "Performance cars, classic cars, daily drivers, 4WDs, trucks and light commercials — all makes and models."),
    ("What forms of payment do you accept?", "Call us on 0421 667 118 to confirm payment options for your job."),
    ("How often should I get my car serviced?", "Follow your manufacturer's logbook intervals — and if something electrical is acting up between services, don't wait for it to get worse."),
    ("My car's battery light just came on — what should I do?", "The battery or charging system needs attention. Have it checked promptly — a dying alternator can leave you stranded."),
    ("Can you install accessories like driving lights or a UHF radio?", "Absolutely — driving lights, spotties, light bars, UHF/CB radios, dual battery systems, brake controllers and more."),
    ("Do you work on race cars and performance builds?", "Yes — ECU supply and fitting, full rewires, engine conversions and engine management from brands like Haltech, FuelTech and MicroTech."),
    ("Do you service air conditioning?", "Yes — A/C installation, regas, leak testing and repairs for cars, 4WDs and trucks."),
    ("How do I book my car in?", "Call 0421 667 118, email albert@albertsautoelectrical.com.au, or use the booking form on our contact page. Monday to Friday 9am–5pm, Saturdays by appointment."),
]


def build_faq():
    route = "faq"
    items = "".join(f'''
          <div class="acc-item">
            <button class="acc-q" aria-expanded="false">{esc(q)}{icon("plus")}</button>
            <div class="acc-a"><p>{esc(a)}</p></div>
          </div>''' for q, a in FAQ_ITEMS)
    main = page_hero(route, "FAQ", "Frequently asked questions",
                     "The questions we hear most at the counter — answered straight. Anything else, call Albert on 0421 667 118.") + f'''

    <section class="section">
      <div class="container">
        <div class="accordion reveal">
{items}
        </div>
        <div style="text-align:center; margin-top:44px;">
          <p style="color:var(--text-soft);">Still stuck? <a href="{href(route, 'contact-us')}" style="font-weight:700;">Ask us directly</a> — real advice, no charge.</p>
        </div>
      </div>
    </section>

    {cta_band(route, "Have a car repair question?", "Get your automotive questions answered by a real auto electrician — not a phone menu.")}'''
    return page_shell(route, "FAQ | Albert's Auto Electrical",
                      "Answers to common questions about repairs, pricing, bookings, warranties and servicing at Albert's Auto Electrical, Smithfield NSW.",
                      "contact", main)


def build_pricing():
    route = "pricing-coupons"
    coupons = [
        ("$10 OFF", "Repairs!", "New Customer Coupon", "Present this coupon and receive $10 off any service."),
        ("$15 OFF", "Maintenance!", "Standard Oil Change", "Present this coupon and receive $15 off a standard oil change."),
        ("$25 OFF", "Brake Service!", "Front or Rear Brake Pads", "Present this coupon and receive $25 off front or rear brake pads."),
    ]
    coupon_html = "".join(f'''
          <article class="coupon-card reveal">
            <div class="coupon-value">{v}</div>
            <div class="coupon-what">{w}</div>
            <div class="coupon-name">{n}</div>
            <p>{d}</p>
            <span class="coupon-exp">Archived offer — expired 2019</span>
          </article>''' for v, w, n, d in coupons)
    rows = "".join(f'''
            <tr><td>{s}</td><td>{p}</td></tr>''' for s, p in [
        ("Preventative Maintenance", "From $99"),
        ("Electrical Diagnostics", "From $60"),
        ("Battery Replacement", "From $150 fitted"),
        ("Alternator / Starter Repairs", "Quote on inspection"),
        ("Full Custom Rewire", "Quote per project"),
        ("Air-Con Service / Regas", "From $150"),
        ("4WD Accessory Fit-outs", "Quote per build"),
    ])
    main = page_hero(route, "Pricing & Coupons", "Fair prices, upfront quotes",
                     "No surprises on the invoice — you'll know the price before we start. Below: the coupon offers and guide prices carried over from the original site.") + f'''

    <section class="section">
      <div class="container">
        <div class="grid-3">
{coupon_html}
        </div>
        <p class="reveal" style="text-align:center; color:var(--text-soft); margin-top:18px; font-size:14px;">These coupons are archived from the original site (expired November 2019). For current specials, call <a href="tel:+61421667118"><strong>0421 667 118</strong></a>.</p>

        <div class="section-head center reveal" style="margin-top:72px;">
          <span class="kicker">Guide Prices</span>
          <h2>What things cost</h2>
          <p>Indicative starting prices — your exact quote depends on the vehicle and the job. Always confirmed before work begins.</p>
        </div>
        <div class="price-wrap reveal">
          <table class="price-table">
{rows}
          </table>
        </div>
      </div>
    </section>

    {cta_band(route, "Get your exact price", "One call is all it takes — describe the job and get a straight answer.")}'''
    return page_shell(route, "Pricing & Coupons | Albert's Auto Electrical",
                      "Fair-price estimates and archived coupon offers from Albert's Auto Electrical, Smithfield NSW.",
                      "contact", main)


# ---------------------------------------------------------------- shop placeholders
def build_shop_notice(route, title, heading, blurb):
    main = page_hero(route, title, heading, blurb) + f'''

    <section class="section">
      <div class="container" style="text-align:center; max-width:640px;">
        <div class="card reveal" style="padding:48px 40px;">
          <div class="icon" style="margin-inline:auto;"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="9" cy="21" r="1.6"/><circle cx="19" cy="21" r="1.6"/><path d="M2 3h3l2.6 12.4a2 2 0 0 0 2 1.6h8.9a2 2 0 0 0 2-1.6L22 7H6"/></svg></div>
          <h3>Nothing on the shelf just yet</h3>
          <p style="color:var(--text-soft); margin-top:10px;">The original site's store only ever stocked WooCommerce demo samples — we've left the clutter out. Everything Albert offers is a service, and it starts with a phone call.</p>
          <div style="display:flex; gap:14px; justify-content:center; margin-top:26px; flex-wrap:wrap;">
            <a class="btn btn-solid" href="tel:+61421667118">{icon("phone")} 0421 667 118</a>
            <a class="btn btn-outline" href="{href(route, 'serve')}">Browse Services</a>
          </div>
        </div>
      </div>
    </section>'''
    return page_shell(route, f"{title} | Albert's Auto Electrical",
                      f"{blurb} Albert's Auto Electrical is a service workshop — call 0421 667 118.",
                      "", main)


# ---------------------------------------------------------------- estimates
def build_estimate(e, idx):
    route = "service-estimate/" + e["slug"]
    name = e.get("title") or e["slug"].replace("-", " ").title()
    main = page_hero(route, "Estimate", name,
                     f"Fair-price estimates for {name.lower()} — confirmed before any work begins.") + f'''

    <section class="section">
      <div class="container" style="max-width:760px;">
        <div class="card reveal" style="padding:40px;">
          <h3 style="font-size:22px;">How your estimate works</h3>
          <ul class="check-list" style="margin-top:20px;">
            <li>{icon("check")} <span><strong>Tell us the symptom</strong> — by phone, email or the booking form. Photos help.</span></li>
            <li>{icon("check")} <span><strong>We inspect and diagnose</strong> — so you're paying for the real fix, not a guess.</span></li>
            <li>{icon("check")} <span><strong>You get a fair-price quote</strong> — before any work begins. No surprises.</span></li>
          </ul>
          <div style="display:flex; gap:14px; margin-top:28px; flex-wrap:wrap;">
            <a class="btn btn-solid" href="tel:+61421667118">{icon("phone")} Call 0421 667 118</a>
            <a class="btn btn-outline" href="{href(route, 'contact-us')}">Request Estimate Online</a>
          </div>
        </div>
{prev_next(route, "service-estimate", ESTIMATES, idx, lambda x: x.get('title') or x['slug'])}
        <div style="text-align:center; margin-top:30px;"><a class="card-link" href="{href(route, 'serve')}">Browse all services {icon("arrow")}</a></div>
      </div>
    </section>'''
    return page_shell(route, f"{name} — Estimate | Albert's Auto Electrical",
                      f"Get a fair-price estimate for {name.lower()} from Albert's Auto Electrical, Smithfield NSW. Call 0421 667 118.",
                      "services", main)


# ---------------------------------------------------------------- 404
def build_404():
    """Self-contained: GitHub Pages serves 404.html at arbitrary URL paths,
    so every reference must be absolute — relative links/assets would break."""
    return f'''<!DOCTYPE html>
<html lang="en-AU">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>404 — Page Not Found | Albert's Auto Electrical</title>
  <link rel="icon" type="image/png" href="{SITE}/assets/img/logo.png">
  <style>
    body {{ margin: 0; min-height: 100vh; display: grid; place-items: center;
           background: #0b0f16; color: #e9eef5; text-align: center;
           font-family: system-ui, -apple-system, "Segoe UI", sans-serif; padding: 24px; }}
    h1 {{ font-size: clamp(34px, 6vw, 56px); margin: 0 0 10px; letter-spacing: -0.02em; }}
    p {{ color: #9aa8ba; max-width: 46ch; margin: 0 auto 28px; line-height: 1.6; }}
    a.btn {{ display: inline-block; padding: 14px 28px; border-radius: 999px; margin: 0 8px;
             font-weight: 700; text-decoration: none; font-size: 15.5px; }}
    a.solid {{ background: #2e9bff; color: #fff; }}
    a.ghost {{ border: 2px solid rgba(255,255,255,0.2); color: #e9eef5; }}
    .logo {{ width: 74px; height: 74px; margin: 0 auto 22px; display: block; }}
  </style>
</head>
<body>
  <div>
    <img class="logo" src="{SITE}/assets/img/logo.png" alt="Albert's Auto Electrical">
    <h1>404 — dead wire</h1>
    <p>That circuit doesn't lead anywhere. Let's get you back to a live one.</p>
    <a class="btn solid" href="{SITE}/">Back to Home</a>
    <a class="btn ghost" href="{SITE}/contact-us/">Contact Us</a>
  </div>
</body>
</html>'''


# ---------------------------------------------------------------- assemble + write
def _win_long(p):
    """Bypass Windows MAX_PATH for very long blog slugs."""
    if os.name == "nt" and not p.startswith("\\\\?\\"):
        return "\\\\?\\" + os.path.abspath(p)
    return p


MANIFEST = {"pages": [], "stubs": []}   # public URL paths this build produced


def write_page(route, html):
    # folders are written percent-DECODED: static servers (incl. GitHub Pages)
    # decode the URL before matching the filesystem, so /%f0%9d.../ must find
    # a folder named with the decoded characters.
    segs = [urllib.parse.unquote(x) for x in route.split("/")] if route else []
    path = os.path.join(ROOT, *segs, "index.html") if route else os.path.join(ROOT, "index.html")
    os.makedirs(_win_long(os.path.dirname(path)), exist_ok=True)
    with open(_win_long(path), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(html)
    MANIFEST["pages"].append(route + "/" if route else "")
    return path


def purge_stale_twins():
    """Remove leftover percent-encoded twin dirs from older builds, e.g.
    '%f0%9f%98%8e-slug/' sitting next to the decoded '😎-slug/'. A dir is only
    removed when its DECODED name is a current route and the dir itself is not,
    so nothing hand-written or unrelated can ever match."""
    known = {
        "": {urllib.parse.unquote(b["slug"]) for b in BLOG},
        "blog": {urllib.parse.unquote(b["slug"]) for b in BLOG},
        "gallery": {urllib.parse.unquote(g["slug"]) for g in GALLERY},
        "testimonial": {urllib.parse.unquote(t["slug"]) for t in TESTIMONIALS},
        "service-estimate": {e["slug"] for e in ESTIMATES},
    }
    removed = 0
    for parent, names in known.items():
        base = os.path.join(ROOT, parent) if parent else ROOT
        try:
            entries = os.listdir(_win_long(base))
        except OSError:
            continue
        for name in entries:
            if "%" not in name or name in names or urllib.parse.unquote(name) not in names:
                continue
            shutil.rmtree(_win_long(os.path.join(base, name)), ignore_errors=True)
            removed += 1
    return removed


def main():
    built = []
    stale = purge_stale_twins()
    MANIFEST["pages"].clear()
    MANIFEST["stubs"].clear()

    # core pages rebuilt from existing content with original-URL links
    built.append(write_page("", core_page("", "index.html",
        "Albert's Auto Electrical | Auto Electrician Smithfield & Sydney NSW",
        "Albert's Auto Electrical — specialist auto electrician in Smithfield, Sydney. Performance cars, classic car rewires, 4WD accessories, truck lighting, air conditioning. Call 0421 667 118.",
        "home", "assets/img/hero-car.png")))
    built.append(write_page("about-us", core_page("about-us", "about.html",
        "About Us | Albert's Auto Electrical — Sydney Auto Electrician",
        "Founded on a passion for cars — meet Albert Costagliola and the values behind 20+ years of quality auto electrical workmanship across NSW.",
        "about")))
    built.append(write_page("serve", core_page("serve", "services.html",
        "Auto Electrical Services | Performance, Classic, 4WD & Air-Con — Albert's Auto Electrical",
        "Specialist auto electrical services in Sydney: performance ECU and engine management, classic car rewires, 4WD accessories, truck lighting, air conditioning and more.",
        "services")))
    built.append(write_page("testimonial", core_page("testimonial", "testimonials.html",
        "Testimonials | Albert's Auto Electrical — Sydney Reviews",
        "What Sydney drivers say about Albert's Auto Electrical — professionalism, punctuality, quality and value. Real Google reviews.",
        "testimonials")))
    built.append(write_page("locations", core_page("locations", "locations.html",
        "Locations | Areas We Service Across Sydney — Albert's Auto Electrical",
        "Servicing Smithfield and suburbs across Sydney — Auburn, Blacktown, Camden, Campbelltown, Bankstown, Fairfield, Cumberland, Liverpool, Parramatta, Penrith and the Hills Shire.",
        "locations")))
    built.append(write_page("contact-us", core_page("contact-us", "contact.html",
        "Contact Us | Book a Service — Albert's Auto Electrical Smithfield",
        "Book your car in with Albert's Auto Electrical. Call 0421 667 118, visit 3/41 O'Connell Street Smithfield NSW, or send a booking request. Mon–Fri 9–5, Sat by appointment.",
        "contact")))

    # serve detail pages
    for slug in ["performance-cars", "classic-cars", "cars-trucks-and-four-wheel-drives",
                 "installation-of-a-c-units-air-con-service", "tires-wheels"]:
        built.append(write_page("serve/" + slug, build_serve_detail(slug)))

    # blog
    built.append(write_page("blog", build_blog_archive()))
    for i, b in enumerate(BLOG):
        built.append(write_page(b["slug"], build_blog_post(b, i)))

    # testimonials archive extras + items
    # append the review-archive section into the extracted testimonial page
    route = "testimonial"
    t_main = rewrite(route, extract_main("testimonials.html"))
    t_main += build_testimonial_archive_extras(route)
    built.append(write_page(route, page_shell(route,
        "Testimonials | Albert's Auto Electrical — Sydney Reviews",
        "What Sydney drivers say about Albert's Auto Electrical — professionalism, punctuality, quality and value. Real Google reviews.",
        "testimonials", t_main)))
    for i, t in enumerate(TESTIMONIALS):
        built.append(write_page("testimonial/" + t["slug"], build_testimonial_item(t, i)))

    # gallery archive extras + items
    route = "gallery"
    # gallery.html already extracted above via core_page; rebuild with archive appended
    g_main = rewrite(route, extract_main("gallery.html"))
    g_main += build_gallery_archive(route)
    built.append(write_page(route, page_shell(route,
        "Gallery | Our Work — Albert's Auto Electrical",
        "Photos from the Albert's Auto Electrical workshop in Smithfield — performance wiring, classic rewires, 4WD fit-outs and more.",
        "gallery", g_main)))
    for i, g in enumerate(GALLERY):
        built.append(write_page("gallery/" + g["slug"], build_gallery_item(g, i)))

    # faq / pricing / shop placeholders / estimates / 404
    built.append(write_page("faq", build_faq()))
    built.append(write_page("pricing-coupons", build_pricing()))
    built.append(write_page("shop", build_shop_notice("shop", "Shop", "The shop is taking a rest",
        "Albert's workshop is full of cars, not e-commerce boxes — the original store only ever held WooCommerce demo products, so we've kept the URL and dropped the clutter.")))
    built.append(write_page("cart", build_shop_notice("cart", "Cart", "Nothing in the cart",
        "There's nothing to check out — everything Albert offers is a service, not a product.")))
    built.append(write_page("checkout", build_shop_notice("checkout", "Checkout", "Nothing to check out",
        "No products, no checkout — just honest auto electrical work.")))
    built.append(write_page("my-account", build_shop_notice("my-account", "My Account", "No account needed",
        "You don't need an account to get great service — just a phone call.")))
    for i, e in enumerate(ESTIMATES):
        built.append(write_page("service-estimate/" + e["slug"], build_estimate(e, i)))

    with open(os.path.join(ROOT, "404.html"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(build_404())
    built.append(os.path.join(ROOT, "404.html"))

    # sitemap + robots
    routes = [""] + [r for r in [
        "about-us", "faq", "pricing-coupons", "gallery", "testimonial", "locations", "contact-us",
        "serve", "blog", "shop", "cart", "checkout", "my-account",
    ] ]
    routes += ["serve/" + s["slug"] for s in [
        {"slug": "performance-cars"}, {"slug": "classic-cars"},
        {"slug": "cars-trucks-and-four-wheel-drives"},
        {"slug": "installation-of-a-c-units-air-con-service"}, {"slug": "tires-wheels"}]]
    routes += [b["slug"] for b in BLOG]
    routes += ["testimonial/" + t["slug"] for t in TESTIMONIALS]
    routes += ["gallery/" + g["slug"] for g in GALLERY]
    routes += ["service-estimate/" + e["slug"] for e in ESTIMATES]
    routes = list(dict.fromkeys(routes))  # dedupe, keep order

    # redirect stubs for the old flat URLs (bookmarks / history / old links)
    for old, to, label in [("about.html", "about-us", "About Us"),
                           ("services.html", "serve", "Services"),
                           ("gallery.html", "gallery", "Gallery"),
                           ("testimonials.html", "testimonial", "Testimonials"),
                           ("locations.html", "locations", "Locations"),
                           ("contact.html", "contact-us", "Contact Us")]:
        with open(os.path.join(ROOT, old), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(make_redirect_stub(href("", to), label))
        MANIFEST["stubs"].append(old)
        built.append(os.path.join(ROOT, old))

    # compat redirects: one early deploy served posts under /blog/<slug>/
    # so any bookmarks of those URLs keep working
    for b in BLOG:
        stub_path = os.path.join(ROOT, "blog", urllib.parse.unquote(b["slug"]), "index.html")
        os.makedirs(os.path.dirname(_win_long(stub_path)), exist_ok=True)
        with open(_win_long(stub_path), "w", encoding="utf-8", newline="\n") as fh:
            # page lives at /blog/<slug>/, so the root-level post is two levels up
            fh.write(make_redirect_stub(href("blog/" + b["slug"], b["slug"]), b["title"]))
        # manifest stores the public URL path (percent-encoded, as in the data)
        MANIFEST["stubs"].append("blog/" + b["slug"] + "/")
        built.append(stub_path)

    with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for r in routes:
            fh.write(f"  <url><loc>{SITE}/{r + '/' if r else ''}</loc></url>\n")
        fh.write("</urlset>\n")
    with open(os.path.join(ROOT, "robots.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n")
    # skip Jekyll processing on GitHub Pages — output is served as-is
    with open(os.path.join(ROOT, ".nojekyll"), "w", encoding="utf-8") as fh:
        fh.write("")

    # exact list of what this build produced — tools/audit.py crawls this
    # instead of walking the disk (Windows can't enumerate the longest folders)
    with open(os.path.join(ROOT, ".build-manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(MANIFEST, fh, ensure_ascii=False, indent=1)

    print(f"built {len(built)} pages + sitemap.xml ({len(routes)} urls) + robots.txt"
          f" | purged {stale} stale dirs | manifest: {len(MANIFEST['pages'])} pages, {len(MANIFEST['stubs'])} stubs")


if __name__ == "__main__":
    main()
