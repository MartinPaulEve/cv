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


SEARCH_MODES = ("union", "first")


def parse_search_spec(value):
    """
    Normalise a repository entry's `search` setting into a strategy plan
    :param value: None (no customisation), a bare list of strategy names
        (an ordered fallback chain, mode 'first'), or a dict of the form
        {'strategies': [...], 'mode': 'union'|'first'} (mode defaults to
        'union', which runs every strategy and combines the results)
    :return: a (strategies, mode) tuple, or None when nothing is specified
    """
    if value is None:
        return None

    if isinstance(value, dict):
        strategies = list(value.get("strategies", []))
        mode = value.get("mode", "union")
    else:
        strategies = list(value)
        mode = "first"

    if not strategies:
        raise SourceConfigurationError(
            "a `search` specification must name at least one strategy"
        )

    if mode not in SEARCH_MODES:
        raise SourceConfigurationError(
            f"unknown search mode '{mode}' (expected one of "
            f"{', '.join(repr(m) for m in SEARCH_MODES)})"
        )

    return strategies, mode


def encode_eprints_value(value):
    """
    Encode a value (e.g. an email address) for use in an eprints browse
    view URL: alphanumerics and underscores pass through; anything else
    becomes '=XX' with the character's hex code, the same escaping used
    by eprints person identifiers
    :param value: the plain value
    :return: the encoded value
    """
    return "".join(
        char
        if (char.isalnum() and char.isascii()) or char == "_"
        else f"={ord(char):02X}"
        for char in value
    )


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
    """One configured eprints repository.

    Search strategies: 'name' (exportview by the person identifier derived
    from the plaintext user), 'user' (exportview by a pre-encoded person
    identifier given in the entry), and 'email' (an exportview browse view
    — `email_view` on the entry, default 'creators_email' — keyed by each
    of the configured email addresses). The default, with no `search` key,
    is the historic behaviour: the entry's pre-encoded user when there is
    one, otherwise the derived person identifier.
    """

    DEFAULT_EMAIL_VIEW = "creators_email"

    def __init__(self, config, logger, entry):
        self.config = config
        self.logger = logger
        self.entry = entry
        self.name = entry.get("name") or default_source_name(entry["repo"])
        self.email_view = entry.get("email_view", self.DEFAULT_EMAIL_VIEW)
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

    def _view_url(self, view, value):
        """The exportview JSON endpoint for one browse view and value."""
        return f"{self._base_url()}cgi/exportview/{view}/{value}/JSON/{value}.js"

    def _build_url(self):
        """
        Creates the default eprints exportview endpoint URL
        :return: an eprints endpoint URL string, or None when no person
            identifier can be derived (e.g. an email-only search with no
            plaintext user configured)
        """
        try:
            user = self._person_identifier()
        except AttributeError:
            return None

        url = self._view_url("people", user)

        self.logger.debug(f"Built eprints URL for {self.name} as: {url}")

        return url

    def _search_plan(self):
        """The (strategies, mode) plan for this entry: its `search` key,
        or the historic default of the single person-identifier view."""
        spec = parse_search_spec(self.entry.get("search"))

        if spec is not None:
            return spec

        return (["user"] if "user" in self.entry else ["name"]), "first"

    def _strategy_requests(self, strategy):
        """
        The exportview requests one strategy requires
        :param strategy: the strategy name
        :return: a list of (url, missing_ok) tuples; missing_ok marks
            views where an HTTP 404 just means "no records for this value"
        """
        if strategy == "name":
            user = getattr(self.config, "user", None)
            if not user:
                raise SourceConfigurationError(
                    f"{self.name}: the 'name' search strategy needs a "
                    "plaintext `user` in the configuration"
                )
            return [(self._view_url("people", encode_eprints_user(user)), False)]

        if strategy == "user":
            if "user" not in self.entry:
                raise SourceConfigurationError(
                    f"{self.name}: the 'user' search strategy needs a "
                    "pre-encoded 'user' in the repository entry"
                )
            return [(self._view_url("people", self.entry["user"]), False)]

        if strategy == "email":
            emails = list(getattr(self.config, "emails", None) or [])
            if not emails:
                raise SourceConfigurationError(
                    f"{self.name}: the 'email' search strategy needs "
                    "`emails` in the configuration"
                )
            return [
                (
                    self._view_url(self.email_view, encode_eprints_value(email)),
                    True,
                )
                for email in emails
            ]

        raise SourceConfigurationError(
            f"{self.name}: unknown eprints search strategy '{strategy}' "
            "(expected 'name', 'user', or 'email')"
        )

    def _run_strategy(self, strategy):
        """
        Run one search strategy
        :param strategy: the strategy name
        :return: the records it found, deduplicated by eprintid
        """
        found = []
        seen = set()

        for url, missing_ok in self._strategy_requests(strategy):
            self.logger.debug(f"Fetching eprints data from {url}")

            response = requests.get(url, timeout=60)

            if missing_ok and response.status_code == 404:
                self.logger.debug(f"No browse page at {url}; treating as empty")
                continue

            response.raise_for_status()

            for item in json.loads(response.text):
                key = item.get("eprintid")
                if key is not None:
                    if key in seen:
                        continue
                    seen.add(key)
                found.append(item)

        return found

    def fetch(self):
        """
        Fetch the scholar's records from this eprints repository by
        running its search plan
        :return: a list of internal-format items
        """
        strategies, mode = self._search_plan()

        items = []
        seen = set()

        for strategy in strategies:
            found = self._run_strategy(strategy)

            self.logger.debug(
                f"{self.name}: strategy '{strategy}' returned "
                f"{len(found)} records"
            )

            if mode == "first":
                if found:
                    return found
                continue

            for item in found:
                key = item.get("eprintid")
                if key is not None:
                    if key in seen:
                        continue
                    seen.add(key)
                items.append(item)

        return items
