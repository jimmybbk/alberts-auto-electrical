#!/usr/bin/env python3
"""Browser end-to-end test of the contact form (photo attach + submit).

Runs the real /contact-us/ page in headless Edge/Chrome against a LOCAL mock
form service, so nothing is sent anywhere. Starts its own site server and mock
service, writes a temporary harness page into the site root (same origin, so
it can drive the page), prints a report, then removes the harness.

Usage:  python tools/form_selftest.py              run the scenarios
        python tools/form_selftest.py --shots DIR  also screenshot the form
Build the site first: python tools/build.py
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import serve  # noqa: E402  — the site's own server handler (long-path aware)

HARNESS = "_form-selftest.html"
SHOT_HARNESS = "_form-shot.html"
RECEIVED = []   # each submission as [(field, filename, size, value)]
REPORT = []     # the harness's result text


def find_edge():
    for cand in [os.environ.get("EDGE_PATH", ""),
                 r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                 r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                 shutil.which("msedge") or "", shutil.which("chrome") or ""]:
        if cand and os.path.isfile(cand):
            return cand
    sys.exit("Edge/Chrome not found — set EDGE_PATH")


EDGE = find_edge()


def parse_multipart(ctype, body):
    """[(name, filename, size, value)] for a multipart/form-data body."""
    m = re.search(r'boundary="?([^";]+)"?', ctype or "")
    if not m:
        return []
    delim = b"--" + m.group(1).encode("latin-1")
    parts = []
    for chunk in body.split(delim)[1:-1]:
        chunk = chunk[2:] if chunk.startswith(b"\r\n") else chunk
        chunk = chunk[:-2] if chunk.endswith(b"\r\n") else chunk
        head, _, content = chunk.partition(b"\r\n\r\n")
        name = re.search(rb'name="([^"]*)"', head)
        fname = re.search(rb'filename="([^"]*)"', head)
        is_file = bool(fname)
        parts.append((name.group(1).decode("utf-8", "replace") if name else "",
                      fname.group(1).decode("utf-8", "replace") if is_file else None,
                      len(content),
                      b"" if is_file else content))
    return parts


class Relay(BaseHTTPRequestHandler):
    """Stands in for a form service: records submissions and answers JSON.
    Also receives the test harness's report (/report), because a browser
    launched from Python on Windows gives no usable stdout."""

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Accept, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        if self.path.endswith("/report"):
            REPORT.append(body.decode("utf-8", "replace"))
            self.send_response(200)
            self._cors()
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        parts = parse_multipart(self.headers.get("Content-Type", ""), body)
        RECEIVED.append(parts)
        if b"FAILTEST" in b" ".join(p[3] for p in parts):
            code, data = 500, b'{"success": "false", "message": "mock failure"}'
        else:
            code, data = 200, b'{"success": "true"}'
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):  # keep the report readable
        pass


class QuietSite(serve.Handler):
    def log_message(self, *args):
        pass


def start(handler):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def launch_edge(args, url):
    """Headless browsers on Windows detach from the launching process, so this
    only starts one; results arrive via the mock service or screenshot file."""
    profile = tempfile.mkdtemp(prefix="aae-edge-")
    subprocess.Popen([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                      "--user-data-dir=" + profile, *args, url],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return profile


def wait_until(fn, timeout):
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = fn()
        if value:
            return value
        time.sleep(0.5)
    return None


def close_browser(profile):
    """Stop only the browser that was started with this profile folder."""
    script = (
        "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | "
        "Where-Object { $_.CommandLine -like '*%s*' } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    ) % profile
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                   capture_output=True, timeout=60)


HARNESS_JS = r"""
(function () {
  var out = [], failed = 0;
  function post(s) {
    // each line is sent to the mock service as it happens, so a stalled run
    // still shows how far it got
    try { fetch("__REPORT__", { method: "POST", body: s + "\n" }); } catch (e) {}
  }
  function say(s) {
    out.push(s);
    document.getElementById("out").textContent = out.join("\n");
    post(s);
  }
  window.addEventListener("error", function (e) { post("WINDOW ERROR " + e.message); });
  window.addEventListener("unhandledrejection", function (e) { post("WINDOW REJECTION " + (e.reason && e.reason.stack || e.reason)); });
  function check(ok, name, detail) { if (!ok) failed++; say((ok ? "PASS " : "FAIL ") + name + " — " + detail); }
  var frame = document.getElementById("f");
  function load() {
    return new Promise(function (res) { frame.onload = function () { res(frame); }; frame.src = "/contact-us/?t=" + Date.now(); });
  }
  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  function waitFor(fn, ms) {
    var t0 = Date.now();
    return new Promise(function (res) {
      (function tick() {
        var v = null;
        try { v = fn(); } catch (e) { v = null; }
        if (v) return res(v);
        if (Date.now() - t0 > (ms || 15000)) return res(null);
        setTimeout(tick, 40);
      })();
    });
  }
  function open(mode) {
    return load().then(function (f) {
      var form = f.contentDocument.querySelector("[data-booking-form]");
      if (mode === "email") form.removeAttribute("data-endpoint");
      else form.setAttribute("data-endpoint", "__RELAY__");
      return f;
    });
  }
  function fill(f, msg) {
    var d = f.contentDocument;
    d.getElementById("name").value = "Test Customer";
    d.getElementById("phone").value = "0400 000 000";
    d.getElementById("email").value = "test@example.com";
    d.getElementById("vehicle").value = "1995 Toyota Supra";
    d.getElementById("service").selectedIndex = 4;
    d.getElementById("message").value = msg;
  }
  function picture(f, w, h, name) {
    var c = f.contentDocument.createElement("canvas");
    c.width = w; c.height = h;
    var g = c.getContext("2d"), grad = g.createLinearGradient(0, 0, w, h);
    grad.addColorStop(0, "#c0392b"); grad.addColorStop(0.5, "#f1c40f"); grad.addColorStop(1, "#2980b9");
    g.fillStyle = grad; g.fillRect(0, 0, w, h);
    for (var i = 0; i < 900; i++) {
      g.fillStyle = "rgba(255,255,255," + (i % 10) / 10 + ")";
      g.beginPath(); g.arc((i * 97) % w, (i * 53) % h, 15 + (i % 40), 0, 7); g.fill();
    }
    return new Promise(function (r) {
      c.toBlob(function (b) { r(new f.contentWindow.File([b], name, { type: "image/jpeg" })); }, "image/jpeg", 0.95);
    });
  }
  function attach(f, file) {
    var d = f.contentDocument, dt = new f.contentWindow.DataTransfer();
    dt.items.add(file);
    d.getElementById("photo").files = dt.files;
    d.getElementById("photo").dispatchEvent(new f.contentWindow.Event("change", { bubbles: true }));
  }
  function q(f, sel) { return f.contentDocument.querySelector(sel); }
  function visible(el) { return !!el && !el.hidden; }

  function scenarioA() {
    return open("relay").then(function (f) {
      fill(f, "Engine light is on and the indicator flickers.");
      return picture(f, 3000, 2000, "dash-warning.jpg").then(function (file) {
        attach(f, file);
        return waitFor(function () { return !q(f, "[data-attach-preview]").hidden; }).then(function (shown) {
          check(!!shown, "A1 preview appears after choosing a photo", shown ? "preview visible" : "timed out");
          return waitFor(function () { return q(f, "[data-attach-img]").naturalWidth > 0; }).then(function () {
            var img = q(f, "[data-attach-img]");
            var longest = Math.max(img.naturalWidth, img.naturalHeight);
            check(longest > 0 && longest <= 1600, "A2 big photo resized on device", img.naturalWidth + "x" + img.naturalHeight + " (was 3000x2000)");
            check(/^dash-warning.*\.jpe?g$/.test(q(f, "[data-attach-name]").textContent), "A3 file name kept", q(f, "[data-attach-name]").textContent + ", " + q(f, "[data-attach-size]").textContent);
            q(f, "[data-attach-remove]").click();
            check(q(f, "[data-attach-preview]").hidden && !q(f, "[data-attach-pick]").hidden, "A4 remove button clears the photo", "preview hidden, add button back");
            attach(f, file);
            return waitFor(function () { return !q(f, "[data-attach-preview]").hidden; });
          });
        }).then(function (back) {
          check(!!back, "A5 photo can be re-attached", back ? "preview visible again" : "timed out");
          q(f, "[data-booking-form]").requestSubmit();
          return waitFor(function () { return visible(q(f, "[data-form-success]")); }).then(function (ok) {
            check(!!ok, "A6 send succeeds and shows the thank-you panel", ok ? "success panel visible" : "timed out");
            check(q(f, "[data-booking-form]").hidden, "A7 form hides after success", "form hidden");
            check(/photo/.test(q(f, "[data-success-lead]").textContent), "A8 thank-you mentions the photo", q(f, "[data-success-lead]").textContent);
          });
        });
      });
    });
  }

  function scenarioB() {
    return open("relay").then(function (f) {
      attach(f, new f.contentWindow.File(["not a picture"], "notes.txt", { type: "text/plain" }));
      return waitFor(function () { return q(f, "[data-attach-hint]").classList.contains("is-error"); }).then(function (bad) {
        check(!!bad, "B1 non-image file rejected", q(f, "[data-attach-hint]").textContent);
        check(q(f, "[data-attach-preview]").hidden, "B2 no preview for a rejected file", "preview hidden");
      });
    });
  }

  function scenarioF() {
    return open("relay").then(function (f) {
      attach(f, new f.contentWindow.File([new Uint8Array(11 * 1024 * 1024)], "huge.jpg", { type: "image/jpeg" }));
      return waitFor(function () { return q(f, "[data-attach-hint]").classList.contains("is-error"); }).then(function (bad) {
        check(!!bad, "F1 photo over 10 MB rejected", q(f, "[data-attach-hint]").textContent);
      });
    });
  }

  function scenarioC() {
    return open("relay").then(function (f) {
      fill(f, "FAILTEST please");
      q(f, "[data-booking-form]").requestSubmit();
      return waitFor(function () { return visible(q(f, "[data-form-status]")); }).then(function (shown) {
        check(!!shown, "C1 failed send shows an error message", shown ? q(f, "[data-form-status]").textContent : "timed out");
        var btn = q(f, 'button[type="submit"]');
        check(!btn.disabled && /Send Booking Request/.test(btn.textContent), "C2 button usable again after failure", btn.textContent.trim());
        check(!q(f, "[data-booking-form]").hidden && !visible(q(f, "[data-form-success]")), "C3 form stays after failure", "form visible, no thank-you");
      });
    });
  }

  function scenarioD() {
    return open("relay").then(function (f) {
      fill(f, "Battery goes flat overnight.");
      q(f, "[data-booking-form]").requestSubmit();
      return waitFor(function () { return visible(q(f, "[data-form-success]")); }).then(function (ok) {
        check(!!ok, "D1 sends fine without a photo", ok ? "success panel visible" : "timed out");
        check(!/photo/.test(q(f, "[data-success-lead]").textContent), "D2 thank-you omits photo wording", q(f, "[data-success-lead]").textContent);
      });
    });
  }

  function scenarioE() {
    return open("email").then(function (f) {
      fill(f, "Hand-off to email app.");
      q(f, "[data-booking-form]").requestSubmit();
      return sleep(400).then(function () {
        check(!q(f, "[data-note-email]").hidden && q(f, "[data-note-send]").hidden, "E1 notes switch to email-app wording", "email note shown");
        check(visible(q(f, ".form-confirm")), "E2 email-app hand-off still works", "confirmation note shown");
      });
    });
  }

  scenarioA().then(scenarioB).then(scenarioF).then(scenarioC).then(scenarioD).then(scenarioE)
    .then(function () { say("RESULT " + failed + " failed"); })
    .catch(function (e) { say("ERROR " + (e && e.stack || e)); say("RESULT " + failed + " failed"); });
})();
"""

SHOT_HTML = r"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>html,body{margin:0;height:100%;background:#f5f7fa}iframe{position:fixed;inset:0;width:100%;height:100%;border:0}</style>
</head><body><iframe id="f" src="/contact-us/#booking"></iframe>
<script>
document.getElementById("f").onload = function () {
  var f = this, d = f.contentDocument;
  d.getElementById("name").value = "Jane Citizen";
  d.getElementById("phone").value = "04xx xxx xxx";
  d.getElementById("message").value = "Battery light came on this morning.";
  var c = d.createElement("canvas"); c.width = 1400; c.height = 900;
  var g = c.getContext("2d"), grad = g.createLinearGradient(0, 0, 1400, 900);
  grad.addColorStop(0, "#c0392b"); grad.addColorStop(0.5, "#f1c40f"); grad.addColorStop(1, "#2980b9");
  g.fillStyle = grad; g.fillRect(0, 0, 1400, 900);
  g.fillStyle = "#111"; g.fillRect(400, 250, 600, 300);
  c.toBlob(function (b) {
    var dt = new f.contentWindow.DataTransfer();
    dt.items.add(new f.contentWindow.File([b], "engine-bay.jpg", { type: "image/jpeg" }));
    var input = d.getElementById("photo");
    input.files = dt.files;
    input.dispatchEvent(new f.contentWindow.Event("change", { bubbles: true }));
  }, "image/jpeg", 0.9);
};
</script></body></html>"""


