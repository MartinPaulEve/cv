"""Behavioural tests for cv.repository.Repository.

These tests pin down what the repository layer must do — build the right
endpoint URL, cache fetched JSON, classify items into CV sections, and
persist those sections — without caring how it does it. All network access
is mocked.
"""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
import requests

from cv.repository import Repository


@pytest.fixture
def repo(fake_config, logger):
    return Repository(fake_config, logger, refresh=False)


SAMPLE_ITEMS = [
    {
        "type": "book",
        "title": "A Monograph",
        "refereed": "TRUE",
        "date": "2020-01-01",
    },
    {
        "type": "book",
        "title": "An Edited Collection",
        "refereed": "TRUE",
        "editors": [{"name": {"given": "Jane", "family": "Doe"}}],
        "date": "2019-01-01",
    },
    {
        "type": "article",
        "title": "A Refereed Article",
        "refereed": "TRUE",
        "date": "2021-01-01",
    },
    {
        "type": "article",
        "title": "A Magazine Piece",
        "refereed": "FALSE",
        "date": "2018-01-01",
    },
]


class TestUrlBuilding:
    def test_user_name_is_encoded_into_the_url(self, repo):
        """The plaintext config user is converted to the eprints escaped
        person-identifier format when the endpoint URL is built."""
        assert repo.url == (
            "https://eprints.example.ac.uk/cgi/exportview/people/"
            "Doe=3AJane=3A=3A/JSON/Doe=3AJane=3A=3A.js"
        )

    def test_existing_scheme_is_preserved(self, fake_config, logger):
        fake_config.eprints["repo"] = "http://eprints.example.ac.uk/"
        repo = Repository(fake_config, logger, refresh=False)
        assert repo.url.startswith("http://eprints.example.ac.uk/cgi/")

    def test_pre_encoded_user_is_honoured_when_present(self, fake_config, logger):
        """A config may still carry an explicit pre-encoded eprints user,
        which wins over the derived encoding."""
        fake_config.eprints["user"] = "Custom=3APerson=3A=3A"
        repo = Repository(fake_config, logger, refresh=False)
        assert "Custom=3APerson=3A=3A" in repo.url

    def test_legacy_pre_encoded_user_does_not_require_plaintext_user(
        self, fake_config, logger
    ):
        del fake_config.user
        fake_config.eprints["user"] = "Legacy=3APerson=3A=3A"

        repo = Repository(fake_config, logger, refresh=False)

        assert "Legacy=3APerson=3A=3A" in repo.url


class TestFilters:
    def test_peer_review_any_permits_everything(self, repo):
        item = {"title": "x", "refereed": "FALSE"}
        assert repo._filter_by_peer_review(item, ["books"]) == ["books"]

    def test_peer_review_true_requires_refereed(self, repo):
        refereed = {"title": "x", "refereed": "TRUE"}
        unrefereed = {"title": "x", "refereed": "FALSE"}
        assert repo._filter_by_peer_review(refereed, ["articles"]) == ["articles"]
        assert repo._filter_by_peer_review(unrefereed, ["articles"]) == []

    def test_peer_review_false_requires_unrefereed(self, repo):
        unrefereed = {"title": "x", "refereed": "FALSE"}
        assert repo._filter_by_peer_review(unrefereed, ["other_articles"]) == [
            "other_articles"
        ]

    def test_editorial_split(self, repo):
        edited = {"title": "x", "editors": [{"name": {}}]}
        unedited = {"title": "x"}
        assert repo._filter_by_editorial(edited, ["books", "edited_books"]) == [
            "edited_books"
        ]
        assert repo._filter_by_editorial(unedited, ["books", "edited_books"]) == [
            "books"
        ]

    def test_book_review_split(self, repo):
        review = {"title": "Review of Something"}
        article = {"title": "Something Else"}
        assert repo._filter_by_book_review(review, ["reviews", "articles"]) == [
            "reviews"
        ]
        assert repo._filter_by_book_review(article, ["reviews", "articles"]) == [
            "articles"
        ]

    def test_potential_types_reverse_lookup(self, repo):
        item = {"type": "book", "title": "x"}
        assert sorted(repo._get_potential_types(item)) == ["books", "edited_books"]


