"""Behavioural tests for cv.citeproc.CiteProc.

These pin down the transformation logic that turns repository items into
CSL-JSON and formatted CV lines: date handling, title italicisation, open
access status links, and creator/editor mapping. No citeproc server is
involved anywhere here.
"""

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
        assert "goldenrod" in status

    def test_green_item_keeps_green_colour(self, processor):
        item = {
            "title": "x",
            "oa_status": "green",
            "documents": [{"uri": "https://repo.example/2"}],
        }
        status = processor._build_oa_status(item, "html")
        assert "green" in status

    def test_item_without_oa_status_gets_no_link(self, processor):
        assert processor._build_oa_status({"title": "x"}, "html") == ""

    def test_rule_without_oa_config_is_empty(self, processor):
        assert processor._build_oa_status({"title": "x"}, "pdf") == ""


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


class TestTemplateLoading:
    def test_template_contents_returned(self, processor, tmp_path):
        template = tmp_path / "tpl"
        template.write_text("Hello\nWorld\n")
        assert processor._load_template(str(template)) == "Hello\nWorld"

    def test_missing_template_returns_none(self, processor):
        assert processor._load_template("/nonexistent/template") is None


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
