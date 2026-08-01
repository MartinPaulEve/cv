"""A human-readable provenance log for fetched publication records.

When records are merged from several repositories it stops being obvious
where any given CV line came from. The ProvenanceRecorder collects
events during a fetch — the searches run against each repository, the
records each returned, which repository provided the base copy of every
item, which other repositories contributed which fields during merging,
which duplicate copies were discarded and why, and which records were
skipped entirely — and writes them as a clear text log next to the
cached data, so every fetch leaves an auditable trail.
"""

import os
import unicodedata
from datetime import datetime

UNTITLED = "(untitled)"

_ESCAPES = {"\n": "\\n", "\r": "\\r", "\t": "\\t"}


def _clean(value):
    """
    Make a value safe to interpolate into one log line. Metadata arrives
    from remote repositories, so a crafted title or query containing
    newlines could otherwise forge entries in the audit trail; control
    and format characters are rendered as visible escapes instead of
    being obeyed, so nothing is silently lost either.
    :param value: the value to sanitise
    :return: a single-line string with control characters escaped
    """
    cleaned = []
    for char in str(value):
        if char in _ESCAPES:
            cleaned.append(_ESCAPES[char])
        elif unicodedata.category(char) in ("Cc", "Cf"):
            cleaned.append(f"\\u{ord(char):04x}")
        else:
            cleaned.append(char)
    return "".join(cleaned)


class ProvenanceRecorder:
    """Collects fetch and merge events and writes them as readable text."""

    def __init__(self, profile=None):
        self.profile = profile
        # per repository (in first-seen order): a list of search lines
        self._searches = {}
        # records dropped entirely: (source, identifier, reason)
        self._skipped_records = []
        # per final item title (in first-seen order): base repository,
        # field contributions, and discarded duplicate copies
        self._items = {}

    def _source_searches(self, source_name):
        return self._searches.setdefault(source_name, [])

    def _item(self, title):
        title = title or UNTITLED
        return self._items.setdefault(
            title, {"base": None, "fills": [], "discards": []}
        )

    def search_ran(self, source_name, strategy, query, count, mode):
        """
        Record one executed search
        :param source_name: the repository's human-readable name
        :param strategy: the strategy name
        :param query: the query string or URL(s) the strategy issued
        :param count: how many records the search returned
        :param mode: the combine mode the search ran under
        """
        self._source_searches(source_name).append(
            f"strategy '{_clean(strategy)}' (mode: {_clean(mode)}): "
            f"{_clean(query)} -> {count} records"
        )

    def search_skipped(self, source_name, strategy, reason):
        """
        Record a strategy that was never run
        :param source_name: the repository's human-readable name
        :param strategy: the strategy name
        :param reason: why it was skipped
        """
        self._source_searches(source_name).append(
            f"strategy '{_clean(strategy)}': skipped ({_clean(reason)})"
        )

    def record_skipped(self, source_name, identifier, reason):
        """
        Record a repository record that was dropped entirely
        :param source_name: the repository's human-readable name
        :param identifier: the record's identifier in that repository
        :param reason: why it was dropped (e.g. an unmapped resource type)
        """
        self._skipped_records.append((source_name, identifier, reason))

    def base_records(self, source_name, records):
        """
        Attribute a list of records to the repository that provided them
        as base copies (the primary source's full list)
        :param source_name: the repository's human-readable name
        :param records: the internal-format records
        """
        for record in records:
            self._item(record.get("title"))["base"] = source_name

    def for_source(self, source_name):
        """
        A merge recorder bound to one contributing repository, suitable
        for passing to merge_records as its recorder
        :param source_name: the repository's human-readable name
        :return: an object with filled/discarded/appended methods
        """
        return _MergeRecorder(self, source_name)

    def write(self, path):
        """
        Write the collected events as a human-readable text log
        :param path: the file path to write
        """
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as log:
            log.write(self._render())

    def _render(self):
        lines = ["Provenance of fetched publication records"]
        if self.profile:
            lines.append(f"Profile: {self.profile}")
        timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
        lines.append(f"Fetched: {timestamp}")

        lines += ["", "== Searches ==", ""]
        if self._searches:
            for source_name, searches in self._searches.items():
                lines.append(f"[{_clean(source_name)}]")
                lines += [f"  - {search}" for search in searches]
                lines.append("")
        else:
            lines += ["  (none)", ""]

        lines += ["== Skipped records ==", ""]
        if self._skipped_records:
            lines += [
                f"  - {_clean(source_name)}: record {_clean(identifier)} "
                f"skipped ({_clean(reason)})"
                for source_name, identifier, reason in self._skipped_records
            ]
        else:
            lines.append("  (none)")
        lines.append("")

        lines += ["== Items ==", ""]
        if self._items:
            for title, item in self._items.items():
                lines += self._render_item(title, item)
        else:
            lines += ["  (none)", ""]

        return "\n".join(lines)

    def _render_item(self, title, item):
        lines = [f"KEPT: '{_clean(title)}'"]

        if item["base"]:
            lines.append(f"  - base record from {_clean(item['base'])}")

        for source_name, fields in item["fills"]:
            fields = ", ".join(sorted(_clean(field) for field in fields))
            lines.append(f"  - {fields} filled from {_clean(source_name)}")

        for source_name, discarded_title, reason in item["discards"]:
            lines.append(
                f"  - {_clean(source_name)} record '{_clean(discarded_title)}' "
                f"discarded as duplicate ({self._reason_text(reason)})"
            )

        lines.append("")
        return lines

    @staticmethod
    def _reason_text(reason):
        kind, value = reason
        if kind == "doi":
            return f"DOI {_clean(value)} matched"
        return "title matched"


class _MergeRecorder:
    """The merge_records-facing recorder, bound to the repository whose
    records are being merged in."""

    def __init__(self, provenance, source_name):
        self.provenance = provenance
        self.source_name = source_name

    def filled(self, target, fields):
        self.provenance._item(target.get("title"))["fills"].append(
            (self.source_name, list(fields))
        )

    def discarded(self, record, target, reason):
        self.provenance._item(target.get("title"))["discards"].append(
            (self.source_name, record.get("title") or UNTITLED, reason)
        )

    def appended(self, record):
        self.provenance._item(record.get("title"))["base"] = self.source_name
