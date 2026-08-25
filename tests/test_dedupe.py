"""Behavioural tests for DOI-based record deduplication and merging.

The contract: records from a primary repository (eprints) and a secondary
repository (InvenioRDM) are merged into one list; a publication carried
by both — identified by any shared DOI, however formatted — appears once,
based on the primary record but completed with fields only the secondary
copy has.
"""

from cv.dedupe import (
    merge_records,
    normalise_doi,
    publication_dois,
    record_dois,
)


class TestDoiNormalisation:
    def test_case_is_folded(self):
        assert normalise_doi("10.1234/ABC") == normalise_doi("10.1234/abc")

    def test_resolver_prefixes_are_stripped(self):
        assert normalise_doi("https://doi.org/10.1234/abc") == "10.1234/abc"
        assert normalise_doi("http://dx.doi.org/10.1234/abc") == "10.1234/abc"
        assert normalise_doi("doi:10.1234/abc") == "10.1234/abc"

    def test_whitespace_is_stripped(self):
        assert normalise_doi("  10.1234/abc \n") == "10.1234/abc"


class TestRecordDois:
    def test_primary_doi_field_is_found(self):
        assert record_dois({"doi": "10.1234/abc"}) == {"10.1234/abc"}

    def test_alternate_dois_are_found(self):
        """KC Works mints its own DOI but records the publisher's DOI as an
        alternate identifier; both must count for matching."""
        record = {
            "doi": "10.17613/11px-b370",
            "alternate_dois": ["10.53288/0339.1.00"],
        }
        assert record_dois(record) == {"10.17613/11px-b370", "10.53288/0339.1.00"}

    def test_record_without_doi_has_none(self):
        assert record_dois({"title": "No DOI here"}) == set()

    def test_doi_is_extracted_from_the_official_url(self):
        """Many eprints records carry their DOI only as an official_url
        pointing at the resolver; that DOI must count for matching."""
        record = {"official_url": "https://doi.org/10.1234/abc"}
        assert record_dois(record) == {"10.1234/abc"}

    def test_non_doi_official_url_is_ignored(self):
        record = {"official_url": "https://publisher.example/book"}
        assert record_dois(record) == set()

    def test_blank_doi_values_are_ignored(self):
        assert record_dois({"doi": "  ", "alternate_dois": [""]}) == set()


class TestPublicationDois:
    def test_minted_deposit_doi_is_excluded(self):
        """A DOI the repository minted for its own deposit identifies the
        deposit, not the publication, so it carries no weight when asking
        which work a record describes."""
        record = {
            "doi": "10.17613/M6DW4B",
            "alternate_dois": ["10.17613/M6DW4B"],
            "minted_doi": "10.17613/M6DW4B",
        }
        assert publication_dois(record) == set()

    def test_publisher_doi_survives_alongside_a_minted_one(self):
        record = {
            "doi": "10.53288/0339.1.00",
            "alternate_dois": ["10.17613/11px-b370", "10.53288/0339.1.00"],
            "minted_doi": "10.17613/11px-b370",
        }
        assert publication_dois(record) == {"10.53288/0339.1.00"}

    def test_without_a_minted_doi_every_doi_counts(self):
        record = {"doi": "10.1234/abc"}
        assert publication_dois(record) == {"10.1234/abc"}


