"""Behavioural tests for the human-readable provenance log.

The deliverable is the written log itself: after a fetch it must record,
per repository, the searches run and how many records each returned;
per final item, which repository provided the base record, which other
repositories contributed which fields, and which duplicate copies were
discarded and why; and any records skipped entirely. The tests therefore
assert on the content of the written file.
"""

import json
import os
from unittest.mock import patch

from cv.dedupe import merge_records
from cv.provenance import ProvenanceRecorder
from cv.repository import Repository


class RecordingSink:
    """A minimal merge recorder capturing the decisions merge_records
    reports, for asserting on the reported facts."""

    def __init__(self):
        self.fills = []
        self.discards = []
        self.appends = []

    def filled(self, target, fields):
        self.fills.append((target.get("title"), sorted(fields)))

    def discarded(self, record, target, reason):
        self.discards.append((record.get("title"), target.get("title"), reason))

    def appended(self, record):
        self.appends.append(record.get("title"))


class TestMergeReporting:
    def test_doi_duplicate_reports_the_matching_doi_and_filled_fields(self):
        primary = [{"title": "Warez", "type": "book", "doi": "10.53288/0339.1.00"}]
        secondary = [
            {
                "title": "Warez (KC)",
                "type": "book",
                "doi": "https://doi.org/10.53288/0339.1.00",
                "publisher": "punctum books",
                "oa_status": "green",
            }
        ]

        sink = RecordingSink()
        merged = merge_records(primary, secondary, recorder=sink)

        assert len(merged) == 1
        assert sink.fills == [("Warez", ["oa_status", "publisher"])]
        assert sink.discards == [
            ("Warez (KC)", "Warez", ("doi", "10.53288/0339.1.00"))
        ]
        assert sink.appends == []

    def test_title_duplicate_reports_a_title_match(self):
        primary = [{"title": "Open Access", "type": "book"}]
        secondary = [{"title": "Open Access", "type": "book", "publisher": "P"}]

        sink = RecordingSink()
        merge_records(primary, secondary, recorder=sink)

        assert sink.discards == [
            ("Open Access", "Open Access", ("title", "Open Access"))
        ]

    def test_new_records_report_as_appended(self):
        primary = [{"title": "Only here", "type": "book", "doi": "10.1/a"}]
        secondary = [{"title": "New one", "type": "article", "doi": "10.2/b"}]

        sink = RecordingSink()
        merge_records(primary, secondary, recorder=sink)

        assert sink.appends == ["New one"]
        assert sink.discards == []
        assert sink.fills == []

    def test_duplicate_with_nothing_to_add_reports_no_fill(self):
        primary = [
            {"title": "Complete", "type": "book", "doi": "10.1/a", "publisher": "P"}
        ]
        secondary = [{"title": "Copy", "type": "book", "doi": "10.1/a"}]

        sink = RecordingSink()
        merge_records(primary, secondary, recorder=sink)

        assert sink.fills == []
        assert len(sink.discards) == 1

    def test_merging_without_a_recorder_is_unchanged(self):
        primary = [{"title": "A", "type": "book", "doi": "10.1/a"}]
        secondary = [{"title": "A (copy)", "type": "book", "doi": "10.1/a"}]

        assert len(merge_records(primary, secondary)) == 1


