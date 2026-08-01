"""Behavioural tests for the InvenioRDM (KC Works) metadata source.

These pin down the two responsibilities of the source: finding all of a
scholar's records (name query plus ORCID query, unioned, paginated) and
normalising InvenioRDM records into the internal eprints-style item shape
that the rest of the pipeline consumes. All HTTP is mocked; the sample
records mirror real KC Works responses.
"""

from unittest.mock import patch

import pytest

from cv.invenio import InvenioSource


@pytest.fixture
def source(fake_config, logger):
    fake_config.invenio = {"api": "https://works.example.org/api/records"}
    return InvenioSource(fake_config, logger)


BOOK_RECORD = {
    "id": "3a3dz-qgg11",
    "pids": {"doi": {"identifier": "10.17613/11px-b370"}},
    "access": {"status": "open"},
    "files": {
        "enabled": True,
        "entries": {
            "eve-warez.pdf": {
                "mimetype": "application/pdf",
                "links": {
                    "content": "https://works.example.org/api/records/"
                    "3a3dz-qgg11/files/eve-warez.pdf/content"
                },
            }
        },
    },
    "metadata": {
        "resource_type": {"id": "textDocument-book"},
        "title": "Warez: The Infrastructure and Aesthetics of Piracy",
        "publisher": "punctum books",
        "publication_date": "2021",
        "identifiers": [
            {"identifier": "hc:43559", "scheme": "hclegacy-pid"},
            {"identifier": "10.53288/0339.1.00", "scheme": "doi"},
        ],
        "creators": [
            {
                "person_or_org": {
                    "type": "personal",
                    "name": "Eve, Martin Paul",
                    "given_name": "Martin Paul",
                    "family_name": "Eve",
                }
            }
        ],
    },
}

ARTICLE_RECORD = {
    "id": "0wff1-yf212",
    "pids": {"doi": {"identifier": "10.17613/xyz"}},
    "access": {"status": "metadata-only"},
    "metadata": {
        "resource_type": {"id": "textDocument-journalArticle"},
        "title": "An Article",
        "publication_date": "2014-05-01",
        "creators": [
            {
                "person_or_org": {
                    "type": "personal",
                    "name": "Doe, Jane",
                    "given_name": "Jane",
                    "family_name": "Doe",
                }
            }
        ],
    },
    "custom_fields": {
        "journal:journal": {
            "title": "C21 Literature",
            "volume": "6",
            "issue": "3",
            "pages": "1-20",
        }
    },
}

CHAPTER_RECORD = {
    "id": "qta93-d3896",
    "pids": {},
    "access": {"status": "open"},
    "metadata": {
        "resource_type": {"id": "textDocument-bookSection"},
        "title": "A Chapter",
        "publication_date": "2019",
        "creators": [],
    },
    "custom_fields": {
        "imprint:imprint": {"title": "A Container Book", "pages": "61-62"}
    },
}

ZENODO_ARTICLE_RECORD = {
    "id": "8434828",
    "pids": {"doi": {"identifier": "10.5281/zenodo.8434828"}},
    "access": {"status": "open"},
    "links": {
        "self_html": "https://zenodo.org/records/8434828",
        "files": "https://zenodo.org/api/records/8434828/files",
    },
    "files": {
        "enabled": True,
        "entries": {
            "article manuscript.pdf": {
                "key": "article manuscript.pdf",
                "mimetype": "application/pdf",
                "access": {"hidden": False},
            }
        },
    },
    "metadata": {
        "resource_type": {"id": "publication-article"},
        "title": "A Zenodo Article",
        "publication_date": "2024-05-01",
        "creators": [
            {
                "person_or_org": {
                    "type": "personal",
                    "name": "Doe, Jane",
                    "given_name": "Jane",
                    "family_name": "Doe",
                }
            }
        ],
    },
}

BLOG_RECORD = {
    "id": "zzzzz-00001",
    "pids": {},
    "access": {"status": "open"},
    "metadata": {
        "resource_type": {"id": "textDocument-blogPost"},
        "title": "A Blog Post",
        "publication_date": "2020",
        "creators": [],
    },
}


class TestQueries:
    def test_creator_query_uses_family_comma_given(self, source):
        assert (
            source.creator_query()
            == 'metadata.creators.person_or_org.name:"Doe, Jane"'
        )

    def test_orcid_query_uses_configured_orcid(self, source):
        assert source.orcid_query() == (
            "metadata.creators.person_or_org.identifiers.identifier:"
            '"0000-0000-0000-0000"'
        )


