"""Behavioural tests for cv.renderer.CitationRenderer.

The renderer's contract: given CSL-JSON items, return the formatted
bibliography entry for each item, in order, without any server processes.
The node subprocess is mocked throughout, so these tests exercise the
batching, path resolution, caching, and error behaviour only.
"""

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from cv.renderer import CitationRenderer


@pytest.fixture
def renderer(fake_config, logger):
    return CitationRenderer(fake_config, logger)


def fake_run(entries):
    """Build a fake subprocess.run returning the given rendered entries."""

    def _run(*args, **kwargs):
        return SimpleNamespace(
            returncode=0, stdout=json.dumps(entries), stderr=""
        )

    return _run


ITEM_A = {"id": "0-2020", "type": "book", "title": "A"}
ITEM_B = {"id": "1-2019", "type": "book", "title": "B"}


class TestPathResolution:
    def test_style_path_lives_in_the_csl_directory(self, renderer):
        assert renderer.style_path("mhra").endswith("static/csl/mhra.csl")

    def test_locale_path_uses_configured_locale(self, renderer):
        assert renderer.locale_path().endswith("static/csl/locales-en-GB.xml")


class TestRendering:
    def test_entries_are_returned_in_item_order(self, renderer):
        entries = ['<div class="csl-entry">A.</div>', '<div class="csl-entry">B.</div>']
        with patch("cv.renderer.subprocess.run", side_effect=fake_run(entries)):
            result = renderer.render([ITEM_A, ITEM_B], "mhra")
        assert result == entries

    def test_items_are_passed_to_the_subprocess_as_json(self, renderer):
        captured = {}

        def capture(*args, **kwargs):
            captured["input"] = kwargs.get("input")
            return SimpleNamespace(returncode=0, stdout=json.dumps(["x"]), stderr="")

        with patch("cv.renderer.subprocess.run", side_effect=capture):
            renderer.render([ITEM_A], "mhra")

        assert json.loads(captured["input"]) == [ITEM_A]

    def test_empty_input_renders_nothing_and_spawns_nothing(self, renderer):
        with patch("cv.renderer.subprocess.run") as run:
            run.side_effect = AssertionError("should not spawn a process")
            assert renderer.render([], "mhra") == []

    def test_failure_raises_with_stderr_detail(self, renderer):
        def fail(*args, **kwargs):
            return SimpleNamespace(returncode=1, stdout="", stderr="engine exploded")

        with (
            patch("cv.renderer.subprocess.run", side_effect=fail),
            pytest.raises(RuntimeError, match="engine exploded"),
        ):
            renderer.render([ITEM_A], "mhra")


class TestCaching:
    def test_repeat_renders_are_served_from_cache(self, renderer):
        entries = ['<div class="csl-entry">A.</div>']
        with patch("cv.renderer.subprocess.run", side_effect=fake_run(entries)):
            first = renderer.render([ITEM_A], "mhra")

        # a second render of the same item must not need the subprocess
        with patch("cv.renderer.subprocess.run") as run:
            run.side_effect = AssertionError("cache miss: subprocess invoked")
            second = renderer.render([ITEM_A], "mhra")

        assert first == second

    def test_only_uncached_items_are_sent_to_the_subprocess(self, renderer):
        run_a = fake_run(["<div>A</div>"])
        with patch("cv.renderer.subprocess.run", side_effect=run_a):
            renderer.render([ITEM_A], "mhra")

        captured = {}

        def capture(*args, **kwargs):
            captured["input"] = kwargs.get("input")
            return SimpleNamespace(
                returncode=0, stdout=json.dumps(["<div>B</div>"]), stderr=""
            )

        with patch("cv.renderer.subprocess.run", side_effect=capture):
            result = renderer.render([ITEM_A, ITEM_B], "mhra")

        assert json.loads(captured["input"]) == [ITEM_B]
        assert result == ["<div>A</div>", "<div>B</div>"]

    def test_cache_distinguishes_styles(self, renderer):
        run_mhra = fake_run(["<div>A mhra</div>"])
        with patch("cv.renderer.subprocess.run", side_effect=run_mhra):
            renderer.render([ITEM_A], "mhra")

        run_apa = fake_run(["<div>A apa</div>"])
        with patch("cv.renderer.subprocess.run", side_effect=run_apa):
            assert renderer.render([ITEM_A], "apa") == ["<div>A apa</div>"]
