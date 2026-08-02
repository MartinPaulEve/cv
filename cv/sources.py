"""Repository source objects for the fetch pipeline.

A configuration may name any number of repositories of each supported
type (eprints and InvenioRDM). Each configured repository becomes one
source object carrying a human-readable name and a fetch() method that
returns items in the internal format; the Repository class reduces the
ordered source list with merge_records, so the first source is primary
and each later source fills gaps in (or appends to) what came before.

For backwards compatibility a configuration may still give `eprints` or
`invenio` as a single dict; normalise_source_entries turns either shape
into a list of entries.
"""

import json
from urllib.parse import urlparse

import requests

from cv.configuration import encode_eprints_user


class SourceConfigurationError(ValueError):
    """A repository entry cannot be used as configured."""


def normalise_source_entries(value):
    """
    Normalise a configured repository setting into a list of entries
    :param value: a single entry dict, a list of entry dicts, or None
    :return: a list of entry dicts (empty when nothing is configured)
    """
    if value is None:
        return []
    if isinstance(value, dict):
        return [value]
    return list(value)


def default_source_name(url):
    """
    Derive a human-readable default source name from a repository URL
    :param url: the repository or API URL, with or without a scheme
    :return: the hostname of the URL
    """
    if "//" not in url:
        url = f"//{url}"
    parsed = urlparse(url)
    return parsed.netloc or url


class ConfigView:
    """A read-only view of a configuration with some attributes overridden.

    Sources read repository details from the configuration object; a view
    lets the Repository pin a multi-entry setting (e.g. a list under
    `invenio`) down to the single entry a given source should use, without
    copying or mutating the underlying config module.
    """

    def __init__(self, base, **overrides):
        self._base = base
        self._overrides = overrides

    def __getattr__(self, name):
        if name in self._overrides:
            return self._overrides[name]
        return getattr(self._base, name)


class EprintsSource:
    """One configured eprints repository."""

    def __init__(self, config, logger, entry):
        self.config = config
        self.logger = logger
        self.entry = entry
        self.name = entry.get("name") or default_source_name(entry["repo"])
        self.url = self._build_url()

    def _base_url(self):
        """The repository base URL with a scheme and a trailing slash."""
        repo = self.entry["repo"]

        if not repo.startswith("htt"):
            repo = "https://" + repo

        if not repo.endswith("/"):
            repo += "/"

        return repo

    def _person_identifier(self):
        """The eprints person identifier: a pre-encoded one from the entry
        wins; otherwise it is derived from the plaintext user name."""
        if "user" in self.entry:
            return self.entry["user"]
        return encode_eprints_user(self.config.user)

    def _build_url(self):
        """
        Creates the eprints exportview endpoint URL
        :return: an eprints endpoint URL string
        """
        user = self._person_identifier()
        url = f"{self._base_url()}cgi/exportview/people/{user}/JSON/{user}.js"

        self.logger.debug(f"Built eprints URL for {self.name} as: {url}")

        return url

    def fetch(self):
        """
        Fetch the scholar's records from this eprints repository
        :return: a list of internal-format items
        """
        self.logger.debug(f"Fetching eprints data from {self.url}")

        response = requests.get(self.url, timeout=60)
        response.raise_for_status()

        return json.loads(response.text)
