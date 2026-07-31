"""Fetch and normalise publication metadata from an InvenioRDM repository.

This targets KC Works (works.hcommons.org) in particular, but the API
endpoint is configurable, so any InvenioRDM instance — Zenodo, for
example — should work. Records are normalised into the same internal
item shape that the eprints pipeline consumes, so everything downstream
of fetching is source-agnostic.

Two searches are run and unioned: one by the creator's name and, where an
ORCID is configured, one by that identifier. Neither alone is complete —
records imported from legacy systems often lack ORCIDs, while a name
match can miss variant forms — so the union is the safest net.
"""

import requests

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
}

PAGE_SIZE = 100


class InvenioSource:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.api = config.invenio["api"]
        self.type_map = config.invenio.get("type_map", DEFAULT_TYPE_MAP)

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

    def fetch(self):
        """
        Fetch all of the user's records and normalise them
        :return: a list of internal-format items (unmapped types omitted)
        """
        queries = [self.creator_query()]
        if self.orcid_query():
            queries.append(self.orcid_query())

        records = {}
        for query in queries:
            for record in self._search(query):
                records[record["id"]] = record

        self.logger.debug(f"Fetched {len(records)} InvenioRDM records")

        items = []
        for record in records.values():
            item = self.normalise(record)
            if item is not None:
                items.append(item)

        return items

    def _search(self, query):
        """Yield every record matching a query, following pagination."""
        response = requests.get(
            self.api, params={"q": query, "size": PAGE_SIZE}, timeout=60
        )

        while True:
            response.raise_for_status()
            payload = response.json()

            yield from payload["hits"]["hits"]

            next_url = payload.get("links", {}).get("next")
            if not next_url:
                break

            response = requests.get(next_url, timeout=60)

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

        documents = [
            {"uri": entry["links"]["content"]}
            for entry in entries.values()
            if entry.get("links", {}).get("content")
        ]

        if documents:
            item["oa_status"] = "green"
            item["documents"] = documents
