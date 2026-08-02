"""Fetch and normalise publication metadata from an InvenioRDM repository.

This targets KC Works (works.hcommons.org) in particular, but the API
endpoint is configurable, so any InvenioRDM instance — Zenodo, for
example — should work. Records are normalised into the same internal
item shape that the eprints pipeline consumes, so everything downstream
of fetching is source-agnostic.

By default two searches are run and unioned: one by the creator's name
and, where an ORCID is configured, one by that identifier. Neither alone
is complete — records imported from legacy systems often lack ORCIDs,
while a name match can miss variant forms — so the union is the safest
net. A repository entry may override this with a `search` specification
naming strategies ('name', 'orcid', or a 'query:<raw query>' escape
hatch) and a combine mode ('union' or 'first').
"""

from urllib.parse import quote, urljoin

import requests

from cv.sources import (
    SourceConfigurationError,
    default_source_name,
    parse_search_spec,
)

# how InvenioRDM resource types map onto the internal eprints-style types;
# types absent from this mapping (blog posts, video, and so on) have no CV
# section and are skipped
DEFAULT_TYPE_MAP = {
    "textDocument-book": "book",
    "textDocument-monograph": "book",
    "textDocument-journalArticle": "article",
    "textDocument-review": "article",
    "textDocument-bookSection": "book_section",
    "textDocument-bookChapter": "book_section",
    "presentation-conferencePaper": "conference_item",
    "presentation-conferencePresentation": "conference_item",
    "publication-article": "article",
    "publication-book": "book",
    "publication-section": "book_section",
    "publication-conferencepaper": "conference_item",
}

# resource types whose items count as peer-reviewed in the absence of any
# refereeing metadata in InvenioRDM
REFEREED_TYPES = {
    "textDocument-book",
    "textDocument-monograph",
    "textDocument-journalArticle",
    "textDocument-bookSection",
    "textDocument-bookChapter",
    "presentation-conferencePaper",
    "presentation-conferencePresentation",
    "publication-article",
    "publication-book",
    "publication-section",
    "publication-conferencepaper",
}

PAGE_SIZE = 100
INVENIO_MEDIA_TYPE = "application/vnd.inveniordm.v1+json"


