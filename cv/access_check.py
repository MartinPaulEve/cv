"""Run axe-core WCAG checks over the generated CV outputs, headlessly.

Two documents are checked:

 1. the configured HTML fragment that is transcluded into a website. It
    is wrapped in a minimal page scaffold here, because a fragment alone
    has no lang or title of its own to test.
 2. the configured print source document. Paged.js is blocked during the
    check so that axe sees the semantic source rather than the paginated
    layout boxes.

A third check reads the generated PDF itself and verifies that it
carries tagging, language, and outline structures.

The gate exits non-zero if any WCAG rule (A, AA, or AAA) is violated, so
it can act as a gate in local runs and CI.
"""

import os
import sys

from playwright.sync_api import sync_playwright

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AXE_PATH = os.path.join(PROJECT_ROOT, "static", "js", "axe.min.js")

WCAG_TAGS = [
    "wcag2a",
    "wcag2aa",
    "wcag2aaa",
    "wcag21a",
    "wcag21aa",
    "wcag22a",
    "wcag22aa",
    "best-practice",
]

# sandbox flags: see the note in cv/printpdf.py — only local generated
# content is ever loaded
BROWSER_ARGS = ["--no-sandbox", "--disable-setuid-sandbox"]

PDF_MARKERS = ["/StructTreeRoot", "/Marked true", "/Lang", "/Outlines"]

_RUN_AXE = (
    "async (tags) => await window.axe.run(document, "
    "{ runOnly: { type: 'tag', values: tags } })"
)


def _artifact_paths():
    """Resolve the three artifact paths, honouring the env overrides."""
    fragment = os.environ.get("CV_ACCESSIBILITY_FRAGMENT") or os.path.join(
        PROJECT_ROOT, "output", "martin_paul_eve-Eve-CV.html"
    )
    pdf_source = os.environ.get("CV_ACCESSIBILITY_PDF_SOURCE") or os.path.join(
        PROJECT_ROOT, "output", "martin_paul_eve-Eve-CV-PDF.html"
    )
    pdf = os.environ.get("CV_ACCESSIBILITY_PDF") or os.path.join(
        PROJECT_ROOT, "output", "martin_paul_eve-Eve-CV.pdf"
    )

    return os.path.abspath(fragment), os.path.abspath(pdf_source), os.path.abspath(pdf)


def check_pdf_structure(pdf_path):
    """
    Verify that a PDF carries tagging, language, and outline markers
    :param pdf_path: the path of the PDF to inspect
    :return: the number of failed checks (0 or 1)
    """
    with open(pdf_path, "rb") as pdf_file:
        contents = pdf_file.read().decode("latin-1")

    missing = [marker for marker in PDF_MARKERS if marker not in contents]

    if missing:
        print(
            f"PDF is missing accessibility structure: {', '.join(missing)}",
            file=sys.stderr,
        )
        return 1

    print("PDF: tagged structure, language, and outline present")
    return 0


def _check_page(browser, label, load):
    """Run axe over one document; return its violation count."""
    page = browser.new_page()
    load(page)
    page.add_script_tag(path=AXE_PATH)

    results = page.evaluate(_RUN_AXE, WCAG_TAGS)

    page.close()

    print(
        f"{label}: {len(results['violations'])} violation(s), "
        f"{len(results['passes'])} rule(s) passed"
    )

    for violation in results["violations"]:
        print(f"  [{violation['impact']}] {violation['id']}: {violation['help']}")
        for node in violation["nodes"][:5]:
            print(f"    {node['html'][:160]}")

    return len(results["violations"])


def _load_fragment(page, fragment):
    """Wrap the HTML fragment in a minimal page scaffold and load it."""
    with open(fragment) as fragment_file:
        markup = fragment_file.read()

    scaffold = (
        '<!DOCTYPE html><html lang="en-GB"><head><meta charset="utf-8">'
        "<title>Publications</title></head><body><main>"
        "<h1>Publications</h1><h2>Section scaffold</h2>" + markup +
        "</main></body></html>"
    )
    page.set_content(scaffold, wait_until="load")


def _load_pdf_source(page, pdf_source):
    """Load the print source with Paged.js and remote fonts blocked."""
    # blocking Paged.js and remote fonts lets axe see the source
    # semantics under the same white-page print styles used for PDF
    # generation
    page.emulate_media(media="print")

    def block_pagination(route, request):
        if "pagedjs" in request.url or "typekit" in request.url:
            route.abort()
        else:
            route.continue_()

    page.route("**/*", block_pagination)
    page.goto("file://" + pdf_source, wait_until="load")


def main():
    """Run the full accessibility gate; return the process exit code."""
    fragment, pdf_source, pdf = _artifact_paths()

    missing = [
        artifact
        for artifact in (fragment, pdf_source, pdf)
        if not os.path.exists(artifact)
    ]
    if missing:
        for artifact in missing:
            print(
                f"Expected accessibility artifact is missing: {artifact}",
                file=sys.stderr,
            )
        return 1

    violations = 0

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=BROWSER_ARGS)

        try:
            violations += _check_page(
                browser,
                "HTML fragment",
                lambda page: _load_fragment(page, fragment),
            )
            violations += _check_page(
                browser,
                "PDF source",
                lambda page: _load_pdf_source(page, pdf_source),
            )
            violations += check_pdf_structure(pdf)
        finally:
            browser.close()

    if violations > 0:
        print(f"\nFAILED: {violations} WCAG violation(s) found", file=sys.stderr)
        return 1

    print("\nAll WCAG checks passed")
    return 0


def run():
    """Console entry point: cv-check-access"""
    sys.exit(main())
