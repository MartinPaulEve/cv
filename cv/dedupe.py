"""Merge publication records from multiple repositories.

Where the same publication was deposited in more than one repository, the
primary repository's record (eprints, for now) is kept as the base and
any fields it lacks are filled in from the other copy: the merged record
takes the best of both.

Two records count as duplicates when they share a DOI (however written:
resolver URLs and case differences are normalised, and a DOI hiding in an
eprints official_url counts too), or — because some deposits carry no DOI
at all — when their titles and types are identical after normalisation.
"""

import re

_RESOLVER_PREFIXES = (
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
    "doi:",
)

_DOI_URL_PATTERN = re.compile(r"^https?://(dx\.)?doi\.org/", re.IGNORECASE)

_PUNCTUATION_PATTERN = re.compile(r"[^\w\s]")


def normalise_doi(doi):
    """
    Reduce a DOI to a canonical comparison form: lower case, whitespace
    stripped, resolver prefixes removed
    :param doi: a DOI in any common written form
    :return: the bare, lower-cased DOI
    """
    doi = doi.strip().lower()

    for prefix in _RESOLVER_PREFIXES:
        if doi.startswith(prefix):
            doi = doi[len(prefix) :]
            break

    return doi


def record_dois(record):
    """
    Return the set of normalised DOIs a record carries: the main doi
    field, any alternate DOIs (repositories such as KC Works mint their
    own DOI while recording the publisher's as an alternate identifier),
    and a DOI expressed as the record's official resolver URL
    :param record: an internal-format publication record
    :return: a set of normalised DOI strings
    """
    dois = set()

    if record.get("doi"):
        dois.add(normalise_doi(record["doi"]))

    for alternate in record.get("alternate_dois", []):
        dois.add(normalise_doi(alternate))

    official_url = record.get("official_url", "")
    if _DOI_URL_PATTERN.match(official_url):
        dois.add(normalise_doi(official_url))

    return dois


def _title_key(record):
    """A (normalised title, type) key for records that lack a DOI."""
    title = record.get("title", "")
    title = title.casefold().replace("&", " and ")
    title = _PUNCTUATION_PATTERN.sub("", title)
    title = " ".join(title.split())

    if not title:
        return None

    return (title, record.get("type"))


def merge_records(primary, secondary):
    """
    Merge two record lists, deduplicating duplicates
    :param primary: records from the preferred repository (kept as-is,
        gaps filled from a duplicate where one exists)
    :param secondary: records from the other repository (appended only
        when no earlier record is a duplicate)
    :return: a single merged record list
    """
    merged = [dict(record) for record in primary]

    by_doi = {}
    by_title = {}

    def index(record):
        for doi in record_dois(record):
            by_doi.setdefault(doi, record)
        key = _title_key(record)
        if key:
            by_title.setdefault(key, record)

    for record in merged:
        index(record)

    for record in secondary:
        doi_matches = [
            by_doi[doi] for doi in record_dois(record) if doi in by_doi
        ]
        title_match = by_title.get(_title_key(record))

        target = doi_matches[0] if doi_matches else title_match

        if target is not None:
            # take the best of both: the earlier record keeps its own
            # values and gains any fields only this copy has
            for key, value in record.items():
                if key not in target:
                    target[key] = value
        else:
            copy = dict(record)
            merged.append(copy)
            index(copy)

    return merged