LIVE_HARNESS = "_form-live.html"

LIVE_JS = r"""
(function () {
  function post(s) { try { fetch("__REPORT__", { method: "POST", body: s + "\n" }); } catch (e) {} }
  var frame = document.getElementById("f");
  frame.onload = function () {
    var f = frame, w = f.contentWindow, d = f.contentDocument;
    var form = d.querySelector("[data-booking-form]");
    var endpoint = form.getAttribute("data-endpoint") || "";
    post("ENDPOINT " + (endpoint || "(none)"));
    if (!endpoint) { post("NO ENDPOINT - nothing sent"); post("RESULT 1 failed"); return; }

    // record exactly what the real service answers
    var realFetch = w.fetch.bind(w);
    w.fetch = function (url, opts) {
      return realFetch(url, opts).then(function (res) {
        return res.clone().text().then(function (text) {
          var cors = [];
          res.headers.forEach(function (v, k) { if (/access-control/.test(k)) cors.push(k + "=" + v); });
          post("RESPONSE status=" + res.status + " | final url=" + res.url +
               " | cors headers: " + (cors.join("; ") || "(none readable)") +
               " | body=" + text.slice(0, 500));
          return res;
        });
      }, function (err) { post("NETWORK ERROR " + err); throw err; });
    };

    d.getElementById("name").value = "TEST - website form check (please ignore)";
    d.getElementById("phone").value = "0000 000 000";
    d.getElementById("email").value = "";
    d.getElementById("vehicle").value = "Test enquiry - no vehicle";
    d.getElementById("service").selectedIndex = 8;
    d.getElementById("message").value =
      "This is a test enquiry sent by the website developer to confirm the contact form and photo upload work. No action is needed.";
    var c = d.createElement("canvas");
    c.width = 640; c.height = 420;
    var g = c.getContext("2d");
    g.fillStyle = "#2e9bff"; g.fillRect(0, 0, 640, 420);
    g.fillStyle = "#fff"; g.font = "bold 40px sans-serif"; g.textAlign = "center"; g.fillText("TEST PHOTO", 320, 225);
    c.toBlob(function (b) {
      var dt = new w.DataTransfer();
      dt.items.add(new w.File([b], "test-photo.jpg", { type: "image/jpeg" }));
      var input = d.getElementById("photo");
      input.files = dt.files;
      input.dispatchEvent(new w.Event("change", { bubbles: true }));
      var t0 = Date.now();
      (function ready() {
        var img = d.querySelector("[data-attach-img]");
        if (!d.querySelector("[data-attach-preview]").hidden && img.naturalWidth > 0) { form.requestSubmit(); return; }
        if (Date.now() - t0 < 15000) setTimeout(ready, 50);
      })();
    }, "image/jpeg", 0.8);

    var t1 = Date.now();
    (function watch() {
      var done = !d.querySelector("[data-form-success]").hidden;
      var status = d.querySelector("[data-form-status]");
      if (done) { post("OUTCOME thank-you panel shown"); post("RESULT 0 failed"); return; }
      if (!status.hidden) { post("OUTCOME error shown to the visitor: " + status.textContent); post("RESULT 1 failed"); return; }
      if (Date.now() - t1 < 90000) setTimeout(watch, 100);
    })();
  };
  frame.src = "/contact-us/";
})();
"""


