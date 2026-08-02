"""Behavioural tests for cv.renderer.

The renderer's contract: given CSL-JSON items, return the formatted
bibliography entry for each item, in order, without any external
processes. The embedded citeproc-js engine is mocked for the batching,
path resolution, caching, and error tests; a small set of integration
tests runs the real vendored engine, which is pure in-process compute.
"""

import json
import os
from unittest.mock import patch

import pytest

from cv.renderer import PROJECT_ROOT, CitationRenderer, CiteprocEngine

GOLDEN_PATH = os.path.join(os.path.dirname(__file__), "golden_citations.json")


@pytest.fixture
def renderer(fake_config, logger):
    return CitationRenderer(fake_config, logger)


class FakeEngine:
    """A stand-in engine returning canned entries, one per item."""

    def __init__(self, entries_by_id):
        self.entries_by_id = entries_by_id
        self.rendered = []

    def render(self, items, link_titles=False):
        self.rendered.append([dict(item) for item in items])
        return [self.entries_by_id[item["id"]] for item in items]


def fake_engine_factory(entries_by_id, created=None):
    """Build a CiteprocEngine replacement ignoring construction args."""

    def _factory(style_path, locale_path):
        engine = FakeEngine(entries_by_id)
        if created is not None:
            created.append((style_path, locale_path, engine))
        return engine

    return _factory


ITEM_A = {"id": "0-2020", "type": "book", "title": "A"}
ITEM_B = {"id": "1-2019", "type": "book", "title": "B"}


class TestPathResolution:
    def test_style_path_lives_in_the_csl_directory(self, renderer):
        assert renderer.style_path("mhra").endswith("static/csl/mhra.csl")

    def test_locale_path_uses_configured_locale(self, renderer):
        assert renderer.locale_path().endswith("static/csl/locales-en-GB.xml")


class TestRendering:
    def test_entries_are_returned_in_item_order(self, renderer):
        entries = {
            "0-2020": '<div class="csl-entry">A.</div>',
            "1-2019": '<div class="csl-entry">B.</div>',
        }
        with patch(
            "cv.renderer.CiteprocEngine",
            side_effect=fake_engine_factory(entries),
        ):
            result = renderer.render([ITEM_A, ITEM_B], "mhra")

        assert result == [entries["0-2020"], entries["1-2019"]]

    def test_engine_is_built_from_the_configured_style_and_locale(self, renderer):
        created = []
        with patch(
            "cv.renderer.CiteprocEngine",
            side_effect=fake_engine_factory({"0-2020": "<div>A</div>"}, created),
        ):
            renderer.render([ITEM_A], "mhra")

        style_path, locale_path, _ = created[0]
        assert style_path.endswith("static/csl/mhra.csl")
        assert locale_path.endswith("static/csl/locales-en-GB.xml")

    def test_empty_input_renders_nothing_and_builds_no_engine(self, renderer):
        with patch("cv.renderer.CiteprocEngine") as engine:
            engine.side_effect = AssertionError("should not build an engine")
            assert renderer.render([], "mhra") == []

    def test_engine_failure_raises_a_runtime_error_with_detail(self, renderer):
        def explode(style_path, locale_path):
            raise ValueError("engine exploded")

        with (
            patch("cv.renderer.CiteprocEngine", side_effect=explode),
            pytest.raises(RuntimeError, match="engine exploded"),
        ):
            renderer.render([ITEM_A], "mhra")


class TestCaching:
    def test_repeat_renders_are_served_from_cache(self, renderer):
        entries = {"0-2020": '<div class="csl-entry">A.</div>'}
        with patch(
            "cv.renderer.CiteprocEngine",
            side_effect=fake_engine_factory(entries),
        ):
            first = renderer.render([ITEM_A], "mhra")

        # a second render of the same item must not need any engine
        with patch("cv.renderer.CiteprocEngine") as engine:
            engine.side_effect = AssertionError("cache miss: engine invoked")
            second = renderer.render([ITEM_A], "mhra")

        assert first == second

    def test_only_uncached_items_are_rendered(self, renderer):
        created = []
        entries = {"0-2020": "<div>A</div>", "1-2019": "<div>B</div>"}
        with patch(
            "cv.renderer.CiteprocEngine",
            side_effect=fake_engine_factory(entries, created),
        ):
            renderer.render([ITEM_A], "mhra")
            result = renderer.render([ITEM_A, ITEM_B], "mhra")

        assert result == ["<div>A</div>", "<div>B</div>"]
        # every batch handed to an engine after the first render contains
        # only the item that was not already cached
        later_batches = [
            batch for _, _, engine in created for batch in engine.rendered
        ][1:]
        for batch in later_batches:
            assert [item["id"] for item in batch] == ["1-2019"]

    def test_cache_distinguishes_styles(self, renderer):
        with patch(
            "cv.renderer.CiteprocEngine",
            side_effect=fake_engine_factory({"0-2020": "<div>A mhra</div>"}),
        ):
            renderer.render([ITEM_A], "mhra")

        with patch(
            "cv.renderer.CiteprocEngine",
            side_effect=fake_engine_factory({"0-2020": "<div>A apa</div>"}),
        ):
            assert renderer.render([ITEM_A], "apa") == ["<div>A apa</div>"]