class TestWrittenLog:
    def _write(self, recorder, tmp_path):
        path = str(tmp_path / "provenance.log")
        recorder.write(path)
        with open(path) as log:
            return log.read()

    def test_log_carries_a_timestamp_header_and_profile(self, tmp_path):
        recorder = ProvenanceRecorder(profile="jane_doe")
        content = self._write(recorder, tmp_path)

        assert "jane_doe" in content
        assert "Fetched:" in content

    def test_searches_are_reported_per_repository(self, tmp_path):
        recorder = ProvenanceRecorder()
        recorder.search_ran(
            "Birkbeck eprints",
            "email",
            "https://eprints.bbk.ac.uk/cgi/exportview/creators_email/x/JSON/x.js",
            12,
            "first",
        )
        recorder.search_skipped(
            "Birkbeck eprints",
            "name",
            "an earlier strategy already returned records",
        )
        recorder.search_ran(
            "KC Works",
            "orcid",
            'metadata.creators.person_or_org.identifiers.identifier:"0000"',
            90,
            "union",
        )

        content = self._write(recorder, tmp_path)

        assert "Birkbeck eprints" in content
        assert "email" in content
        assert "12 records" in content
        assert "first" in content
        assert "skipped (an earlier strategy already returned records)" in content
        assert "KC Works" in content
        assert 'identifiers.identifier:"0000"' in content
        assert "90 records" in content

    def test_items_report_base_fills_and_discards(self, tmp_path):
        recorder = ProvenanceRecorder()
        recorder.base_records(
            "Birkbeck eprints",
            [{"title": "Open Access and the Humanities", "type": "book"}],
        )
        merge_records(
            [
                {
                    "title": "Open Access and the Humanities",
                    "type": "book",
                    "doi": "10.5334/bcg",
                }
            ],
            [
                {
                    "title": "Open Access and the Humanities (KC)",
                    "type": "book",
                    "doi": "10.5334/bcg",
                    "publisher": "Cambridge University Press",
                    "oa_status": "green",
                }
            ],
            recorder=recorder.for_source("KC Works"),
        )

        content = self._write(recorder, tmp_path)

        assert "Open Access and the Humanities" in content
        assert "base record from Birkbeck eprints" in content
        assert "oa_status, publisher filled from KC Works" in content
        assert "discarded as duplicate" in content
        assert "DOI 10.5334/bcg matched" in content

    def test_appended_records_are_attributed_to_their_repository(
        self, tmp_path
    ):
        recorder = ProvenanceRecorder()
        recorder.base_records("Birkbeck eprints", [])
        merge_records(
            [],
            [{"title": "KC Only", "type": "article"}],
            recorder=recorder.for_source("KC Works"),
        )

        content = self._write(recorder, tmp_path)

        assert "KC Only" in content
        assert "base record from KC Works" in content

    def test_skipped_records_are_reported_with_their_reason(self, tmp_path):
        recorder = ProvenanceRecorder()
        recorder.record_skipped(
            "KC Works",
            "zzzzz-00001",
            "unmapped resource type textDocument-blogPost",
        )

        content = self._write(recorder, tmp_path)

        assert "zzzzz-00001" in content
        assert "unmapped resource type textDocument-blogPost" in content

    def test_title_matched_discards_say_so(self, tmp_path):
        recorder = ProvenanceRecorder()
        recorder.base_records(
            "Birkbeck eprints", [{"title": "Warez", "type": "book"}]
        )
        merge_records(
            [{"title": "Warez", "type": "book"}],
            [{"title": "Warez", "type": "book", "publisher": "punctum books"}],
            recorder=recorder.for_source("KC Works"),
        )

        content = self._write(recorder, tmp_path)

        assert "title matched" in content


class TestSourcesRecordSearches:
    def test_invenio_unmapped_types_reach_the_provenance_log(
        self, fake_config, logger, tmp_path
    ):
        from cv.invenio import InvenioSource

        fake_config.orcid = None
        fake_config.invenio = {
            "api": "https://works.example.org/api/records",
            "name": "KC Works",
        }

        blog_record = {
            "id": "zzzzz-00001",
            "pids": {},
            "access": {"status": "open"},
            "metadata": {
                "resource_type": {"id": "textDocument-blogPost"},
                "title": "A Blog Post",
                "publication_date": "2020",
                "creators": [],
            },
        }

        def fake_get(url, **kwargs):
            class Response:
                def json(self):
                    return {"hits": {"hits": [blog_record]}, "links": {}}

                def raise_for_status(self):
                    pass

            return Response()

        source = InvenioSource(fake_config, logger)
        recorder = ProvenanceRecorder()
        source.recorder = recorder

        with patch("cv.invenio.requests.get", side_effect=fake_get):
            source.fetch()

        path = str(tmp_path / "provenance.log")
        recorder.write(path)
        with open(path) as log:
            content = log.read()

        assert "zzzzz-00001" in content
        assert "unmapped resource type textDocument-blogPost" in content

    def test_eprints_first_mode_skips_reach_the_provenance_log(
        self, fake_config, logger, tmp_path
    ):
        from cv.sources import EprintsSource

        source = EprintsSource(
            fake_config,
            logger,
            {"repo": "eprints.example.ac.uk", "search": ["email", "name"]},
        )
        recorder = ProvenanceRecorder()
        source.recorder = recorder

        with patch("cv.sources.requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.text = json.dumps(
                [{"eprintid": 1, "title": "Via email"}]
            )
            source.fetch()

        path = str(tmp_path / "provenance.log")
        recorder.write(path)
        with open(path) as log:
            content = log.read()

        assert "creators_email" in content
        assert "1 records" in content
        assert "skipped" in content


