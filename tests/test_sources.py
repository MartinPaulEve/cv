"""Behavioural tests for the repository source layer.

A configuration may name any number of repositories; each becomes a
source object with a human-readable name and a fetch() returning
internal-format items. These tests pin down entry normalisation (single
dict or list), default naming from hostnames, and the eprints source's
URL building and fetching. All HTTP is mocked.
"""

import json
from unittest.mock import patch

import pytest
import requests

from cv.invenio import InvenioSource
from cv.sources import (
    ConfigView,
    EprintsSource,
    default_source_name,
    normalise_source_entries,
)


class TestEntryNormalisation:
    def test_single_dict_becomes_a_one_entry_list(self):
        assert normalise_source_entries({"repo": "eprints.example.ac.uk"}) == [
            {"repo": "eprints.example.ac.uk"}
        ]

    def test_a_list_of_entries_passes_through(self):
        entries = [{"repo": "a.example.org"}, {"repo": "b.example.org"}]
        assert normalise_source_entries(entries) == entries

    def test_nothing_configured_yields_no_entries(self):
        assert normalise_source_entries(None) == []


class TestDefaultNames:
    def test_hostname_of_a_full_url(self):
        assert (
            default_source_name("https://works.hcommons.org/api/records")
            == "works.hcommons.org"
        )

    def test_bare_hostname_is_kept(self):
        assert default_source_name("eprints.bbk.ac.uk") == "eprints.bbk.ac.uk"

    def test_hostname_with_trailing_path_but_no_scheme(self):
        assert default_source_name("eprints.bbk.ac.uk/") == "eprints.bbk.ac.uk"


class TestConfigView:
    def test_overridden_attribute_wins(self, fake_config):
        view = ConfigView(fake_config, invenio={"api": "https://x.example/api"})
        assert view.invenio == {"api": "https://x.example/api"}

    def test_other_attributes_delegate_to_the_base(self, fake_config):
        view = ConfigView(fake_config, invenio={"api": "https://x.example/api"})
        assert view.user == "Jane Doe"
        assert view.orcid == "0000-0000-0000-0000"

    def test_missing_attributes_raise_as_usual(self, fake_config):
        view = ConfigView(fake_config)
        with pytest.raises(AttributeError):
            _ = view.nonexistent
        assert getattr(view, "nonexistent", "fallback") == "fallback"


class TestEprintsSource:
    def test_url_is_derived_from_the_plaintext_user(self, fake_config, logger):
        source = EprintsSource(
            fake_config, logger, {"repo": "eprints.example.ac.uk"}
        )
        assert source.url == (
            "https://eprints.example.ac.uk/cgi/exportview/people/"
            "Doe=3AJane=3A=3A/JSON/Doe=3AJane=3A=3A.js"
        )

    def test_pre_encoded_user_in_the_entry_wins(self, fake_config, logger):
        source = EprintsSource(
            fake_config,
            logger,
            {"repo": "eprints.example.ac.uk", "user": "Custom=3APerson=3A=3A"},
        )
        assert "Custom=3APerson=3A=3A" in source.url

    def test_existing_scheme_is_preserved(self, fake_config, logger):
        source = EprintsSource(
            fake_config, logger, {"repo": "http://eprints.example.ac.uk/"}
        )
        assert source.url.startswith("http://eprints.example.ac.uk/cgi/")

    def test_name_defaults_to_the_hostname(self, fake_config, logger):
        source = EprintsSource(
            fake_config, logger, {"repo": "eprints.example.ac.uk"}
        )
        assert source.name == "eprints.example.ac.uk"

    def test_explicit_name_is_honoured(self, fake_config, logger):
        source = EprintsSource(
            fake_config,
            logger,
            {"repo": "eprints.example.ac.uk", "name": "Example eprints"},
        )
        assert source.name == "Example eprints"

    def test_fetch_returns_the_parsed_item_list(self, fake_config, logger):
        items = [{"type": "book", "title": "A Monograph"}]
        source = EprintsSource(
            fake_config, logger, {"repo": "eprints.example.ac.uk"}
        )

        with patch("cv.sources.requests.get") as mock_get:
            mock_get.return_value.text = json.dumps(items)
            assert source.fetch() == items

    def test_fetch_raises_on_http_errors(self, fake_config, logger):
        source = EprintsSource(
            fake_config, logger, {"repo": "eprints.example.ac.uk"}
        )

        with patch("cv.sources.requests.get") as mock_get:
            mock_get.return_value.raise_for_status.side_effect = (
                requests.HTTPError("server error")
            )
            with pytest.raises(requests.RequestException):
                source.fetch()


class TestInvenioSourceNaming:
    def test_name_defaults_to_the_api_hostname(self, fake_config, logger):
        fake_config.invenio = {"api": "https://works.example.org/api/records"}
        source = InvenioSource(fake_config, logger)
        assert source.name == "works.example.org"

    def test_explicit_name_is_honoured(self, fake_config, logger):
        fake_config.invenio = {
            "api": "https://works.example.org/api/records",
            "name": "KC Works",
        }
        source = InvenioSource(fake_config, logger)
        assert source.name == "KC Works"
