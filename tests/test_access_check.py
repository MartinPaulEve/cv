"""Behavioural tests for cv.access_check.

The gate's contract: check the HTML fragment and the PDF source with
axe-core, verify the PDF's accessibility structure markers, honour the
CV_ACCESSIBILITY_* environment overrides, and return a non-zero exit
code when anything fails. Playwright is mocked in the unit tests; the
browser-marked tests run the real gate end to end.
"""

import os
import re
from unittest.mock import patch

import pytest

from cv import access_check
from cv.accessibility import contrast_ratio
from cv.configuration import PROJECT_ROOT

TAGGED_PDF = (
    b"%PDF-1.7\n"
    b"1 0 obj << /StructTreeRoot 2 0 R /Marked true /Lang (en-GB) "
    b"/Outlines 3 0 R >> endobj\n"
    b"%%EOF\n"
)

CLEAN_AXE_RESULTS = {"violations": [], "passes": [{"id": "document-title"}]}

VIOLATION_AXE_RESULTS = {
    "violations": [
        {
            "impact": "serious",
            "id": "image-alt",
            "help": "Images must have alternate text",
            "nodes": [{"html": "<img src='x.png'>"}],
        }
    ],
    "passes": [],
}


class FakePage:
    def __init__(self, results):
        self.results = results

    def set_content(self, markup, **kwargs):
        pass

    def goto(self, url, **kwargs):
        pass

    def emulate_media(self, **kwargs):
        pass

    def route(self, pattern, handler):
        pass

    def add_script_tag(self, **kwargs):
        pass

    def evaluate(self, expression, arg=None):
        return self.results

    def close(self):
        pass


class FakeBrowser:
    def __init__(self, results):
        self.results = results

    def new_page(self):
        return FakePage(self.results)

    def close(self):
        pass


class FakeChromium:
    def __init__(self, results):
        self.results = results

    def launch(self, **kwargs):
        return FakeBrowser(self.results)


class FakePlaywright:
    def __init__(self, results):
        self.chromium = FakeChromium(results)


class FakeSyncPlaywright:
    def __init__(self, results):
        self.results = results

    def __enter__(self):
        return FakePlaywright(self.results)

    def __exit__(self, *exc_info):
        return False


@pytest.fixture
def artifacts(tmp_path, monkeypatch):
    """Real artifact files on disk, selected via the env overrides."""
    fragment = tmp_path / "fragment.html"
    pdf_source = tmp_path / "pdf-source.html"
    pdf = tmp_path / "cv.pdf"

    fragment.write_text(
        '<section aria-labelledby="works"><h3 id="works">Works</h3>'
        "<ul><li>One work</li></ul></section>"
    )
    pdf_source.write_text(
        '<!DOCTYPE html><html lang="en-GB"><head><meta charset="utf-8">'
        "<title>CV</title></head><body><main>"
        '<section aria-labelledby="works"><h1 id="works">Works</h1>'
        "<ul><li>One work</li></ul></section></main></body></html>"
    )
    pdf.write_bytes(TAGGED_PDF)

    monkeypatch.setenv("CV_ACCESSIBILITY_FRAGMENT", str(fragment))
    monkeypatch.setenv("CV_ACCESSIBILITY_PDF_SOURCE", str(pdf_source))
    monkeypatch.setenv("CV_ACCESSIBILITY_PDF", str(pdf))
    return fragment, pdf_source, pdf


class TestPdfStructure:
    def test_passes_when_all_markers_are_present(self, tmp_path, capsys):
        pdf = tmp_path / "cv.pdf"
        pdf.write_bytes(TAGGED_PDF)

        assert access_check.check_pdf_structure(str(pdf)) == 0
        assert "tagged structure" in capsys.readouterr().out

    def test_fails_and_names_the_missing_markers(self, tmp_path, capsys):
        pdf = tmp_path / "cv.pdf"
        pdf.write_bytes(b"%PDF-1.7\n1 0 obj << /Lang (en-GB) >> endobj\n")

        assert access_check.check_pdf_structure(str(pdf)) == 1
        output = capsys.readouterr()
        assert "/StructTreeRoot" in output.out + output.err
        assert "/Outlines" in output.out + output.err

    def test_reads_non_utf8_pdf_bytes(self, tmp_path):
        pdf = tmp_path / "cv.pdf"
        pdf.write_bytes(b"\xff\xfe binary " + TAGGED_PDF)

        assert access_check.check_pdf_structure(str(pdf)) == 0