class TestTypeChecking:
    def test_known_types_pass(self, repo):
        assert repo._check_types(["books", "articles"]) is True

    def test_unknown_types_fail(self, repo):
        assert repo._check_types(["nonsense"]) is False

    def test_fetch_rejects_unknown_types(self, repo):
        assert repo.fetch(["nonsense"]) is False


class TestJsonCaching:
    def test_loads_from_disk_cache_when_present(self, repo, fake_config):
        with open(fake_config.storage["json"], "w") as out:
            json.dump(SAMPLE_ITEMS, out)

        assert repo._populate_json(refresh=False) is True
        assert repo.json == SAMPLE_ITEMS

    def test_fetches_from_remote_when_no_cache(self, repo, fake_config):
        with patch("cv.repository.requests.get") as mock_get:
            mock_get.return_value.text = json.dumps(SAMPLE_ITEMS)
            assert repo._populate_json(refresh=False) is True

        assert repo.json == SAMPLE_ITEMS
        # and the fetched JSON must now be cached on disk
        with open(fake_config.storage["json"]) as cached:
            assert json.load(cached) == SAMPLE_ITEMS

    def test_remote_error_reports_failure(self, repo):
        import requests as requests_lib

        with patch("cv.repository.requests.get") as mock_get:
            mock_get.side_effect = requests_lib.RequestException("boom")
            assert repo._populate_json(refresh=True) is False

    def test_http_error_preserves_the_last_good_cache(self, repo, fake_config):
        previous = [{"type": "book", "title": "Cached book"}]
        with open(fake_config.storage["json"], "w") as cached:
            json.dump(previous, cached)

        with patch("cv.repository.requests.get") as mock_get:
            mock_get.return_value.text = "[]"
            mock_get.return_value.raise_for_status.side_effect = (
                requests.HTTPError("server error")
            )
            assert repo._populate_json(refresh=True) is False

        with open(fake_config.storage["json"]) as cached:
            assert json.load(cached) == previous

    def test_malformed_json_preserves_the_last_good_cache(self, repo, fake_config):
        previous = [{"type": "book", "title": "Cached book"}]
        with open(fake_config.storage["json"], "w") as cached:
            json.dump(previous, cached)

        with patch("cv.repository.requests.get") as mock_get:
            mock_get.return_value.text = "<html>upstream error</html>"
            assert repo._populate_json(refresh=True) is False

        with open(fake_config.storage["json"]) as cached:
            assert json.load(cached) == previous

    def test_fetch_creates_a_profile_cache_directory(self, repo, fake_config):
        fake_config.storage["json"] = str(
            Path(fake_config.storage["json"]).parent
            / "jane_doe"
            / "eprints.json"
        )

        with patch("cv.repository.requests.get") as mock_get:
            mock_get.return_value.text = "[]"
            assert repo._populate_json(refresh=True) is True

        assert os.path.isfile(fake_config.storage["json"])


