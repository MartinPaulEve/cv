"""Behavioural tests for cv.citeproc.CiteProc.

These pin down the transformation logic that turns repository items into
CSL-JSON and formatted CV lines: date handling, title italicisation, open
access status links, and creator/editor mapping. No citeproc server is
involved anywhere here.
"""

from unittest.mock import patch

import pytest

from cv.citeproc import CiteProc


@pytest.fixture
def processor(fake_config, logger):
    return CiteProc(repo=None, config=fake_config, logger=logger)


class TestDates:
    def test_year_extracted_from_iso_date(self):
        assert CiteProc._build_date({"date": "2019-03-01"}) == 2019

    def test_missing_date_yields_no_date_marker(self):
        assert CiteProc._build_date({}) == "n.d."

    def test_unparseable_date_yields_no_date_marker(self):
        assert CiteProc._build_date({"date": "not-a-date"}) == "n.d."

    def test_precise_date_returns_year_month_day(self):
        assert CiteProc._build_precise_date({"date": "2019-03-07"}) == [2019, 3, 7]

    def test_imprecise_date_falls_back_to_year(self):
        assert CiteProc._build_precise_date({"date": "2019"}) == 2019


class TestItalicisation:
    def test_configured_titles_are_wrapped(self, processor):
        item = {"title": "On Gravity's Rainbow and history"}
        processor._italicize_titles(item, "html")
        assert item["title"] == "On <i>Gravity's Rainbow</i> and history"

    def test_disabled_rule_leaves_title_alone(self, processor):
        item = {"title": "On Gravity's Rainbow and history"}
        processor._italicize_titles(item, "pdf")
        assert item["title"] == "On Gravity's Rainbow and history"

    def test_unlisted_title_is_untouched(self, processor):
        item = {"title": "An unrelated title"}
        processor._italicize_titles(item, "html")
        assert item["title"] == "An unrelated title"


class TestOpenAccessStatus:
    def test_gold_item_with_document_gets_link(self, processor):
        item = {
            "title": "x",
            "oa_status": "gold",
            "documents": [{"uri": "https://repo.example/1"}],
        }
        status = processor._build_oa_status(item, "html")
        assert 'href="https://repo.example/1"' in status

    def test_item_without_oa_status_gets_no_link(self, processor):
        assert processor._build_oa_status({"title": "x"}, "html") == ""

    def test_rule_without_oa_config_is_empty(self, processor):
        assert processor._build_oa_status({"title": "x"}, "pdf") == ""

    def test_each_open_document_gets_its_own_link(self, processor):
        item = {
            "title": "x",
            "oa_status": "green",
            "documents": [
                {"uri": "https://repo.example/one", "formatdesc": "Accepted"},
                {"uri": "https://repo.example/two", "formatdesc": "Published"},
            ],
        }

        status = processor._build_oa_status(item, "html")

        assert 'href="https://repo.example/one"' in status
        assert 'href="https://repo.example/two"' in status
        assert "Accepted" in status
        assert "Published" in status

    def test_download_link_names_its_target(self, processor):
        """WCAG 2.4.9: the link's accessible name must identify its target,
        as plain text even when the title carries markup."""
        item = {
            "title": "On <i>Gravity's Rainbow</i> and history",
            "oa_status": "gold",
            "documents": [{"uri": "https://repo.example/1"}],
        }
        status = processor._build_oa_status(item, "html")
        assert "aria-label" in status
        assert "On Gravity's Rainbow and history" in status
        assert "<i>" not in status.split("aria-label")[1].split(">")[0]

    def test_oa_route_is_stated_in_text_not_colour_alone(self, processor):
        """WCAG 1.4.1: gold versus green must not be conveyed by colour
        alone, so the route appears in the accessible name."""
        item = {
            "title": "x",
            "oa_status": "gold",
            "documents": [{"uri": "https://repo.example/1"}],
        }
        assert "gold open access" in processor._build_oa_status(item, "html")

    def test_oa_colours_come_from_configured_palette(self, processor, fake_config):
        """The emitted colour must be the configured AAA-contrast value, not
        the old low-contrast goldenrod/green literals."""
        gold_item = {
            "title": "x",
            "oa_status": "gold",
            "documents": [{"uri": "https://repo.example/1"}],
        }
        green_item = {
            "title": "x",
            "oa_status": "green",
            "documents": [{"uri": "https://repo.example/2"}],
        }
        assert fake_config.oa_colors["gold"] in processor._build_oa_status(
            gold_item, "html"
        )
        assert fake_config.oa_colors["green"] in processor._build_oa_status(
            green_item, "html"
        )


class TestGoldOaLinking:
    def test_gold_oa_uri_replaced_by_official_url(self, processor):
        item = {
            "oa_status": "gold",
            "official_url": "https://doi.org/10.1234/x",
            "uri": "https://repo.example/1",
        }
        processor._link_to_official_url_if_gold_oa(item, "html")
        assert item["uri"] == "https://doi.org/10.1234/x"

    def test_non_gold_item_keeps_repository_uri(self, processor):
        item = {
            "oa_status": "green",
            "official_url": "https://doi.org/10.1234/x",
            "uri": "https://repo.example/1",
        }
        processor._link_to_official_url_if_gold_oa(item, "html")
        assert item["uri"] == "https://repo.example/1"


class TestItemTemplating:
    def test_substitutions_fill_all_placeholders(self):
        line = CiteProc._substitute_item_template(
            template='<p><span>[[year]]</span>[[citeproc]][[oa_status]]</p>',
            citeproc='<div class="csl-entry">Doe, Jane, Book.</div>',
            the_date=2020,
            item={"uri": "https://repo.example/1"},
            oa_status=" [link]",
        )
        assert "2020" in line
        assert "Doe, Jane, Book." in line
        assert " [link]" in line
        # the citeproc div becomes a link to the item
        assert '<a href="https://repo.example/1"' in line
        assert "<div" not in line


