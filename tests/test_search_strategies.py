"""Behavioural tests for per-repository search customisation.

Each repository entry may carry a `search` specification: an ordered
list of strategy names plus a combine mode. `union` runs every strategy
and combines the results; `first` runs strategies in order and stops at
the first that returns any records. Strategies that cannot be used with
the given configuration, or unknown strategy names, fail loudly at fetch
time. With no `search` key, each source type reproduces its historic
default behaviour exactly. All HTTP is mocked.
"""

import json
from unittest.mock import patch

import pytest

from cv.invenio import InvenioSource
from cv.sources import (
    ConfigView,
    EprintsSource,
    SourceConfigurationError,
    encode_eprints_value,
    parse_search_spec,
)


class TestSearchSpecParsing:
    def test_no_specification_yields_none(self):
        assert parse_search_spec(None) is None

    def test_bare_list_is_an_ordered_fallback_chain(self):
        assert parse_search_spec(["email", "name"]) == (
            ["email", "name"],
            "first",
        )

    def test_dict_form_carries_strategies_and_mode(self):
        assert parse_search_spec(
            {"strategies": ["orcid"], "mode": "first"}
        ) == (["orcid"], "first")

    def test_dict_mode_defaults_to_union(self):
        assert parse_search_spec({"strategies": ["name", "orcid"]}) == (
            ["name", "orcid"],
            "union",
        )

    def test_unknown_mode_is_a_configuration_error(self):
        with pytest.raises(SourceConfigurationError):
            parse_search_spec({"strategies": ["name"], "mode": "sometimes"})

    def test_empty_strategy_list_is_a_configuration_error(self):
        with pytest.raises(SourceConfigurationError):
            parse_search_spec([])
        with pytest.raises(SourceConfigurationError):
            parse_search_spec({"strategies": []})


class TestEprintsValueEncoding:
    def test_email_addresses_are_escaped(self):
        assert encode_eprints_value("jane@example.com") == (
            "jane=40example=2Ecom"
        )

    def test_alphanumerics_and_underscores_pass_through(self):
        assert encode_eprints_value("Jane_Doe1") == "Jane_Doe1"

    def test_colons_match_the_person_identifier_escaping(self):
        assert encode_eprints_value("Doe:Jane::") == "Doe=3AJane=3A=3A"


def _eprints_responses(payloads_by_fragment, missing=()):
    """A requests.get side effect serving JSON by URL fragment; URLs
    containing a fragment from `missing` return HTTP 404."""

    def fake_get(url, **kwargs):
        class Response:
            status_code = 200
            text = "[]"

            def raise_for_status(self):
                pass

        response = Response()

        for fragment in missing:
            if fragment in url:
                response.status_code = 404
                return response

        for fragment, payload in payloads_by_fragment.items():
            if fragment in url:
                response.text = json.dumps(payload)
                return response

        raise AssertionError(f"Unexpected URL fetched: {url}")

    return fake_get


class TestEprintsEmailStrategy:
    def test_email_strategy_queries_the_email_browse_view(
        self, fake_config, logger
    ):
        items = [{"eprintid": 1, "type": "book", "title": "A Monograph"}]
        source = EprintsSource(
            fake_config,
            logger,
            {"repo": "eprints.example.ac.uk", "search": ["email"]},
        )

        captured = []

        def fake_get(url, **kwargs):
            captured.append(url)

            class Response:
                status_code = 200
                text = json.dumps(items)

                def raise_for_status(self):
                    pass

            return Response()

        with patch("cv.sources.requests.get", side_effect=fake_get):
            assert source.fetch() == items

        assert captured == [
            "https://eprints.example.ac.uk/cgi/exportview/creators_email/"
            "jane=40example=2Ecom/JSON/jane=40example=2Ecom.js"
        ]

    def test_all_configured_emails_are_tried(self, fake_config, logger):
        fake_config.emails = ["jane@example.com", "j.doe@other.ac.uk"]
        source = EprintsSource(
            fake_config,
            logger,
            {"repo": "eprints.example.ac.uk", "search": ["email"]},
        )

        fake_get = _eprints_responses(
            {
                "jane=40example=2Ecom": [
                    {"eprintid": 1, "type": "book", "title": "First"}
                ],
                "j=2Edoe=40other=2Eac=2Euk": [
                    {"eprintid": 2, "type": "book", "title": "Second"}
                ],
            }
        )

        with patch("cv.sources.requests.get", side_effect=fake_get):
            titles = [item["title"] for item in source.fetch()]

        assert titles == ["First", "Second"]

    def test_email_view_path_is_configurable(self, fake_config, logger):
        source = EprintsSource(
            fake_config,
            logger,
            {
                "repo": "eprints.example.ac.uk",
                "email_view": "contributors_email",
                "search": ["email"],
            },
        )

        fake_get = _eprints_responses(
            {"exportview/contributors_email/": [{"eprintid": 1, "title": "X"}]}
        )

        with patch("cv.sources.requests.get", side_effect=fake_get):
            assert [item["title"] for item in source.fetch()] == ["X"]

    def test_email_strategy_without_emails_fails_loudly(
        self, fake_config, logger
    ):
        fake_config.emails = []
        source = EprintsSource(
            fake_config,
            logger,
            {"repo": "eprints.example.ac.uk", "search": ["email"]},
        )

        with pytest.raises(SourceConfigurationError, match="email"):
            source.fetch()

    def test_missing_email_browse_page_counts_as_no_records(
        self, fake_config, logger
    ):
        """eprints answers 404 for a browse value with no page; in a
        fallback chain that simply means the strategy found nothing."""
        source = EprintsSource(
            fake_config,
            logger,
            {"repo": "eprints.example.ac.uk", "search": ["email", "name"]},
        )

        fake_get = _eprints_responses(
            {"exportview/people/": [{"eprintid": 3, "title": "Via name"}]},
            missing=["exportview/creators_email/"],
        )

        with patch("cv.sources.requests.get", side_effect=fake_get):
            assert [item["title"] for item in source.fetch()] == ["Via name"]