class TestMultiSourceFetch:
    def test_refresh_merges_invenio_records_into_the_cache(
        self, fake_config, logger
    ):
        """With an invenio source configured, a refresh merges its records
        with the eprints data (deduplicated by DOI, eprints preferred)
        into the single cache file that the rest of the pipeline reads."""
        fake_config.invenio = {"api": "https://works.example.org/api/records"}

        eprints_payload = [
            {"type": "book", "title": "Shared Book", "doi": "10.1/shared"},
            {"type": "book", "title": "Eprints Only"},
        ]
        invenio_items = [
            {
                "type": "book",
                "title": "Shared Book (KC)",
                "doi": "10.1/SHARED",
                "publisher": "punctum books",
            },
            {"type": "article", "title": "KC Only", "refereed": "TRUE"},
        ]

        class FakeInvenioSource:
            def __init__(self, config, logger):
                pass

            def fetch(self):
                return invenio_items

        repo = Repository(fake_config, logger, refresh=True)

        with (
            patch("cv.repository.requests.get") as mock_get,
            patch("cv.repository.InvenioSource", FakeInvenioSource),
        ):
            mock_get.return_value.text = json.dumps(eprints_payload)
            assert repo._populate_json(refresh=True) is True

        titles = [item["title"] for item in repo.json]
        assert titles == ["Shared Book", "Eprints Only", "KC Only"]
        # the shared record took the publisher from the KC copy
        assert repo.json[0]["publisher"] == "punctum books"

        # and the merged list is what got cached on disk
        with open(fake_config.storage["json"]) as cached:
            assert json.load(cached) == repo.json

    def test_invenio_failure_does_not_replace_the_complete_cache(
        self, fake_config, logger
    ):
        fake_config.invenio = {"api": "https://works.example.org/api/records"}
        previous = [{"type": "book", "title": "Complete cached data"}]
        with open(fake_config.storage["json"], "w") as cached:
            json.dump(previous, cached)

        class FailingInvenioSource:
            def __init__(self, config, logger):
                pass

            def fetch(self):
                raise requests.RequestException("secondary unavailable")

        repo = Repository(fake_config, logger, refresh=True)
        with (
            patch("cv.repository.requests.get") as mock_get,
            patch("cv.repository.InvenioSource", FailingInvenioSource),
        ):
            mock_get.return_value.text = "[]"
            assert repo._populate_json(refresh=True) is False

        with open(fake_config.storage["json"]) as cached:
            assert json.load(cached) == previous


class TestMultipleRepositories:
    def test_two_eprints_repositories_merge_with_the_first_as_primary(
        self, fake_config, logger
    ):
        """Configs may list several eprints repositories; declaration order
        is priority order, so the first repository's records are the base
        and later ones fill gaps or append."""
        fake_config.eprints = [
            {"repo": "a.example.org"},
            {"repo": "b.example.org"},
        ]

        payloads = {
            "a.example.org": [
                {"type": "book", "title": "Shared Book", "doi": "10.1/shared"}
            ],
            "b.example.org": [
                {
                    "type": "book",
                    "title": "Shared Book (B)",
                    "doi": "10.1/shared",
                    "publisher": "B Press",
                },
                {"type": "book", "title": "B Only"},
            ],
        }

        def fake_get(url, **kwargs):
            class Response:
                text = json.dumps(
                    next(
                        payload
                        for host, payload in payloads.items()
                        if host in url
                    )
                )

                def raise_for_status(self):
                    pass

            return Response()

        repo = Repository(fake_config, logger, refresh=True)
        with patch("cv.sources.requests.get", side_effect=fake_get):
            assert repo._populate_json(refresh=True) is True

        titles = [item["title"] for item in repo.json]
        assert titles == ["Shared Book", "B Only"]
        # the shared record kept A's fields and gained B's publisher
        assert repo.json[0]["publisher"] == "B Press"

    def test_multiple_invenio_repositories_each_receive_their_own_entry(
        self, fake_config, logger
    ):
        """With a list under `invenio`, one source is built per entry and
        each sees its entry as a plain single-repository config."""
        del fake_config.eprints
        fake_config.invenio = [
            {"api": "https://a.example.org/api/records"},
            {"api": "https://b.example.org/api/records"},
        ]

        items_by_api = {
            "https://a.example.org/api/records": [
                {"type": "book", "title": "From A"}
            ],
            "https://b.example.org/api/records": [
                {"type": "article", "title": "From B", "refereed": "TRUE"}
            ],
        }

        class FakeInvenioSource:
            def __init__(self, config, logger):
                self.api = config.invenio["api"]

            def fetch(self):
                return items_by_api[self.api]

        repo = Repository(fake_config, logger, refresh=True)
        with patch("cv.repository.InvenioSource", FakeInvenioSource):
            assert repo._populate_json(refresh=True) is True

        assert [item["title"] for item in repo.json] == ["From A", "From B"]

    def test_invenio_only_configuration_is_supported(self, fake_config, logger):
        del fake_config.eprints
        fake_config.invenio = {"api": "https://works.example.org/api/records"}
        items = [{"type": "book", "title": "Invenio Book"}]

        class FakeInvenioSource:
            def __init__(self, config, logger):
                pass

            def fetch(self):
                return items

        repo = Repository(fake_config, logger, refresh=True)
        assert repo.url is None

        with patch("cv.repository.InvenioSource", FakeInvenioSource):
            assert repo._populate_json(refresh=True) is True

        assert repo.json == items

    def test_no_configured_sources_is_a_configuration_error(
        self, fake_config, logger
    ):
        del fake_config.eprints

        repo = Repository(fake_config, logger, refresh=True)

        assert repo._populate_json(refresh=True) is False
        assert not os.path.exists(fake_config.storage["json"])

    def test_eprints_repositories_take_priority_over_invenio(
        self, fake_config, logger
    ):
        """All eprints entries come before all invenio entries, preserving
        the historic precedence of eprints records."""
        fake_config.invenio = {"api": "https://works.example.org/api/records"}

        eprints_items = [
            {"type": "book", "title": "Shared", "doi": "10.1/x"}
        ]
        invenio_items = [
            {
                "type": "book",
                "title": "Shared (KC)",
                "doi": "10.1/x",
                "publisher": "KC Press",
            }
        ]

        class FakeInvenioSource:
            def __init__(self, config, logger):
                pass

            def fetch(self):
                return invenio_items

        repo = Repository(fake_config, logger, refresh=True)
        with (
            patch("cv.sources.requests.get") as mock_get,
            patch("cv.repository.InvenioSource", FakeInvenioSource),
        ):
            mock_get.return_value.text = json.dumps(eprints_items)
            assert repo._populate_json(refresh=True) is True

        assert [item["title"] for item in repo.json] == ["Shared"]
        assert repo.json[0]["publisher"] == "KC Press"