class TestSectionFinalisation:
    def test_items_are_wrapped_in_a_list(self, processor):
        """Publication runs must be real lists, not paragraph soup, so that
        assistive technology announces them as navigable lists."""
        section = processor._finalize_section(
            header_template='<h3 class="sectionheader">{0} ({1})</h3>',
            item_count=2,
            output_string="<li>one</li><li>two</li>",
            rule="html",
            section="books",
            section_template='<div id="{0}">{1}</div>',
        )
        assert "<ul" in section
        assert section.index("<ul") < section.index("<li>one</li>")
        assert section.index("<li>two</li>") < section.index("</ul>")
        # the heading sits outside the list
        assert section.index("sectionheader") < section.index("<ul")

    def test_empty_section_produces_no_output(self, processor):
        assert (
            processor._finalize_section(
                header_template="<h3>{0} ({1})</h3>",
                item_count=0,
                output_string="",
                rule="html",
                section="books",
                section_template='<div id="{0}">{1}</div>',
            )
            == ""
        )


class TestSectionRendering:
    def test_section_is_built_from_renderer_output(self, fake_config, logger):
        """The builder converts repository items to CSL-JSON, formats them
        through the injected renderer, and assembles the section: heading
        with a count, one list entry per item, year shown once per group."""

        class FakeRepo:
            def __getattr__(self, name):
                return [
                    {"type": "book", "title": "First", "date": "2020-01-01",
                     "uri": "https://repo.example/1"},
                    {"type": "book", "title": "Second", "date": "2020-06-01",
                     "uri": "https://repo.example/2"},
                ]

        class FakeRenderer:
            def render(self, items, style):
                assert style == "modern-humanities-research-association"
                assert [i["type"] for i in items] == ["book", "book"]
                return [
                    f'<div class="csl-entry">{i["title"]}.</div>' for i in items
                ]

        processor = CiteProc(
            repo=FakeRepo(), config=fake_config, logger=logger,
            renderer=FakeRenderer(),
        )
        section = processor._eprint_substitute("books", "html")

        assert "Books (2)" in section
        assert "First." in section
        assert "Second." in section
        # both items are 2020: the year prefix appears exactly once
        assert section.count(">2020</span>") == 1
        # renderer divs become links to the items
        assert 'href="https://repo.example/1"' in section


class TestConfigTransclusion:
    def test_config_values_are_available_to_templates(self, processor):
        """Templates may transclude configuration values, e.g. the user's
        name in a title, via the {{config:variable}} syntax."""
        template = "<title>{{config:user}}: Curriculum Vitae</title>"
        assert processor._substitute_template(template, "html") == (
            "<title>Jane Doe: Curriculum Vitae</title>"
        )

    def test_config_values_are_html_escaped_and_replaced_literally(
        self, processor, fake_config
    ):
        fake_config.user = 'Jane "JJ" & Doe <\\1>'
        template = '<meta name="description" content="CV of {{config:user}}">'

        assert processor._substitute_template(template, "html") == (
            '<meta name="description" '
            'content="CV of Jane &quot;JJ&quot; &amp; Doe &lt;\\1&gt;">'
        )


class TestTemplateLoading:
    def test_template_contents_returned(self, processor, tmp_path):
        template = tmp_path / "tpl"
        template.write_text("Hello\nWorld\n")
        assert processor._load_template(str(template)) == "Hello\nWorld"

    def test_missing_template_returns_none(self, processor):
        assert processor._load_template("/nonexistent/template") is None


class TestCompleteBuild:
    def test_build_writes_fully_substituted_output(
        self, fake_config, logger, tmp_path
    ):
        template = tmp_path / "template.html"
        destination = tmp_path / "nested" / "cv.html"
        template.write_text("<title>{{config:user}}</title>")
        fake_config.output_rules = {
            "html": [str(template), str(destination)],
        }

        processor = CiteProc(repo=None, config=fake_config, logger=logger)

        assert processor.build(["html"]) is True
        assert destination.read_text() == "<title>Jane Doe</title>"

    def test_failed_post_processing_fails_the_build(
        self, fake_config, logger, tmp_path
    ):
        template = tmp_path / "template.html"
        destination = tmp_path / "cv.html"
        template.write_text("<title>{{config:user}}</title>")
        fake_config.output_rules = {
            "html": [str(template), str(destination), "false"],
        }
        processor = CiteProc(repo=None, config=fake_config, logger=logger)

        with patch("cv.citeproc.subprocess.call", return_value=1):
            assert processor.build(["html"]) is False


class TestPeopleMapping:
    def test_creators_become_csl_authors(self, processor):
        items = {"id1": {}}
        item = {
            "creators": [
                {"name": {"given": "Jane", "family": "Doe"}},
                {"name": {"given": "John", "family": "Smith"}},
            ]
        }
        processor._build_creators("id1", item, items)
        assert items["id1"]["author"] == [
            {"family": "Doe", "given": "Jane"},
            {"family": "Smith", "given": "John"},
        ]

    def test_editors_become_csl_editors(self, processor):
        items = {"id1": {}}
        item = {"editors": [{"name": {"given": "Jane", "family": "Doe"}}]}
        processor._build_editors("id1", item, items)
        assert items["id1"]["editor"] == [{"family": "Doe", "given": "Jane"}]

    def test_item_without_creators_gets_no_author_field(self, processor):
        items = {"id1": {}}
        processor._build_creators("id1", {}, items)
        assert "author" not in items["id1"]
