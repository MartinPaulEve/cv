"""Print the Paged.js-rendered CV to a tagged, accessible PDF.

This runs fully headless: the generated HTML is served from disk over a
loopback-only HTTP server (Paged.js loads its stylesheets with fetch(),
which browsers refuse on file:// URLs), the page waits for Paged.js to
signal that pagination has finished (via the window.PagedConfig `after`
hook set in the template), and Chromium produces a tagged PDF with a
document outline, so that the result carries the heading/list/link
structure that assistive technology needs, rather than being a flat
picture of text.

Usage: cv-print <input.html> <output.pdf>
Paths are relative to the project root.
"""

import os
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from playwright.sync_api import sync_playwright

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# the sandbox flags are needed on Linux distributions that restrict
# unprivileged user namespaces; the browser only ever loads our own
# generated files, so this does not process untrusted content
BROWSER_ARGS = ["--no-sandbox", "--disable-setuid-sandbox"]

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css",
    ".js": "text/javascript",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}


class _ProjectRequestHandler(SimpleHTTPRequestHandler):
    """A quiet file handler with the project's MIME map."""

    extensions_map = MIME_TYPES

    def log_message(self, format, *args):  # noqa: A002 - stdlib signature
        pass


def serve_project(root):
    """
    Serve root on a loopback-only ephemeral port
    :param root: the directory to serve
    :return: the running server; the caller must shut it down
    """
    handler = partial(_ProjectRequestHandler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    return server


def print_pdf(input_html, output_pdf, project_root=PROJECT_ROOT):
    """
    Print a Paged.js HTML document to a tagged PDF
    :param input_html: the HTML document path, relative to the project root
    :param output_pdf: the destination PDF path
    :param project_root: the directory to serve the document from
    :return: the absolute path of the written PDF
    """
    output_path = os.path.join(project_root, output_pdf)
    server = serve_project(project_root)
    port = server.server_address[1]

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True, args=BROWSER_ARGS
            )

            try:
                page = browser.new_page()
                document_path = input_html.replace(os.sep, "/").lstrip("/")
                page.goto(
                    f"http://127.0.0.1:{port}/{document_path}",
                    wait_until="networkidle",
                    timeout=60000,
                )

                # wait for Paged.js to finish laying out the document
                page.wait_for_function(
                    "window.__pagedDone === true", timeout=120000
                )

                page.pdf(
                    path=output_path,
                    tagged=True,
                    outline=True,
                    prefer_css_page_size=True,
                    print_background=True,
                )
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()

    print(f"Wrote tagged PDF to {output_path}")

    return output_path


def run(argv=None):
    """Console entry point: cv-print <input.html> <output.pdf>"""
    argv = sys.argv[1:] if argv is None else argv

    if len(argv) < 2:
        print("usage: cv-print <input.html> <output.pdf>", file=sys.stderr)
        return 2

    print_pdf(argv[0], argv[1])
