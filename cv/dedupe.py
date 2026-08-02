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

    return {doi for doi in dois if doi}


def _title_key(record):
    """A (normalised title, type) key for records that lack a DOI."""
    title = record.get("title", "")
    title = title.casefold().replace("&", " and ")
    title = _PUNCTUATION_PATTERN.sub("", title)
    title = " ".join(title.split())

    if not title:
        return None

    return (title, record.get("type"))


def merge_records(primary, secondary, recorder=None):
    """
    Merge two record lists, deduplicating duplicates
    :param primary: records from the preferred repository (kept as-is,
        gaps filled from a duplicate where one exists)
    :param secondary: records from the other repository (appended only
        when no earlier record is a duplicate)
    :param recorder: an optional object told about merge decisions:
        filled(target, fields) when a secondary copy fills gaps in an
        earlier record; discarded(record, target, reason) when a
        secondary copy is dropped as a duplicate, with reason a
        ('doi', <matched doi>) or ('title', <title>) tuple; and
        appended(record) when a secondary record joins the list as new
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
        record_doi_values = record_dois(record)

        target = None
        reason = None
        for doi in record_doi_values:
            if doi in by_doi:
                target = by_doi[doi]
                reason = ("doi", doi)
                break

        if target is None:
            title_match = by_title.get(_title_key(record))

            # Title matching exists for records that lack a DOI. Two
            # records carrying different DOIs are distinct even when
            # their titles match.
            if (
                title_match is not None
                and record_doi_values
                and record_dois(title_match)
            ):
                title_match = None

            if title_match is not None:
                target = title_match
                reason = ("title", record.get("title", ""))

        if target is not None:
            # take the best of both: the earlier record keeps its own
            # values and gains any fields only this copy has
            added = [key for key in record if key not in target]
            for key in added:
                target[key] = record[key]
            index(target)
            if recorder is not None:
                if added:
                    recorder.filled(target, added)
                recorder.discarded(record, target, reason)
        else:
            copy = dict(record)
            merged.append(copy)
            index(copy)
            if recorder is not None:
                recorder.appended(copy)

    return merged
