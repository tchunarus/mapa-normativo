#!/usr/bin/env python3
"""Static file server that avoids os.getcwd() entirely (some sandboxes block that syscall)."""
import functools
import http.server
import os
import sys

PORT = 8765
DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
DIRECTORY = os.path.normpath(DIRECTORY)

Handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=DIRECTORY)

if __name__ == "__main__":
    with http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler) as httpd:
        sys.stderr.write(f"Serving {DIRECTORY} at http://127.0.0.1:{PORT}\n")
        sys.stderr.flush()
        httpd.serve_forever()
