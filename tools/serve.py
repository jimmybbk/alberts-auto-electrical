#!/usr/bin/env python3
"""Local dev server with Windows long-path support.
Plain paths work up to ~259 chars (including unicode); the \\?\\ prefix is
needed beyond that but breaks emoji paths, so it is a fallback only."""
import http.server
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Handler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        p = super().translate_path(path)
        if os.name == "nt" and not os.path.exists(p):
            longp = "\\\\?\\" + os.path.abspath(p)
            if os.path.exists(longp):
                return longp
        return p


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8472
    os.chdir(ROOT)
    http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
