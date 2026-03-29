#!/usr/bin/env python3
"""Staging preview server with edit API.

Serves staged HTML files and accepts PUT requests to save edits back.
Replaces the static `python3 -m http.server` in .claude/launch.json.

Usage:
    python3 scripts/staging_server.py [--port 8111]
"""

import argparse
import json
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SHELL_PATH = PLUGIN_ROOT / "templates" / "canvas-shell.html"

# Import from staging_manager to share course-specific directory logic
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
try:
    from staging_manager import get_staging_dir, STAGING_ROOT
except ImportError:
    STAGING_ROOT = PLUGIN_ROOT / "staging"
    def get_staging_dir():
        return STAGING_ROOT

RAW_START = '<!-- RAW_CONTENT_START -->'
RAW_END = '<!-- RAW_CONTENT_END -->'


def _wrap_content(html_content):
    """Wrap raw HTML in the Canvas shell template."""
    shell = SHELL_PATH.read_text(encoding="utf-8")
    wrapped = f"{RAW_START}\n{html_content}\n{RAW_END}"
    return shell.replace("{{CONTENT}}", wrapped)


def _extract_raw(staged_html):
    """Extract raw content from a staged file (strips shell wrapper)."""
    start_idx = staged_html.find(RAW_START)
    end_idx = staged_html.find(RAW_END)
    if start_idx == -1 or end_idx == -1:
        return staged_html
    return staged_html[start_idx + len(RAW_START):end_idx].strip()


class StagingHandler(SimpleHTTPRequestHandler):
    """Serves staging files and handles PUT for saving edits."""

    def __init__(self, *args, **kwargs):
        staging_dir = get_staging_dir()
        staging_dir.mkdir(parents=True, exist_ok=True)
        super().__init__(*args, directory=str(staging_dir), **kwargs)

    def do_PUT(self):
        """Save edited HTML back to staging file."""
        path = unquote(self.path)

        # Only accept /api/staging/{slug}
        if not path.startswith("/api/staging/"):
            self._json_response(404, {"ok": False, "error": "Not found"})
            return

        slug = path[len("/api/staging/"):]
        if not slug or "/" in slug or slug.startswith("."):
            self._json_response(400, {"ok": False, "error": "Invalid slug"})
            return

        # Read request body
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self._json_response(400, {"ok": False, "error": "Empty body"})
            return

        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
            html = data.get("html", "")
        except (json.JSONDecodeError, AttributeError):
            self._json_response(400, {"ok": False, "error": "Invalid JSON"})
            return

        if not html.strip():
            self._json_response(400, {"ok": False, "error": "Empty HTML"})
            return

        # Write wrapped HTML to staging file
        staging_file = get_staging_dir() / f"{slug}.html"
        try:
            wrapped = _wrap_content(html)
            staging_file.write_text(wrapped, encoding="utf-8")
            self._json_response(200, {"ok": True, "slug": slug, "size": len(wrapped)})
        except Exception as e:
            self._json_response(500, {"ok": False, "error": str(e)})

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    def end_headers(self):
        """Add CORS headers to all responses."""
        self._cors_headers()
        super().end_headers()

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json_response(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        """Quieter logging — only show errors and PUTs."""
        msg = format % args
        if "PUT" in msg or "404" in msg or "500" in msg:
            sys.stderr.write(f"[staging] {msg}\n")


def main():
    parser = argparse.ArgumentParser(description="Staging preview server with edit API")
    parser.add_argument("--port", type=int, default=8111, help="Port (default: 8111)")
    args = parser.parse_args()

    staging_dir = get_staging_dir()
    staging_dir.mkdir(parents=True, exist_ok=True)

    HTTPServer.allow_reuse_address = True
    server = HTTPServer(("localhost", args.port), StagingHandler)
    print(f"Staging server running at http://localhost:{args.port}/")
    print(f"Serving: {staging_dir}")
    print(f"Edit API: PUT /api/staging/{{slug}}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
        server.shutdown()


if __name__ == "__main__":
    main()