class TestFetchWritesProvenance:
    def test_a_refresh_writes_a_provenance_log_beside_the_cache(
        self, fake_config, logger
    ):
        """The full pipeline behaviour: after a refresh that merges two
        repositories, a provenance.log appears next to the cached JSON
        recording searches, base attribution, fills, and discards."""
        fake_config.invenio = {
            "api": "https://works.example.org/api/records",
            "name": "KC Works",
        }

        eprints_items = [
            {
                "eprintid": 1,
                "type": "book",
                "title": "Shared Book",
                "doi": "10.1/shared",
            }
        ]
        invenio_items = [
            {
                "type": "book",
                "title": "Shared Book (KC)",
                "doi": "10.1/shared",
                "publisher": "KC Press",
            },
            {"type": "article", "title": "KC Only", "refereed": "TRUE"},
        ]

        class FakeInvenioSource:
            def __init__(self, config, logger):
                self.name = config.invenio.get("name")

            def fetch(self):
                return invenio_items

        repo = Repository(fake_config, logger, refresh=True)
        with (
            patch("cv.sources.requests.get") as mock_get,
            patch("cv.repository.InvenioSource", FakeInvenioSource),
        ):
            mock_get.return_value.text = json.dumps(eprints_items)
            assert repo._populate_json(refresh=True) is True

        log_path = os.path.join(
            os.path.dirname(fake_config.storage["json"]), "provenance.log"
        )
        with open(log_path) as log:
            content = log.read()

        # searches: the eprints source ran its default person view
        assert "eprints.example.ac.uk" in content
        assert "1 records" in content
        # items: base attribution, fills, and the discarded duplicate
        assert "Shared Book" in content
        assert "base record from eprints.example.ac.uk" in content
        assert "publisher filled from KC Works" in content
        assert "discarded as duplicate" in content
        assert "DOI 10.1/shared matched" in content
        assert "base record from KC Works" in content

    def test_loading_from_cache_does_not_write_provenance(
        self, fake_config, logger
    ):
        with open(fake_config.storage["json"], "w") as cached:
            json.dump([{"type": "book", "title": "Cached"}], cached)

        repo = Repository(fake_config, logger, refresh=False)
        assert repo._populate_json(refresh=False) is True

        log_path = os.path.join(
            os.path.dirname(fake_config.storage["json"]), "provenance.log"
        )
        assert not os.path.exists(log_path)


class TestHostileMetadataCannotForgeLogLines:
    def test_control_characters_in_remote_metadata_are_escaped(self, tmp_path):
        recorder = ProvenanceRecorder(profile="martin_paul_eve")

        hostile_title = (
            "Real Item'\nKEPT: 'Forged Item'\n  - base record from attacker"
        )
        recorder.base_records("eprints.example.org", [{"title": hostile_title}])
        recorder.search_ran(
            "eprints.example.org",
            "name",
            "https://repo.example.org/?q=1\nKEPT: 'Forged Search Item'",
            3,
            "union",
        )
        recorder.record_skipped(
            "KC Works",
            "rec-1\r\n== Items ==",
            "unmapped resource type x\x1b[31m",
        )

        path = os.path.join(tmp_path, "provenance.log")
        recorder.write(path)
        with open(path) as log:
            content = log.read()
        lines = content.splitlines()

        # exactly one genuine item line: the hostile newlines must not
        # have minted extra KEPT lines or a second Items section
        assert len([line for line in lines if line.startswith("KEPT: ")]) == 1
        assert len([line for line in lines if line == "== Items =="]) == 1

        # raw control characters never reach the log; they appear as
        # visible escapes instead, so no information is silently lost
        assert "\x1b" not in content
        assert "\r" not in content
        assert "\\nKEPT: 'Forged Item'" in content
        assert "\\nKEPT: 'Forged Search Item'" in content
        assert "\\r\\n== Items ==" in content