class TestGate:
    def test_missing_artifacts_fail_the_gate(self, tmp_path, monkeypatch, capsys):
        missing = str(tmp_path / "does-not-exist.html")
        monkeypatch.setenv("CV_ACCESSIBILITY_FRAGMENT", missing)
        monkeypatch.setenv("CV_ACCESSIBILITY_PDF_SOURCE", missing)
        monkeypatch.setenv("CV_ACCESSIBILITY_PDF", missing)

        assert access_check.main() != 0
        output = capsys.readouterr()
        assert re.search("missing", output.out + output.err, re.IGNORECASE)

    def test_clean_documents_and_tagged_pdf_pass(self, artifacts, capsys):
        with patch.object(
            access_check,
            "sync_playwright",
            lambda: FakeSyncPlaywright(CLEAN_AXE_RESULTS),
        ):
            assert access_check.main() == 0

        output = capsys.readouterr()
        assert "PDF: tagged structure" in output.out
        assert "All WCAG checks passed" in output.out

    def test_axe_violations_fail_the_gate(self, artifacts, capsys):
        with patch.object(
            access_check,
            "sync_playwright",
            lambda: FakeSyncPlaywright(VIOLATION_AXE_RESULTS),
        ):
            assert access_check.main() != 0

        output = capsys.readouterr()
        assert "image-alt" in output.out + output.err

    def test_untagged_pdf_fails_the_gate(self, artifacts, capsys):
        _, _, pdf = artifacts
        pdf.write_bytes(b"%PDF-1.7 flat picture of text\n%%EOF\n")

        with patch.object(
            access_check,
            "sync_playwright",
            lambda: FakeSyncPlaywright(CLEAN_AXE_RESULTS),
        ):
            assert access_check.main() != 0


@pytest.mark.browser
class TestRealBrowser:
    def test_print_links_are_distinguishable_from_body_text(self):
        from playwright.sync_api import sync_playwright

        with open(
            os.path.join(PROJECT_ROOT, "static", "pagedJS", "css", "cv.css")
        ) as css_file:
            css = css_file.read()

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True, args=access_check.BROWSER_ARGS
            )
            try:
                page = browser.new_page()
                page.set_content(
                    f"<style>{css}</style>"
                    '<p>Body <a href="https://example.test">link</a></p>'
                )
                styles = page.eval_on_selector(
                    "a",
                    "(link) => { const computed = getComputedStyle(link); "
                    "return { color: computed.color, "
                    "decoration: computed.textDecorationLine }; }",
                )
            finally:
                browser.close()

        # links must carry a non-colour affordance (WCAG 1.4.1) and meet
        # the AAA 7:1 contrast ratio on white (WCAG 1.4.6); the exact
        # colour is a design choice and deliberately not pinned here
        assert "underline" in styles["decoration"]
        channels = [int(value) for value in re.findall(r"\d+", styles["color"])[:3]]
        link_hex = "#" + "".join(f"{value:02X}" for value in channels)
        assert contrast_ratio(link_hex, "#FFFFFF") >= 7

    def test_full_gate_passes_on_real_artifacts(
        self, tmp_path, monkeypatch, capsys
    ):
        from cv.printpdf import print_pdf

        markup = (
            '<!DOCTYPE html><html lang="en-GB"><head><meta charset="utf-8">'
            "<title>CV</title><script>window.__pagedDone = true;</script>"
            '</head><body><main><section aria-labelledby="works">'
            '<h1 id="works">Works</h1><ul><li>One work</li></ul>'
            "</section></main></body></html>"
        )
        fragment = tmp_path / "fragment.html"
        pdf_source = tmp_path / "pdf-source.html"
        fragment.write_text(
            '<section aria-labelledby="works"><h3 id="works">Works</h3>'
            "<ul><li>One work</li></ul></section>"
        )
        pdf_source.write_text(markup)
        pdf_source_copy = tmp_path / "source.html"
        pdf_source_copy.write_text(markup)
        print_pdf("source.html", "cv.pdf", project_root=str(tmp_path))

        monkeypatch.setenv("CV_ACCESSIBILITY_FRAGMENT", str(fragment))
        monkeypatch.setenv("CV_ACCESSIBILITY_PDF_SOURCE", str(pdf_source))
        monkeypatch.setenv("CV_ACCESSIBILITY_PDF", str(tmp_path / "cv.pdf"))

        assert access_check.main() == 0
        assert "PDF: tagged structure" in capsys.readouterr().out
