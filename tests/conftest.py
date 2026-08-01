"""Shared fixtures for the cv test suite.

Every test runs against a synthetic configuration object and synthetic
publication data: no test touches the network or a real repository.
"""

import logging
from types import SimpleNamespace

import pytest


@pytest.fixture
def logger():
    """A quiet logger for passing into the classes under test."""
    log = logging.getLogger("cv-tests")
    log.addHandler(logging.NullHandler())
    log.propagate = False
    return log


@pytest.fixture
def fake_config(tmp_path):
    """A minimal configuration namespace mirroring the real config module.

    Storage paths point into a per-test temporary directory so tests can
    freely read and write cached JSON without touching the working tree.
    """
    data = tmp_path / "data"
    data.mkdir()

    return SimpleNamespace(
        user="Jane Doe",
        emails=["jane@example.com"],
        orcid="0000-0000-0000-0000",
        eprints={"repo": "eprints.example.ac.uk"},
        section_headings={
            "html": {"books": "Books", "articles": "Articles"},
            "pdf": {"books": "BOOKS", "articles": "ARTICLES"},
        },
        peer_reviewed={
            "books": "ANY",
            "edited_books": "ANY",
            "articles": True,
            "other_articles": False,
            "reviews": "ANY",
        },
        editorial={
            "books": False,
            "edited_books": True,
            "articles": "ANY",
            "other_articles": "ANY",
            "reviews": "ANY",
        },
        review_of="Review of",
        book_review={
            "reviews": True,
            "articles": False,
            "books": "ANY",
            "edited_books": "ANY",
            "other_articles": "ANY",
        },
        eprints_db={
            "books": "book",
            "edited_books": "book",
            "articles": "article",
            "other_articles": "article",
            "reviews": "article",
        },
        storage={
            "json": str(data / "eprints.json"),
            "books": str(data / "books.json"),
            "edited_books": str(data / "edited_books.json"),
            "articles": str(data / "articles.json"),
            "other_articles": str(data / "other_articles.json"),
            "reviews": str(data / "reviews.json"),
        },
        default_types=["books", "articles"],
        output_rules={},
        section_template={"html": '<div id="{0}">{1}</div>'},
        header_template={"html": '<h3 class="sectionheader">{0} ({1})</h3>'},
        gold_oa_direct_link={"html": True, "pdf": True},
        email="jane@example.com",
        oa_status={
            "html": ' [<a href="[[oa_uri]]" style="color:[[oa_color]]" '
            'aria-label="Download the [[oa_route]] open access version of '
            '[[title]]">Download[[doc]]</a>]'
        },
        non_oa_status={"html": ""},
        oa_colors={"gold": "#6B5300", "green": "#175117"},
        list_template={
            "html": '<ul class="publist" '
            'style="list-style:none;margin:0;padding:0">{0}</ul>'
        },
        exclude_venues={"html": {}},
        italicize_titles={"html": True, "pdf": False},
        titles_to_italicize=["Gravity's Rainbow", "2666"],
        creators_item_name="creators",
        creator_field_top_level="name",
        creator_field_given_name="given",
        creator_field_last_name="family",
        editors_item_name="editors",
        editor_field_top_level="name",
        editor_field_given_name="given",
        editor_field_last_name="family",
        citeproc_item_templates={
            "html": {
                "books": '<li class="anitem"><span class="bibitem">'
                "[[citeproc]] [[oa_status]]</span></li>"
            }
        },
        citeproc_item_templates_new_date={
            "html": {
                "books": '<li class="anitemnewdate"><span class="prefix" '
                'aria-hidden="true">[[year]]</span><span class="bibitem">'
                "[[citeproc]] [[oa_status]]</span></li>"
            }
        },
        citeproc_type_mapper={"books": "book", "articles": "article-journal"},
        citeproc_style={"html": "modern-humanities-research-association"},
        csl_directory="static/csl",
        citeproc_locale="en-GB",
    )