@pytest.fixture
def real_config(fake_config):
    """Point the fake configuration at the real vendored CSL assets."""
    fake_config.csl_directory = os.path.join(PROJECT_ROOT, "static", "csl")
    fake_config.citeproc_locale = "en-GB"
    return fake_config


class TestRealEngine:
    """Integration: the vendored citeproc-js on the embedded V8 engine."""

    def test_vendored_assets_render_a_real_citation(self, real_config, logger):
        renderer = CitationRenderer(real_config, logger)
        entries = renderer.render(
            [
                {
                    "id": "work-1",
                    "type": "book",
                    "title": "A Test Title",
                    "author": [{"family": "Doe", "given": "Jane"}],
                    "issued": {"date-parts": [[2024]]},
                }
            ],
            "modern-humanities-research-association",
        )

        assert len(entries) == 1
        assert "Doe" in entries[0]
        assert "A Test Title" in entries[0]

    def test_output_matches_the_node_toolchain_golden(self, real_config, logger):
        with open(GOLDEN_PATH) as golden_file:
            golden = json.load(golden_file)

        renderer = CitationRenderer(real_config, logger)
        entries = renderer.render(golden["items"], golden["style"])

        assert entries == golden["expected"]

    def test_repeated_authors_are_never_replaced_with_em_dashes(
        self, real_config, logger
    ):
        renderer = CitationRenderer(real_config, logger)
        items = [
            {
                "id": f"work-{year}",
                "type": "book",
                "title": f"Book of {year}",
                "author": [{"family": "Doe", "given": "Jane"}],
                "issued": {"date-parts": [[year]]},
            }
            for year in (2023, 2024)
        ]

        entries = renderer.render(
            items, "modern-humanities-research-association"
        )

        # every entry must carry its author: rendering the items together
        # in one bibliography would substitute the repeated name with an
        # em-dash, which is wrong for a CV
        for entry in entries:
            assert "Doe" in entry
            assert "———" not in entry

    def test_one_engine_renders_successive_batches(self, real_config, logger):
        engine = CiteprocEngine(
            os.path.join(
                real_config.csl_directory,
                "modern-humanities-research-association.csl",
            ),
            os.path.join(real_config.csl_directory, "locales-en-GB.xml"),
        )

        def book(identifier, title):
            return {
                "id": identifier,
                "type": "book",
                "title": title,
                "author": [{"family": "Doe", "given": "Jane"}],
                "issued": {"date-parts": [[2024]]},
            }

        first = engine.render([book("0-2024", "First")])
        # the same positional id must not leak the earlier item's content
        second = engine.render([book("0-2024", "Second")])

        assert "First" in first[0]
        assert "Second" in second[0]


class TestTitleLinks:
    """Integration: linking only the title via the variableWrapper hook."""

    ITEM = {
        "id": "linked-1",
        "type": "book",
        "title": "A Test Title",
        "author": [{"family": "Doe", "given": "Jane"}],
        "issued": {"date-parts": [[2024]]},
        "link": "https://repo.example/1?a=1&b=2",
    }

    STYLE = "modern-humanities-research-association"

    def test_title_mode_links_only_the_title(self, real_config, logger):
        renderer = CitationRenderer(real_config, logger)
        [entry] = renderer.render([self.ITEM], self.STYLE, link_titles=True)

        assert (
            '<a href="https://repo.example/1?a=1&amp;b=2">'
            "<i>A Test Title</i></a>" in entry
        )
        # the author stays outside the anchor
        assert entry.count("<a ") == 1
        assert "Doe, Jane, <a" in entry

    def test_entry_mode_renders_no_anchor(self, real_config, logger):
        renderer = CitationRenderer(real_config, logger)
        [entry] = renderer.render([self.ITEM], self.STYLE)

        assert "<a " not in entry

    def test_item_without_a_link_gets_no_anchor(self, real_config, logger):
        renderer = CitationRenderer(real_config, logger)
        item = {key: value for key, value in self.ITEM.items() if key != "link"}
        [entry] = renderer.render([item], self.STYLE, link_titles=True)

        assert "<a " not in entry

    def test_cache_distinguishes_link_modes(self, real_config, logger):
        renderer = CitationRenderer(real_config, logger)
        [linked] = renderer.render([self.ITEM], self.STYLE, link_titles=True)
        [plain] = renderer.render([self.ITEM], self.STYLE)

        assert "<a " in linked
        assert "<a " not in plain