class TestEprintsSearchModes:
    def test_first_mode_stops_at_the_first_strategy_with_records(
        self, fake_config, logger
    ):
        """With records found by email, the name strategy is never
        consulted: its endpoint erroring cannot affect the fetch."""
        source = EprintsSource(
            fake_config,
            logger,
            {"repo": "eprints.example.ac.uk", "search": ["email", "name"]},
        )

        def fake_get(url, **kwargs):
            if "exportview/people/" in url:
                raise AssertionError("the name strategy should not run")

            class Response:
                status_code = 200
                text = json.dumps([{"eprintid": 1, "title": "Via email"}])

                def raise_for_status(self):
                    pass

            return Response()

        with patch("cv.sources.requests.get", side_effect=fake_get):
            assert [item["title"] for item in source.fetch()] == ["Via email"]

    def test_first_mode_falls_through_empty_strategies(
        self, fake_config, logger
    ):
        source = EprintsSource(
            fake_config,
            logger,
            {"repo": "eprints.example.ac.uk", "search": ["email", "name"]},
        )

        fake_get = _eprints_responses(
            {
                "exportview/creators_email/": [],
                "exportview/people/": [{"eprintid": 2, "title": "Via name"}],
            }
        )

        with patch("cv.sources.requests.get", side_effect=fake_get):
            assert [item["title"] for item in source.fetch()] == ["Via name"]

    def test_union_mode_combines_and_deduplicates_by_eprintid(
        self, fake_config, logger
    ):
        source = EprintsSource(
            fake_config,
            logger,
            {
                "repo": "eprints.example.ac.uk",
                "search": {"strategies": ["name", "email"], "mode": "union"},
            },
        )

        shared = {"eprintid": 1, "title": "Shared"}
        fake_get = _eprints_responses(
            {
                "exportview/people/": [shared, {"eprintid": 2, "title": "A"}],
                "exportview/creators_email/": [
                    shared,
                    {"eprintid": 3, "title": "B"},
                ],
            }
        )

        with patch("cv.sources.requests.get", side_effect=fake_get):
            titles = [item["title"] for item in source.fetch()]

        assert titles == ["Shared", "A", "B"]


class TestEprintsStrategyErrors:
    def test_unknown_strategy_fails_loudly(self, fake_config, logger):
        source = EprintsSource(
            fake_config,
            logger,
            {"repo": "eprints.example.ac.uk", "search": ["telepathy"]},
        )

        with pytest.raises(SourceConfigurationError, match="telepathy"):
            source.fetch()

    def test_user_strategy_requires_a_pre_encoded_user(
        self, fake_config, logger
    ):
        source = EprintsSource(
            fake_config,
            logger,
            {"repo": "eprints.example.ac.uk", "search": ["user"]},
        )

        with pytest.raises(SourceConfigurationError, match="user"):
            source.fetch()

    def test_user_strategy_uses_the_entry_identifier(self, fake_config, logger):
        source = EprintsSource(
            fake_config,
            logger,
            {
                "repo": "eprints.example.ac.uk",
                "user": "Custom=3APerson=3A=3A",
                "search": ["user"],
            },
        )

        fake_get = _eprints_responses(
            {"Custom=3APerson=3A=3A": [{"eprintid": 9, "title": "Custom"}]}
        )

        with patch("cv.sources.requests.get", side_effect=fake_get):
            assert [item["title"] for item in source.fetch()] == ["Custom"]


