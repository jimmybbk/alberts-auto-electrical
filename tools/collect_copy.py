#!/usr/bin/env python3
"""Collect the prose on every non-blog page as blocks for the humanizer.

Each block maps back to the source file that holds it, and text copied from
the original site (customer reviews, photo titles) is flagged customer=True
so the humanizer runner skips it. Output: data/copy-blocks.json

Usage: python tools/collect_copy.py
"""
import html
import json
import os
import re

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join("data", "copy-blocks.json")
PRE = chr(92) * 2 + "?" + chr(92)
VOID = {"img", "br", "hr", "input", "meta", "link", "path", "circle", "rect", "polygon", "line", "source", "use"}
SKIP_ANCESTORS = {"blockquote", "nav", "button", "select", "option", "label", "figcaption", "table",
                  "h1", "h2", "h3", "h4", "h5", "h6"}
KEEP_PARENTS = {"p", "li", "span", "div", "strong", "em", "small", "a"}

PAGES = [
    ("", "home"), ("about-us", "about"), ("serve", "services hub"),
    ("serve/performance-cars", "service: performance"), ("serve/classic-cars", "service: classic"),
    ("serve/cars-trucks-and-four-wheel-drives", "service: cars/trucks/4wd"),
    ("serve/installation-of-a-c-units-air-con-service", "service: aircon"),
    ("serve/tires-wheels", "service: engine services"),
    ("contact-us", "contact"), ("faq", "faq"), ("pricing-coupons", "pricing"), ("locations", "locations"),
    ("gallery", "gallery archive"), ("testimonial", "testimonials archive"),
    ("shop", "shop notice"), ("cart", "cart notice"), ("checkout", "checkout notice"), ("my-account", "account notice"),
    ("service-estimate/brake-pad-replacement", "estimate page template"),
    ("gallery/gallery-3", "gallery item template"), ("testimonial/ct", "review page template"),
]


def read(p):
    try:
        return open(p, encoding="utf-8").read()
    except OSError:
        return open(PRE + os.path.abspath(p), encoding="utf-8").read()


TAG = re.compile(r"<(/?)([a-zA-Z0-9]+)([^>]*?)(/?)>", re.S)


def prose_blocks(main):
    """Yield (raw_html, parent_tag, ancestors) for text runs of 12+ words."""
    stack, out, pos = [], [], 0
    for m in TAG.finditer(main):
        text = main[pos: m.start()]
        if text.strip():
            parent = stack[-1][0] if stack else ""
            if len(html.unescape(text).split()) >= 12 and parent in KEEP_PARENTS \
                    and not ({a for a, _ in stack} & SKIP_ANCESTORS):
                out.append((text.strip(), parent, [a for a, _ in stack]))
        closing, name, attrs, selfclose = m.group(1), m.group(2).lower(), m.group(3), m.group(4)
        if closing:
            for i in range(len(stack) - 1, -1, -1):
                if stack[i][0] == name:
                    del stack[i:]
                    break
        elif name not in VOID and not selfclose:
            stack.append((name, attrs))
        pos = m.end()
    return out


SOURCES = [f"tools/src/{n}.html" for n in
           ("index", "about", "services", "contact", "testimonials", "gallery", "locations")] + ["tools/build.py"]
SRC = {s: read(s) for s in SOURCES}
blocks, customer = [], 0
for route, label in PAGES:
    page = read(os.path.join(route, "index.html") if route else "index.html")
    main = re.search(r'<main id="main">(.*?)</main>', page, re.S).group(1)
    main = re.sub(r"<svg\b.*?</svg>", " ", main, flags=re.S)
    main = re.sub(r"<!--.*?-->", " ", main, flags=re.S)
    for raw, parent, ancestors in prose_blocks(main):
        text = re.sub(r"\s+", " ", html.unescape(raw)).strip()
        source = next((s for s, body in SRC.items() if raw in body), None)
        # unmapped text on the gallery/testimonial pages is customer content or
        # photo titles copied from the original site: not ours to rewrite
        is_customer = source is None and route.split("/")[0] in ("gallery", "testimonial")
        customer += is_customer
        blocks.append({
            "page": label, "route": route, "parent": parent,
            "in_link": "a" in ancestors,
            "customer": is_customer, "source": source,
            "words": len(text.split()), "raw": raw, "text": text,
        })

with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(blocks, fh, ensure_ascii=False, indent=1)

ours = [b for b in blocks if not b["customer"]]
print(f"{len(blocks)} prose blocks ({sum(b['words'] for b in blocks)} words) "
      f"| ours: {len(ours)} blocks / {sum(b['words'] for b in ours)} words "
      f"| customer content skipped: {customer}")
print("blocks containing a link (kept as-is by the runner):", sum(1 for b in ours if b["in_link"]))