class TestNormalisation:
    def test_book_record(self, source):
        item = source.normalise(BOOK_RECORD)

        assert item["type"] == "book"
        assert item["title"] == "Warez: The Infrastructure and Aesthetics of Piracy"
        assert item["date"] == "2021"
        assert item["publisher"] == "punctum books"
        # the publisher's DOI (an alternate identifier) is preferred as the
        # main DOI for cross-repository matching; the minted DOI is kept
        assert item["doi"] == "10.53288/0339.1.00"
        assert "10.17613/11px-b370" in item["alternate_dois"]
        assert item["creators"] == [
            {"name": {"given": "Martin Paul", "family": "Eve"}}
        ]
        assert item["refereed"] == "TRUE"
        # open files become download links
        assert item["oa_status"] == "green"
        assert item["documents"][0]["uri"].endswith("eve-warez.pdf/content")
        # the record page is the item's landing URI
        assert item["uri"] == "https://works.example.org/records/3a3dz-qgg11"

    def test_journal_article_record(self, source):
        item = source.normalise(ARTICLE_RECORD)

        assert item["type"] == "article"
        assert item["publication"] == "C21 Literature"
        assert item["volume"] == "6"
        assert item["number"] == "3"
        assert item["pagerange"] == "1-20"
        assert item["doi"] == "10.17613/xyz"
        # metadata-only records offer no download
        assert "documents" not in item

    def test_chapter_record_gets_its_container(self, source):
        item = source.normalise(CHAPTER_RECORD)

        assert item["type"] == "book_section"
        assert item["book_title"] == "A Container Book"
        assert item["pagerange"] == "61-62"

    def test_unmapped_resource_type_is_skipped(self, source):
        assert source.normalise(BLOG_RECORD) is None

    def test_zenodo_inveniordm_record_uses_portable_types_and_file_links(
        self, source
    ):
        item = source.normalise(ZENODO_ARTICLE_RECORD)

        assert item["type"] == "article"
        assert item["uri"] == "https://zenodo.org/records/8434828"
        assert item["documents"] == [
            {
                "uri": "https://zenodo.org/api/records/8434828/files/"
                "article%20manuscript.pdf/content"
            }
        ]


class TestFetching:
    def _page(self, records, next_url=None):
        payload = {
            "hits": {"hits": records, "total": len(records)},
            "links": {"next": next_url} if next_url else {},
        }
        return payload

    def test_fetch_unions_name_and_orcid_results_by_id(self, source):
        """The name and ORCID queries overlap; each record appears once."""

        def fake_get(url, **kwargs):
            query = kwargs.get("params", {}).get("q", "")

            class Response:
                status_code = 200

                def json(self):
                    if "identifiers.identifier" in query:
                        return {
                            "hits": {"hits": [BOOK_RECORD, ARTICLE_RECORD]},
                            "links": {},
                        }
                    return {
                        "hits": {"hits": [BOOK_RECORD, CHAPTER_RECORD]},
                        "links": {},
                    }

                def raise_for_status(self):
                    pass

            return Response()

        with patch("cv.invenio.requests.get", side_effect=fake_get):
            items = source.fetch()

        assert len(items) == 3  # book, article, chapter — book only once

    def test_fetch_follows_pagination_links(self, source, fake_config):
        fake_config.orcid = None  # single query keeps the walk simple
        pages = {
            "https://works.example.org/api/records": {
                "hits": {"hits": [ARTICLE_RECORD]},
                "links": {"next": "https://works.example.org/api/records?page=2"},
            },
            "https://works.example.org/api/records?page=2": {
                "hits": {"hits": [CHAPTER_RECORD]},
                "links": {},
            },
        }

        def fake_get(url, **kwargs):
            class Response:
                status_code = 200

                def json(self, _url=url):
                    # first call arrives with params; subsequent calls use
                    # the literal next link
                    key = (
                        "https://works.example.org/api/records"
                        if kwargs.get("params")
                        else _url
                    )
                    return pages[key]

                def raise_for_status(self):
                    pass

            return Response()

        with patch("cv.invenio.requests.get", side_effect=fake_get):
            items = source.fetch()

        assert [i["title"] for i in items] == ["An Article", "A Chapter"]

    def test_fetch_skips_unmapped_types(self, source, fake_config):
        fake_config.orcid = None

        def fake_get(url, **kwargs):
            class Response:
                status_code = 200

                def json(self):
                    return {
                        "hits": {"hits": [BLOG_RECORD, BOOK_RECORD]},
                        "links": {},
                    }

                def raise_for_status(self):
                    pass

            return Response()

        with patch("cv.invenio.requests.get", side_effect=fake_get):
            items = source.fetch()

        assert [i["type"] for i in items] == ["book"]

    def test_search_requests_the_stable_inveniordm_representation(
        self, source, fake_config
    ):
        fake_config.orcid = None
        captured = {}

        def fake_get(url, **kwargs):
            captured.update(kwargs)

            class Response:
                def json(self):
                    return {"hits": {"hits": []}, "links": {}}

                def raise_for_status(self):
                    pass

            return Response()

        with patch("cv.invenio.requests.get", side_effect=fake_get):
            source.fetch()

        assert captured["headers"]["Accept"] == (
            "application/vnd.inveniordm.v1+json"
        )