class InvenioSource:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.api = config.invenio["api"]
        self.type_map = config.invenio.get("type_map", DEFAULT_TYPE_MAP)
        self.name = config.invenio.get("name") or default_source_name(self.api)
        # an optional provenance recorder, attached by the Repository
        self.recorder = None

    def creator_query(self):
        """The records query for the configured user's name."""
        parts = self.config.user.split()
        family = parts[-1]
        given = " ".join(parts[:-1])

        return f'metadata.creators.person_or_org.name:"{family}, {given}"'

    def orcid_query(self):
        """The records query for the configured user's ORCID, if any."""
        if not getattr(self.config, "orcid", None):
            return None

        return (
            "metadata.creators.person_or_org.identifiers.identifier:"
            f'"{self.config.orcid}"'
        )

    def _search_plan(self):
        """The (strategies, mode) plan for this repository: its entry's
        `search` key, or the historic default of the creator-name query
        unioned with the ORCID query where an ORCID is configured."""
        spec = parse_search_spec(self.config.invenio.get("search"))

        if spec is not None:
            return spec

        strategies = ["name"]
        if getattr(self.config, "orcid", None):
            strategies.append("orcid")

        return strategies, "union"

    def _query_for(self, strategy):
        """
        The records query one search strategy issues
        :param strategy: 'name', 'orcid', or 'query:<raw invenio query>'
        :return: an InvenioRDM query string
        """
        if strategy == "name":
            return self.creator_query()

        if strategy == "orcid":
            query = self.orcid_query()
            if query is None:
                raise SourceConfigurationError(
                    f"{self.name}: the 'orcid' search strategy needs an "
                    "`orcid` in the configuration"
                )
            return query

        if strategy.startswith("query:"):
            return strategy[len("query:") :]

        raise SourceConfigurationError(
            f"{self.name}: unknown InvenioRDM search strategy '{strategy}' "
            "(expected 'name', 'orcid', or 'query:<raw query>')"
        )

    def fetch(self):
        """
        Fetch all of the user's records by running the search plan, and
        normalise them
        :return: a list of internal-format items (unmapped types omitted)
        """
        strategies, mode = self._search_plan()

        records = {}
        for position, strategy in enumerate(strategies):
            query = self._query_for(strategy)
            found = list(self._search(query))

            self.logger.debug(
                f"{self.name}: strategy '{strategy}' returned "
                f"{len(found)} records"
            )

            if self.recorder:
                self.recorder.search_ran(
                    self.name, strategy, query, len(found), mode
                )

            for record in found:
                records[record["id"]] = record

            if mode == "first" and found:
                if self.recorder:
                    for skipped in strategies[position + 1 :]:
                        self.recorder.search_skipped(
                            self.name,
                            skipped,
                            "an earlier strategy already returned records",
                        )
                break

        self.logger.debug(f"Fetched {len(records)} InvenioRDM records")

        items = []
        for record in records.values():
            item = self.normalise(record)
            if item is not None:
                items.append(item)
            elif self.recorder:
                resource_type = (
                    record.get("metadata", {})
                    .get("resource_type", {})
                    .get("id", "")
                )
                self.recorder.record_skipped(
                    self.name,
                    record.get("id"),
                    f"unmapped resource type {resource_type}",
                )

        return items

    def _search(self, query):
        """Yield every record matching a query, following pagination."""
        response = requests.get(
            self.api,
            params={"q": query, "size": PAGE_SIZE},
            headers={"Accept": INVENIO_MEDIA_TYPE},
            timeout=60,
        )

        while True:
            response.raise_for_status()
            payload = response.json()

            yield from payload["hits"]["hits"]

            next_url = payload.get("links", {}).get("next")
            if not next_url:
                break

            response = requests.get(
                urljoin(self.api, next_url),
                headers={"Accept": INVENIO_MEDIA_TYPE},
                timeout=60,
            )

    def normalise(self, record):
        """
        Convert one InvenioRDM record to the internal item shape
        :param record: the InvenioRDM record JSON
        :return: an internal-format item, or None for unmapped types
        """
        metadata = record.get("metadata", {})
        resource_type = metadata.get("resource_type", {}).get("id", "")

        if resource_type not in self.type_map:
            self.logger.debug(
                f"Skipping InvenioRDM record {record.get('id')} "
                f"with unmapped type {resource_type}"
            )
            return None

        item = {
            "type": self.type_map[resource_type],
            "title": metadata.get("title", ""),
            "date": metadata.get("publication_date", ""),
            "uri": self._landing_page(record),
            "refereed": "TRUE" if resource_type in REFEREED_TYPES else "FALSE",
            "creators": [
                {
                    "name": {
                        "given": creator["person_or_org"].get("given_name", ""),
                        "family": creator["person_or_org"].get("family_name", ""),
                    }
                }
                for creator in metadata.get("creators", [])
                if creator.get("person_or_org", {}).get("type") == "personal"
            ],
        }

        if metadata.get("publisher"):
            item["publisher"] = metadata["publisher"]

        self._add_dois(item, record)
        self._add_container(item, record)
        self._add_files(item, record)

        return item

    def _landing_page(self, record):
        """The human-facing record page, derived from the API base."""
        if record.get("links", {}).get("self_html"):
            return record["links"]["self_html"]
        base = self.api.split("/api/")[0]
        return f"{base}/records/{record['id']}"

    def _add_dois(self, item, record):
        """
        Attach DOIs. The repository-minted DOI (pids.doi) identifies the
        deposit, but a publisher DOI recorded as an alternate identifier
        identifies the publication itself, so the latter is preferred as
        the item's main DOI; all DOIs are kept for deduplication.
        """
        minted = record.get("pids", {}).get("doi", {}).get("identifier")
        alternates = [
            identifier["identifier"]
            for identifier in record.get("metadata", {}).get("identifiers", [])
            if identifier.get("scheme") == "doi"
        ]

        all_dois = ([minted] if minted else []) + alternates

        if not all_dois:
            return

        item["doi"] = alternates[0] if alternates else minted
        item["alternate_dois"] = all_dois

    def _add_container(self, item, record):
        """Attach journal or book-container metadata from custom fields."""
        custom = record.get("custom_fields", {})

        journal = custom.get("journal:journal", {})
        if journal.get("title"):
            item["publication"] = journal["title"]
        if journal.get("volume"):
            item["volume"] = journal["volume"]
        if journal.get("issue"):
            item["number"] = journal["issue"]
        if journal.get("pages"):
            item["pagerange"] = journal["pages"]

        imprint = custom.get("imprint:imprint", {})
        if imprint.get("title"):
            item["book_title"] = imprint["title"]
        if imprint.get("pages"):
            item["pagerange"] = imprint["pages"]
        if imprint.get("place"):
            item["place_of_pub"] = imprint["place"]

    def _add_files(self, item, record):
        """Expose openly accessible files as download links."""
        if record.get("access", {}).get("status") != "open":
            return

        entries = record.get("files", {}).get("entries", {})

        documents = []
        files_url = record.get("links", {}).get("files")
        for key, entry in entries.items():
            if entry.get("access", {}).get("hidden"):
                continue

            content_url = entry.get("links", {}).get("content")
            if not content_url and files_url:
                filename = entry.get("key", key)
                content_url = f"{files_url.rstrip('/')}/{quote(filename)}/content"

            if content_url:
                documents.append({"uri": urljoin(self.api, content_url)})

        if documents:
            item["oa_status"] = "green"
            item["documents"] = documents
