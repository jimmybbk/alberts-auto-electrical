#!/usr/bin/env python3
"""Run the site's own copy (data/copy-blocks.json) through the HueWrite API.

Requires a Max-plan API key (hue_...) from huewrite.com > Developer page.
Provide it via the HUEWRITE_API_KEY environment variable or a
huewrite_key.txt file in the project root (gitignored - never commit it).

Usage:
  python tools/huewrite_api.py --dry-run     show the plan, send nothing
  python tools/huewrite_api.py               send every page, save results
  python tools/huewrite_api.py --page about  send only pages matching "about"

Results go to data/huewrite_results.json as {page: humanized_text}, one
entry per page (blocks joined with blank lines), ready for review.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
os.chdir(ROOT)
API = "https://huewrite.com/api/v1/humanize"
STRONG = re.compile(r"<strong>(.*?)</strong>", re.S)


def read_key():
    key = os.environ.get("HUEWRITE_API_KEY", "").strip()
    if key:
        return key, "environment"
    if os.path.exists("huewrite_key.txt"):
        key = open("huewrite_key.txt", encoding="utf-8").read().strip()
        if key:
            return key, "huewrite_key.txt"
    return None, None


def load_blocks():
    blocks = json.load(open(os.path.join("data", "copy-blocks.json"), encoding="utf-8"))
    pages, skipped = {}, []
    for i, b in enumerate(blocks):
        if b.get("customer"):
            skipped.append((b["page"], "customer content", b["words"]))
            continue
        raw = b["raw"]
        lead = ""
        rest = raw
        m = STRONG.match(rest)
        if m:                                  # bold lead-in: humanize the rest only
            lead, rest = m.group(1), raw[m.end():].strip()
        if re.search(r"<a\b|<em\b|<small\b|<br", rest):
            skipped.append((b["page"], "contains markup besides a bold lead-in", b["words"]))
            continue
        plain = re.sub(r"<[^>]+>", " ", rest)
        plain = re.sub(r"\s+", " ", html_unescape(plain)).strip()
        if len(plain.split()) < 8:
            skipped.append((b["page"], "too short to humanize", b["words"]))
            continue
        pages.setdefault(b["page"], []).append(
            {"i": i, "lead": lead, "text": plain, "words": b["words"]})
    return pages, skipped


def html_unescape(t):
    import html
    return html.unescape(t)


def humanize(text, key, opt):
    body = json.dumps({"text": text, "tone": opt.tone, "rewriteLevel": opt.rewrite}).encode()
    req = urllib.request.Request(API, data=body, method="POST",
                                 headers={"Authorization": "Bearer " + key,
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return "HTTPERROR " + str(e.code) + ": " + e.read().decode("utf-8", "replace")[:200]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-block", action="store_true",
                    help="one request per block (exact 1:1 mapping back to the pages)")
    ap.add_argument("--dry-run", action="store_true", help="show the plan, send nothing")
    ap.add_argument("--page", default="", help="only pages whose name contains this")
    ap.add_argument("--tone", default="professional",
                    choices=["standard", "academic", "professional", "friendly", "formal", "casual", "creative"])
    ap.add_argument("--rewrite", default="quality", choices=["quality", "balanced", "max"],
                    help="quality stays closest to the original wording (recommended for factual copy)")
    opt = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    key, fromwhere = read_key()
    pages, skipped = load_blocks()
    if opt.page:
        pages = {k: v for k, v in pages.items() if opt.page.lower() in k.lower()}

    print(f"pages: {len(pages)} | blocks to humanize: {sum(len(v) for v in pages.values())} "
          f"| words: {sum(b['words'] for v in pages.values() for b in v)}")
    print(f"skipped: {len(skipped)} (customer content / markup / too short)")
    for page, why, words in skipped:
        print(f"   skip [{page}] {why} ({words} words)")
    for page, items in pages.items():
        print(f"   send [{page}] {len(items)} blocks, {sum(b['words'] for b in items)} words")

    if opt.dry_run:
        print("dry run: nothing sent")
        return
    if not key:
        sys.exit("No API key. Subscribe to the Max plan, create a key on the Developer page, then either:\n"
                 "  setx HUEWRITE_API_KEY hue_...      (new terminal afterwards)\n"
                 "  or save it to huewrite_key.txt in the project root (gitignored)")

    results_path = os.path.join("data", "huewrite_results.json")
    if opt.per_block:
        out_path = os.path.join("data", "huewrite_results_blocks.json")
        done = json.load(open(out_path, encoding="utf-8")) if os.path.exists(out_path) else {}
        flat = []
        for page, items in pages.items():
            for item in items:
                flat.append((page, item["i"], item))
        todo = [(p, i, b) for p, i, b in flat if str(i) not in done]
        print(f"per-block mode: {len(flat)} blocks total, {len(done)} already done, {len(todo)} to send")
        fails = 0
        for n, (page, i, b) in enumerate(todo, 1):
            out = humanize(b["text"], key, opt)
            if out.startswith("HTTPERROR"):
                fails += 1
                print(f"  [{n}/{len(todo)}] FAIL {out[:120]}")
            else:
                done[str(i)] = {"page": page, "lead": b["lead"], "text": " ".join(out.split())}
                print(f"  [{n}/{len(todo)}] {page}: {len(b['text'].split())} -> {len(out.split())} words")
            with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
                json.dump(done, fh, ensure_ascii=False, indent=1)   # save after every call
            time.sleep(2.2)                     # stay under 30 requests/minute
        print(f"saved {len(done)} block results to {out_path} | failed: {fails}")
        return

    results = json.load(open(results_path, encoding="utf-8")) if os.path.exists(results_path) else {}
    for page, items in pages.items():
        text = "\n\n".join(b["text"] for b in items)
        body = json.dumps({"text": text, "tone": opt.tone, "rewriteLevel": opt.rewrite}).encode()
        req = urllib.request.Request(API, data=body, method="POST",
                                     headers={"Authorization": "Bearer " + key,
                                              "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                out = r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            print(f"[{page}] HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:200]}")
            continue
        paras = [p.strip() for p in out.split("\n\n") if p.strip()]
        if len(paras) != len(items):
            print(f"[{page}] WARNING: {len(items)} blocks sent, {len(paras)} paragraphs back")
        results[page] = {"tone": opt.tone, "rewrite": opt.rewrite,
                         "blocks": [{"i": b["i"], "lead": b["lead"], "text": p}
                                    for b, p in zip(items, paras)]}
        print(f"[{page}] ok: {len(text.split())} words in, {len(out.split())} words out")
        time.sleep(2.5)                     # stay under 30 requests/minute
    with open(results_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=1)
    print(f"saved {len(results)} pages to {results_path} - review it, then apply")


if __name__ == "__main__":
    main()
