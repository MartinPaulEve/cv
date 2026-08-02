"""Behavioural tests for cv.printpdf.

The printer's contract: serve the project root over loopback, load the
given HTML document in headless Chromium, wait for Paged.js to finish,
and write a tagged PDF to the given destination. Playwright is mocked
in the unit tests; the loopback file server is exercised for real. The
browser-marked test prints a real (tiny) document to a tagged PDF.
"""

import urllib.error
import urllib.request
from unittest.mock import patch

import pytest

from cv import printpdf


class FakePage:
    def __init__(self, recorder):
        self.recorder = recorder

    def goto(self, url, **kwargs):
        self.recorder["url"] = url

    def wait_for_function(self, expression, **kwargs):
        self.recorder["waited_for"] = expression

    def pdf(self, path=None, **kwargs):
        with open(path, "wb") as pdf_file:
            pdf_file.write(b"%PDF-fake")
        self.recorder["pdf_path"] = path


class FakeBrowser:
    def __init__(self, recorder):
        self.recorder = recorder

    def new_page(self):
        return FakePage(self.recorder)

    def close(self):
        pass


class FakeChromium:
    def __init__(self, recorder):
        self.recorder = recorder

    def launch(self, **kwargs):
        return FakeBrowser(self.recorder)


class FakePlaywright:
    def __init__(self, recorder):
        self.chromium = FakeChromium(recorder)


class FakeSyncPlaywright:
    def __init__(self, recorder):
        self.recorder = recorder

    def __enter__(self):
        return FakePlaywright(self.recorder)

    def __exit__(self, *exc_info):
        return False


@pytest.fixture
def project(tmp_path):
    """A miniature project root with an output document to print."""
    (tmp_path / "output").mkdir()
    (tmp_path / "output" / "cv.html").write_text(
        "<!DOCTYPE html><html lang='en'><body>CV</body></html>"
    )
    return tmp_path


class TestServeProject:
    def test_serves_files_from_the_project_root(self, project):
        server = printpdf.serve_project(project)
        try:
            port = server.server_address[1]
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/output/cv.html"
            ) as response:
                body = response.read().decode("utf-8")
            assert "CV" in body
        finally:
            server.shutdown()
            server.server_close()

    def test_unknown_paths_return_404(self, project):
        server = printpdf.serve_project(project)
        try:
            port = server.server_address[1]
            with pytest.raises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/no-such-file")
            assert error.value.code == 404
        finally:
            server.shutdown()
            server.server_close()

    def test_paths_cannot_escape_the_project_root(self, tmp_path):
        secret = tmp_path / "secret.txt"
        secret.write_text("do not serve this")
        root = tmp_path / "root"
        root.mkdir()

        server = printpdf.serve_project(root)
        try:
            port = server.server_address[1]
            for attempt in ("/../secret.txt", "/%2e%2e/secret.txt"):
                try:
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}{attempt}"
                    ) as response:
                        assert "do not serve this" not in response.read().decode(
                            "utf-8", "replace"
                        )
                except urllib.error.HTTPError:
                    pass
        finally:
            server.shutdown()
            server.server_close()


class TestPrintPdf:
    def test_writes_the_pdf_to_the_requested_destination(self, project):
        recorder = {}
        with patch.object(
            printpdf, "sync_playwright", lambda: FakeSyncPlaywright(recorder)
        ):
            written = printpdf.print_pdf(
                "output/cv.html", "output/cv.pdf", project_root=str(project)
            )

        assert written == str(project / "output" / "cv.pdf")
        assert (project / "output" / "cv.pdf").read_bytes() == b"%PDF-fake"

    def test_loads_the_document_over_loopback_http(self, project):
        recorder = {}
        with patch.object(
            printpdf, "sync_playwright", lambda: FakeSyncPlaywright(recorder)
        ):
            printpdf.print_pdf(
                "output/cv.html", "output/cv.pdf", project_root=str(project)
            )

        assert recorder["url"].startswith("http://127.0.0.1:")
        assert recorder["url"].endswith("/output/cv.html")

    def test_waits_for_paged_js_to_finish(self, project):
        recorder = {}
        with patch.object(
            printpdf, "sync_playwright", lambda: FakeSyncPlaywright(recorder)
        ):
            printpdf.print_pdf(
                "output/cv.html", "output/cv.pdf", project_root=str(project)
            )

        assert "window.__pagedDone === true" in recorder["waited_for"]


class TestRun:
    def test_missing_arguments_are_a_usage_error(self):
        with patch.object(printpdf, "print_pdf") as print_pdf:
            assert printpdf.run([]) == 2
            assert printpdf.run(["output/only-one.html"]) == 2

        print_pdf.assert_not_called()

    def test_positional_arguments_select_the_documents(self):
        with patch.object(printpdf, "print_pdf") as print_pdf:
            printpdf.run(["output/a.html", "output/a.pdf"])

        assert print_pdf.call_args.args == ("output/a.html", "output/a.pdf")


@pytest.mark.browser
class TestRealBrowser:
    def test_prints_a_tagged_pdf(self, tmp_path):
        (tmp_path / "page.html").write_text(
            "<!DOCTYPE html><html lang='en'><head><title>T</title>"
            "<script>window.__pagedDone = true;</script></head>"
            "<body><h1>Heading</h1><p>Body</p></body></html>"
        )

        written = printpdf.print_pdf(
            "page.html", "out.pdf", project_root=str(tmp_path)
        )

        contents = (tmp_path / "out.pdf").read_bytes()
        assert written == str(tmp_path / "out.pdf")
        assert contents.startswith(b"%PDF")
        assert b"/StructTreeRoot" in contents