class TestFetchPipeline:
    def test_fetch_writes_classified_sections_to_disk(self, repo, fake_config):
        """The core contract: fetch() splits repository JSON into per-type files."""
        with patch("cv.repository.requests.get") as mock_get:
            mock_get.return_value.text = json.dumps(SAMPLE_ITEMS)
            repo.fetch(["books", "edited_books", "articles", "other_articles"])

        def stored(section):
            with open(fake_config.storage[section]) as stored_file:
                return [json.loads(line) for line in stored_file]

        assert [i["title"] for i in stored("books")] == ["A Monograph"]
        assert [i["title"] for i in stored("edited_books")] == ["An Edited Collection"]
        assert [i["title"] for i in stored("articles")] == ["A Refereed Article"]
        assert [i["title"] for i in stored("other_articles")] == ["A Magazine Piece"]

    def test_sections_readable_as_attributes(self, repo, fake_config):
        """Stored sections are exposed as attributes, e.g. repo.books."""
        with open(fake_config.storage["books"], "w") as out:
            out.write(json.dumps({"title": "A Monograph"}) + "\n")

        assert repo.books == [{"title": "A Monograph"}]

    def test_fetch_only_writes_requested_sections(self, repo, fake_config):
        with patch("cv.repository.requests.get") as mock_get:
            mock_get.return_value.text = json.dumps(SAMPLE_ITEMS)
            assert repo.fetch(["books"]) is True

        assert os.path.isfile(fake_config.storage["books"])
        assert not os.path.exists(fake_config.storage["articles"])

    def test_empty_refresh_clears_a_requested_section(self, repo, fake_config):
        with open(fake_config.storage["books"], "w") as stored:
            stored.write(json.dumps({"title": "Stale book"}) + "\n")

        with patch("cv.repository.requests.get") as mock_get:
            mock_get.return_value.text = "[]"
            assert repo.fetch(["books"]) is True

        with open(fake_config.storage["books"]) as stored:
            assert stored.read() == ""