ORCID_RECORD = {
    "id": "orcid-1",
    "pids": {},
    "access": {"status": "metadata-only"},
    "metadata": {
        "resource_type": {"id": "textDocument-journalArticle"},
        "title": "Found by ORCID",
        "publication_date": "2020",
        "creators": [],
    },
}

NAME_RECORD = {
    "id": "name-1",
    "pids": {},
    "access": {"status": "metadata-only"},
    "metadata": {
        "resource_type": {"id": "textDocument-journalArticle"},
        "title": "Found by name",
        "publication_date": "2021",
        "creators": [],
    },
}

CUSTOM_RECORD = {
    "id": "custom-1",
    "pids": {},
    "access": {"status": "metadata-only"},
    "metadata": {
        "resource_type": {"id": "textDocument-journalArticle"},
        "title": "Found by custom query",
        "publication_date": "2022",
        "creators": [],
    },
}


def _invenio_responses(records_by_query_fragment):
    """A requests.get side effect answering InvenioRDM searches according
    to fragments of the q parameter."""

    def fake_get(url, **kwargs):
        query = kwargs.get("params", {}).get("q", "")

        class Response:
            status_code = 200

            def json(self):
                for fragment, records in records_by_query_fragment.items():
                    if fragment in query:
                        return {"hits": {"hits": records}, "links": {}}
                return {"hits": {"hits": []}, "links": {}}

            def raise_for_status(self):
                pass

        return Response()

    return fake_get


def _invenio_source(fake_config, logger, entry):
    return InvenioSource(ConfigView(fake_config, invenio=entry), logger)


class TestInvenioStrategies:
    def test_orcid_only_search_ignores_name_matches(self, fake_config, logger):
        source = _invenio_source(
            fake_config,
            logger,
            {
                "api": "https://works.example.org/api/records",
                "search": {"strategies": ["orcid"], "mode": "first"},
            },
        )

        fake_get = _invenio_responses(
            {
                "identifiers.identifier": [ORCID_RECORD],
                "person_or_org.name": [NAME_RECORD],
            }
        )

        with patch("cv.invenio.requests.get", side_effect=fake_get):
            titles = [item["title"] for item in source.fetch()]

        assert titles == ["Found by ORCID"]

    def test_orcid_strategy_without_an_orcid_fails_loudly(
        self, fake_config, logger
    ):
        fake_config.orcid = None
        source = _invenio_source(
            fake_config,
            logger,
            {
                "api": "https://works.example.org/api/records",
                "search": ["orcid"],
            },
        )

        with pytest.raises(SourceConfigurationError, match="orcid"):
            source.fetch()

    def test_unknown_strategy_fails_loudly(self, fake_config, logger):
        source = _invenio_source(
            fake_config,
            logger,
            {
                "api": "https://works.example.org/api/records",
                "search": ["clairvoyance"],
            },
        )

        with pytest.raises(SourceConfigurationError, match="clairvoyance"):
            source.fetch()

    def test_raw_query_escape_hatch(self, fake_config, logger):
        source = _invenio_source(
            fake_config,
            logger,
            {
                "api": "https://works.example.org/api/records",
                "search": ['query:metadata.title:"Bespoke"'],
            },
        )

        fake_get = _invenio_responses(
            {'metadata.title:"Bespoke"': [CUSTOM_RECORD]}
        )

        with patch("cv.invenio.requests.get", side_effect=fake_get):
            titles = [item["title"] for item in source.fetch()]

        assert titles == ["Found by custom query"]

    def test_first_mode_falls_through_an_empty_strategy(
        self, fake_config, logger
    ):
        source = _invenio_source(
            fake_config,
            logger,
            {
                "api": "https://works.example.org/api/records",
                "search": ["orcid", "name"],
            },
        )

        fake_get = _invenio_responses({"person_or_org.name": [NAME_RECORD]})

        with patch("cv.invenio.requests.get", side_effect=fake_get):
            titles = [item["title"] for item in source.fetch()]

        assert titles == ["Found by name"]

    def test_union_mode_combines_strategy_results_by_record_id(
        self, fake_config, logger
    ):
        source = _invenio_source(
            fake_config,
            logger,
            {
                "api": "https://works.example.org/api/records",
                "search": {"strategies": ["name", "orcid"], "mode": "union"},
            },
        )

        fake_get = _invenio_responses(
            {
                "person_or_org.name": [NAME_RECORD, ORCID_RECORD],
                "identifiers.identifier": [ORCID_RECORD],
            }
        )

        with patch("cv.invenio.requests.get", side_effect=fake_get):
            titles = sorted(item["title"] for item in source.fetch())

        assert titles == ["Found by ORCID", "Found by name"]