def run_live(site_port, report_url):
    """Send ONE clearly-labelled test enquiry through the endpoint configured
    in the built page, in a real browser, and print what the service answered."""
    m = re.search(r'data-endpoint="([^"]*)"', open("contact-us/index.html", encoding="utf-8").read())
    print("LIVE TEST: one labelled test enquiry goes to:", m.group(1) if m else "(no endpoint)")
    with open(LIVE_HARNESS, "w", encoding="utf-8") as fh:
        fh.write('<!DOCTYPE html><html><body><pre id="out">live</pre>'
                 '<iframe id="f" style="width:1100px;height:900px"></iframe>'
                 '<script>' + LIVE_JS.replace("__REPORT__", report_url) + '</script></body></html>')
    prof = launch_edge([], "http://127.0.0.1:%d/%s" % (site_port, LIVE_HARNESS))
    try:
        wait_until(lambda: any(r.startswith("RESULT") for r in REPORT), 150)
    finally:
        close_browser(prof)
        time.sleep(1)
        shutil.rmtree(prof, ignore_errors=True)
    ok = False
    for chunk in REPORT:
        for line in chunk.split("\n"):
            if line.strip():
                print("  " + line)
                ok = ok or line.startswith("RESULT 0")
    if not REPORT:
        print("  NO REPORT — the test page did not run")
    return ok


