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
        eprints={"repo": "eprints.example.ac.uk", "user": "Doe=3AJane=3A=3A"},
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
            "html": ' [<a href="[[oa_uri]]" '
            'style="color:[[oa_color]]">Download[[doc]]</a>]'
        },
        non_oa_status={"html": ""},
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
        citeproc_js_server_directory=str(tmp_path),
        citeproc_item_templates={},
        citeproc_item_templates_new_date={},
        citeproc_type_mapper={"books": "book", "articles": "article-journal"},
        citeproc_style={"html": "modern-humanities-research-association"},
        citeproc_server="http://127.0.0.1:{0}",
        citeproc_delay=0,
        citeproc_ports=["8085", "8086"],
    )