class TestMerging:
    def test_shared_doi_yields_one_record_based_on_primary(self):
        primary = [{"title": "Warez (eprints)", "doi": "10.53288/0339.1.00"}]
        secondary = [
            {
                "title": "Warez (KC)",
                "doi": "10.17613/11px-b370",
                "alternate_dois": ["10.53288/0339.1.00"],
            }
        ]

        merged = merge_records(primary, secondary)

        assert len(merged) == 1
        assert merged[0]["title"] == "Warez (eprints)"

    def test_missing_fields_are_filled_from_secondary(self):
        primary = [{"title": "Warez", "doi": "10.53288/0339.1.00"}]
        secondary = [
            {
                "title": "Warez: The Infrastructure and Aesthetics of Piracy",
                "doi": "10.53288/0339.1.00",
                "publisher": "punctum books",
            }
        ]

        merged = merge_records(primary, secondary)

        # the primary's own fields are untouched; its gaps are filled
        assert merged[0]["title"] == "Warez"
        assert merged[0]["publisher"] == "punctum books"

    def test_unmatched_secondary_records_are_appended(self):
        primary = [{"title": "Only in eprints", "doi": "10.1/a"}]
        secondary = [{"title": "Only in KC Works", "doi": "10.2/b"}]

        merged = merge_records(primary, secondary)

        assert [r["title"] for r in merged] == ["Only in eprints", "Only in KC Works"]

    def test_different_doiless_records_are_never_merged(self):
        primary = [{"title": "No DOI, eprints", "type": "book"}]
        secondary = [{"title": "No DOI, KC", "type": "book"}]

        merged = merge_records(primary, secondary)

        assert len(merged) == 2

    def test_same_title_and_type_deduplicate_without_a_doi(self):
        """The Warez case: the eprints deposit has no DOI at all, so an
        identical title and type must be enough to spot the duplicate."""
        primary = [
            {
                "title": "Warez: The Infrastructure and Aesthetics of Piracy",
                "type": "book",
                "isbn": "978-1-68571-036-1",
            }
        ]
        secondary = [
            {
                "title": "Warez: The Infrastructure and Aesthetics of Piracy",
                "type": "book",
                "doi": "10.53288/0339.1.00",
                "publisher": "punctum books",
            }
        ]

        merged = merge_records(primary, secondary)

        assert len(merged) == 1
        assert merged[0]["isbn"] == "978-1-68571-036-1"
        assert merged[0]["publisher"] == "punctum books"

    def test_title_match_ignores_case_and_punctuation(self):
        primary = [{"title": "Password!", "type": "book"}]
        secondary = [{"title": "password", "type": "book", "publisher": "P"}]

        assert len(merge_records(primary, secondary)) == 1

    def test_ampersand_and_the_word_and_are_equivalent_in_titles(self):
        primary = [
            {"title": "University English & Contemporary Fiction", "type": "book"}
        ]
        secondary = [
            {"title": "University English and Contemporary Fiction", "type": "book"}
        ]

        assert len(merge_records(primary, secondary)) == 1

    def test_same_title_different_type_is_not_a_duplicate(self):
        primary = [{"title": "Password", "type": "book"}]
        secondary = [{"title": "Password", "type": "article"}]

        assert len(merge_records(primary, secondary)) == 2

    def test_duplicates_within_the_secondary_list_collapse(self):
        """KC Works can hold two deposits of the same publication; only
        one may survive the merge."""
        primary = []
        secondary = [
            {"title": "Warez", "type": "book", "doi": "10.53288/0339.1.00"},
            {"title": "Warez", "type": "book", "doi": "10.53288/0339.1.00"},
        ]

        assert len(merge_records(primary, secondary)) == 1

    def test_doi_formatting_differences_do_not_defeat_matching(self):
        primary = [{"title": "A", "doi": "https://doi.org/10.1234/ABC"}]
        secondary = [{"title": "A (KC)", "doi": "10.1234/abc", "publisher": "P"}]

        merged = merge_records(primary, secondary)

        assert len(merged) == 1
        assert merged[0]["publisher"] == "P"

    def test_same_title_with_distinct_dois_remains_distinct(self):
        primary = [
            {"title": "Editorial", "type": "article", "doi": "10.1/first"}
        ]
        secondary = [
            {"title": "Editorial", "type": "article", "doi": "10.1/second"}
        ]

        assert len(merge_records(primary, secondary)) == 2

    def test_deposit_only_doi_does_not_block_a_title_match(self):
        """The Literature Against Criticism case: the eprints record's DOI
        lives in its official_url, while the KC Works deposit carries only
        the DOI the repository minted for its own copy. That deposit DOI
        says nothing about which work the record describes, so the title
        match must still collapse the pair."""
        primary = [
            {
                "title": "Literature Against Criticism: University English "
                "& Contemporary Fiction in Conflict",
                "type": "book",
                "official_url": "http://dx.doi.org/10.11647/OBP.0102",
                "place_of_pub": "Cambridge",
            }
        ]
        secondary = [
            {
                "title": "Literature Against Criticism: University English "
                "and Contemporary Fiction in Conflict",
                "type": "book",
                "doi": "10.17613/M6DW4B",
                "alternate_dois": ["10.17613/M6DW4B"],
                "minted_doi": "10.17613/M6DW4B",
            }
        ]

        merged = merge_records(primary, secondary)

        assert len(merged) == 1
        assert merged[0]["place_of_pub"] == "Cambridge"

    def test_two_publication_dois_still_defeat_a_title_match(self):
        """A deposit that records a publisher DOI different from the
        target's really is another publication, minted DOI or not."""
        primary = [
            {
                "title": "Editorial",
                "type": "article",
                "official_url": "https://doi.org/10.1/first",
            }
        ]
        secondary = [
            {
                "title": "Editorial",
                "type": "article",
                "doi": "10.1/second",
                "alternate_dois": ["10.17613/dep1", "10.1/second"],
                "minted_doi": "10.17613/dep1",
            }
        ]

        assert len(merge_records(primary, secondary)) == 2

    def test_deposit_doi_does_not_displace_the_targets_own_doi(self):
        """A title-matched copy must not hand its doi field to a target
        that already carries a publication DOI (say, in its official_url):
        the publisher's DOI, not the deposit's, stays the displayed one.
        The deposit's DOIs still join the record for later matching."""
        primary = [
            {
                "title": "A Book",
                "type": "book",
                "official_url": "https://doi.org/10.11647/OBP.0102",
            }
        ]
        secondary = [
            {
                "title": "A Book",
                "type": "book",
                "doi": "10.17613/M6DW4B",
                "alternate_dois": ["10.17613/M6DW4B"],
                "minted_doi": "10.17613/M6DW4B",
            }
        ]

        merged = merge_records(primary, secondary)

        assert len(merged) == 1
        assert "doi" not in merged[0]
        assert "10.17613/m6dw4b" in record_dois(merged[0])

    def test_doi_still_fills_a_target_without_any_doi(self):
        """The Password case: the eprints record has no DOI in any field,
        so the deposit's DOI is better than none and fills the gap."""
        primary = [
            {
                "title": "Password",
                "type": "book",
                "official_url": "https://publisher.example/password/",
            }
        ]
        secondary = [
            {
                "title": "Password",
                "type": "book",
                "doi": "10.17613/gczc8-8gg64",
                "alternate_dois": ["10.17613/gczc8-8gg64"],
                "minted_doi": "10.17613/gczc8-8gg64",
            }
        ]

        merged = merge_records(primary, secondary)

        assert len(merged) == 1
        assert merged[0]["doi"] == "10.17613/gczc8-8gg64"

    def test_newly_merged_alternate_doi_is_used_for_later_matches(self):
        primary = [{"title": "Primary", "type": "book", "doi": "10.1/a"}]
        secondary = [
            {
                "title": "Repository copy",
                "type": "book",
                "doi": "10.1/a",
                "alternate_dois": ["10.1/a", "10.1/b"],
            },
            {"title": "Third copy", "type": "book", "doi": "10.1/b"},
        ]

        assert len(merge_records(primary, secondary)) == 1
