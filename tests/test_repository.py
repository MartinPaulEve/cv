"""Behavioural tests for cv.repository.Repository.

These tests pin down what the repository layer must do — build the right
endpoint URL, cache fetched JSON, classify items into CV sections, and
persist those sections — without caring how it does it. All network access
is mocked.
"""

import json
from unittest.mock import patch

import pytest

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
