#!/usr/bin/env python3
"""Local dev server with Windows long-path support (\\?\ prefix)."""
import http.server
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Handler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        p = super().translate_path(path)
        if os.name == "nt" and len(p) > 240 and not p.startswith("\\\\?\\"):
            p = "\\\\?\\" + p
        return p


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8472
    os.chdir(ROOT)
    http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