def main():
    # reports contain typographic dashes; keep them readable on Windows consoles
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", nargs="?", const=tempfile.gettempdir(), default=None,
                    metavar="DIR", help="also save screenshots of the form into DIR")
    ap.add_argument("--live", action="store_true",
                    help="send ONE real, clearly-labelled test enquiry through the endpoint in the built page")
    opt = ap.parse_args()

    os.chdir(ROOT)
    if "data-booking-form" not in open("contact-us/index.html", encoding="utf-8").read():
        sys.exit("contact-us/index.html is out of date — run: python tools/build.py")

    site, site_port = start(QuietSite)
    relay, relay_port = start(Relay)
    base = "http://127.0.0.1:%d" % relay_port
    print("site on :%d, mock form service on :%d" % (site_port, relay_port))
    profiles = []
    try:
        if opt.live:
            sys.exit(0 if run_live(site_port, base + "/report") else 1)

        with open(HARNESS, "w", encoding="utf-8") as fh:
            js = HARNESS_JS.replace("__RELAY__", base + "/relay").replace("__REPORT__", base + "/report")
            fh.write('<!DOCTYPE html><html><body><pre id="out">running</pre>'
                     '<iframe id="f" style="width:1100px;height:900px"></iframe>'
                     '<script>' + js + '</script></body></html>')
        # Real time, not the headless "virtual clock": fast-forwarded time
        # expires while image work is still running and kills the page early.
        profiles.append(launch_edge([], "http://127.0.0.1:%d/%s" % (site_port, HARNESS)))
        wait_until(lambda: any("RESULT " in r for r in REPORT), 240)
        close_browser(profiles[-1])
        report = "".join(REPORT).strip() or "NO REPORT — harness did not run"
        report = "\n".join(dict.fromkeys(line for line in report.split("\n") if line.strip()))
        print(report)

        print("\nwhat the mock form service received:")
        for i, parts in enumerate(RECEIVED):
            fields = ["%s=%s" % (n, v.decode("utf-8", "replace")[:30]) for n, fn, sz, v in parts
                      if fn is None and n in ("name", "phone", "service", "_honey")]
            files = ["%s: %s (%d bytes)" % (n, fn, sz) for n, fn, sz, v in parts if fn is not None]
            print("  request %d: %d parts | %s | files: %s" % (i + 1, len(parts), "; ".join(fields), ", ".join(files) or "none"))

        # request order: A (with photo), C (forced failure), D (no photo)
        sent = [p for p in RECEIVED[0] if p[1] is not None] if RECEIVED else []
        py_ok = bool(sent) and sent[0][2] > 1000
        print("\nPYTHON CHECK photo attached to request 1:", "PASS" if py_ok else "FAIL", sent)
        ok = len(RECEIVED) >= 3 and not any(p[1] is not None for p in RECEIVED[2])
        py_ok &= ok
        print("PYTHON CHECK request 3 (no photo) carries no file:", "PASS" if ok else "FAIL")

        if opt.shots:
            with open(SHOT_HARNESS, "w", encoding="utf-8") as fh:
                fh.write(SHOT_HTML)
            for label, size in (("desktop", (1440, 1500)), ("mobile", (500, 1750))):
                out = os.path.join(opt.shots, "form-%s.png" % label)
                if os.path.exists(out):
                    os.remove(out)
                profiles.append(launch_edge(["--window-size=%d,%d" % size, "--screenshot=" + out,
                                             "--virtual-time-budget=15000"],
                                            "http://127.0.0.1:%d/%s" % (site_port, SHOT_HARNESS)))
                wait_until(lambda: os.path.exists(out), 120)
                print("screenshot:", out, "%d bytes" % os.path.getsize(out) if os.path.exists(out) else "NOT CREATED")
    finally:
        for name in (HARNESS, SHOT_HARNESS, LIVE_HARNESS):
            if os.path.exists(name):
                os.remove(name)
        # give browsers a moment to exit before removing their profiles
        time.sleep(2)
        for prof in profiles:
            shutil.rmtree(prof, ignore_errors=True)
        site.shutdown()
        relay.shutdown()

    res = re.search(r"^RESULT (\d+) failed$", report, re.M)
    js_failed = int(res.group(1)) if res else 99   # 99 = harness never finished
    print("\nSUMMARY: browser checks failed = %d | python checks failed = %d" % (js_failed, 0 if py_ok else 1))
    sys.exit(0 if (js_failed == 0 and py_ok) else 1)


if __name__ == "__main__":
    main()
