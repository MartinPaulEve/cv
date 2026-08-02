"""Fetch and classify publication metadata from configured repositories.

The Repository class downloads a scholar's publication lists from every
configured repository source (any number of eprints and InvenioRDM
instances), merges them in declaration order — the first source is
primary; each later source fills gaps in earlier records or appends new
ones, deduplicated by DOI with a title fallback — caches the merged list
on disk, and splits it into per-section files (books, articles, and so
on) according to the rules in the configuration: peer-review status,
editorial status, and whether an item is a book review.
"""

import json
import os
import tempfile

import requests

from cv.dedupe import merge_records
from cv.invenio import InvenioSource
from cv.provenance import ProvenanceRecorder
from cv.sources import (
    ConfigView,
    EprintsSource,
    SourceConfigurationError,
    normalise_source_entries,
)


class Repository:
    def __init__(self, config, logger, refresh):
        """
        Initialise a repository
        :param config: a configuration
        :param logger: a logger
        :param refresh: whether fetch operations should hit the remote endpoint
            even if there is an on-disk copy
        """
        self.config = config
        self.logger = logger
        self.url = self._build_repo_url()
        self.json = None
        self._json_loaded = False
        self.refresh = refresh
        self._type_safe = False

    def __getattr__(self, name):
        """
        A generic getter for undefined attributes that we use to return types
        (e.g. repo.book_sections)
        :param name: the name of the attr
        """
        try:
            with open(self.config.storage[name]) as json_in_file:
                return [json.loads(line) for line in json_in_file.readlines()]
        except OSError:
            self.logger.error(f"Cannot load json from {self.config.storage[name]}")
            return None

    def _build_repo_url(self):
        """
        Creates the endpoint URL for the first configured eprints
        repository, kept as `self.url` for backwards compatibility
        :return: an eprints endpoint URL string, or None when no eprints
            repository is configured
        """
        entries = normalise_source_entries(getattr(self.config, "eprints", None))

        if not entries:
            return None

        url = EprintsSource(self.config, self.logger, entries[0]).url

        self.logger.debug(f"Built repository URL as: {url}")

        return url

    def _build_sources(self):
        """
        Build the ordered list of configured repository sources. Priority
        order is declaration order: every eprints entry first, then every
        InvenioRDM entry, which preserves the historic precedence of
        eprints records over InvenioRDM ones.
        :return: a list of source objects, each with a name and a fetch()
        """
        sources = [
            EprintsSource(self.config, self.logger, entry)
            for entry in normalise_source_entries(
                getattr(self.config, "eprints", None)
            )
        ]

        for entry in normalise_source_entries(
            getattr(self.config, "invenio", None)
        ):
            # each source sees a config whose `invenio` is its own entry
            sources.append(
                InvenioSource(ConfigView(self.config, invenio=entry), self.logger)
            )

        return sources

    def _fetch_all_sources(self, provenance):
        """
        Fetch every configured source and merge the results in priority
        order, recording provenance events along the way
        :param provenance: a ProvenanceRecorder collecting fetch events
        :return: the merged record list, or None on any failure
        """
        sources = self._build_sources()

        if not sources:
            self.logger.error(
                "No repository sources are configured: give at least one "
                "`eprints` or `invenio` entry in the configuration"
            )
            return None

        records = None

        for source in sources:
            name = getattr(source, "name", None) or type(source).__name__
            source.recorder = provenance
            try:
                items = source.fetch()
            except (
                requests.RequestException,
                json.JSONDecodeError,
                SourceConfigurationError,
            ) as exc:
                self.logger.error(f"Error fetching from {name}: {exc}")
                return None

            self.logger.info(f"Fetched {len(items)} items from {name}")

            if records is None:
                records = items
                provenance.base_records(name, items)
            else:
                records = merge_records(
                    records, items, recorder=provenance.for_source(name)
                )

        return records

    def _populate_json(self, refresh):
        """
        Updates the internal json object either from the on-disk file or from
        the configured remote repositories
        :param refresh: whether to refresh from the remote repositories even
            if there is an on-disk representation
        :return: boolean indicating whether the operation succeeded
        """
        if not os.path.isfile(self.config.storage["json"]) or refresh:
            self.logger.debug("Attempting to refresh from configured sources")

            provenance = ProvenanceRecorder(
                profile=getattr(self.config, "profile", None)
            )
            records = self._fetch_all_sources(provenance)

            if records is None:
                self._json_loaded = False
                return False

            temp_path = None
            try:
                destination = self.config.storage["json"]
                os.makedirs(os.path.dirname(destination) or ".", exist_ok=True)
                with tempfile.NamedTemporaryFile(
                    "w",
                    dir=os.path.dirname(destination) or ".",
                    delete=False,
                ) as json_out_file:
                    json.dump(records, json_out_file)
                    temp_path = json_out_file.name
                os.replace(temp_path, destination)
                self._write_provenance(provenance)
                self.json = records
                self._json_loaded = True
                return True
            except OSError:
                self.logger.error(
                    f"Cannot write json data to {self.config.storage['json']}"
                )
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)
                self._json_loaded = False
                return False
        else:
            self.logger.debug(
                f"Attempting to load JSON from data store "
                f"{self.config.storage['json']}"
            )
            try:
                with open(self.config.storage["json"]) as json_in_file:
                    self.json = json.load(json_in_file)
                    self._json_loaded = True
                    return True
            except OSError:
                self.logger.error(
                    f"Cannot load json from {self.config.storage['json']}"
                )
                self._json_loaded = False
                return False

    def _write_provenance(self, provenance):
        """
        Write the provenance log next to the cached data
        :param provenance: the ProvenanceRecorder holding this fetch's
            events
        """
        destination = self.config.storage["json"]
        path = os.path.join(
            os.path.dirname(destination) or ".", "provenance.log"
        )

        try:
            provenance.write(path)
        except OSError as exc:
            self.logger.error(f"Cannot write provenance log to {path}: {exc}")
            return

        self.logger.info(f"Provenance log written to {path}")

    def _parse_json(self, types, load_json=False, check_types=False):
        """
        Parse JSON from eprints into sections
        :param types: the types to parse
        :param load_json: whether this function should attempt to load the JSON
        :param check_types: whether this function should check type validity
        :return: True if successful, otherwise False
        """
        self.logger.debug(f"Attempting to parse types {types}")

        if not self._parse_prechecks(check_types, load_json, types):
            return False

        self.logger.debug("Building output list")
        outputs = self._build_output_types_list(types)

        return self._write_sections_to_disk(outputs)

    def _write_sections_to_disk(self, outputs):
        """
        Writes the outputs to the disk for fast access
        :param outputs: the outputs to write
        :return: True if success, otherwise False
        """
        for output_type, output_list in outputs.items():
            self.logger.debug(
                f"Writing {output_type} to {self.config.storage[output_type]}"
            )
            try:
                destination = self.config.storage[output_type]
                os.makedirs(os.path.dirname(destination) or ".", exist_ok=True)
                with open(destination, "w") as json_out_file:
                    for output in output_list:
                        json_out_file.write(json.dumps(output) + "\n")
            except OSError:
                self.logger.error(
                    f"Cannot write json data to {self.config.storage[output_type]}"
                )
                os.remove(self.config.storage[output_type])
                self._json_loaded = False
                return False
        return True

    def _build_output_types_list(self, types):
        """
        Build a dictionary of output types with corresponding outputs within
        :return: a dictionary of output types as keys with corresponding
            outputs within
        """
        outputs = {output_type: [] for output_type in types}

        eprints_db_vals = list(self.config.eprints_db.values())

        for item in self.json:
            if item["type"] in eprints_db_vals:
                # find all configured section types that match this item, then
                # narrow them down by the section criteria
                potential_types = self._get_potential_types(item)
                potential_types = [
                    potential_type
                    for potential_type in potential_types
                    if potential_type in outputs
                ]
                potential_types = self._filter_by_peer_review(item, potential_types)
                potential_types = self._filter_by_editorial(item, potential_types)
                potential_types = self._filter_by_book_review(item, potential_types)

                for remaining_type in potential_types:
                    outputs[remaining_type].append(item)
            else:
                self.logger.debug(
                    f"Unsure how to handle type {item['type']} "
                    f"for item {item['title']}"
                )

        return outputs

    def _filter_by_book_review(self, item, potential_types):
        """
        Reduces an item type list by its book review criteria
        :param item: the item
        :param potential_types: a list of potential types for the item
        :return: a list of filtered potential types
        """
        filtered_types = []

        for potential_type in potential_types:
            is_review = item["title"].startswith(self.config.review_of)
            setting = self.config.book_review[potential_type]

            if setting == "ANY":
                # this type allows both book reviews and non-reviews
                filtered_types.append(potential_type)
            elif setting and is_review:
                # this type allows only book reviews
                filtered_types.append(potential_type)
            elif not setting and not is_review:
                # this type allows only non-reviews
                filtered_types.append(potential_type)

        self.logger.debug(
            f"Reduced types for {item['title']} to {filtered_types} "
            f"[book review filter]"
        )
        return filtered_types

    def _filter_by_editorial(self, item, potential_types):
        """
        Reduces an item type list by its editorial criteria
        :param item: the item
        :param potential_types: a list of potential types for the item
        :return: a list of filtered potential types
        """
        filtered_types = []

        for potential_type in potential_types:
            setting = self.config.editorial[potential_type]

            if setting == "ANY":
                # this type allows both edited and non-edited items
                filtered_types.append(potential_type)
            elif setting and "editors" in item:
                # this type allows only edited items
                filtered_types.append(potential_type)
            elif not setting and "editors" not in item:
                # this type allows only non-edited items
                filtered_types.append(potential_type)

        self.logger.debug(
            f"Reduced types for {item['title']} to {filtered_types} "
            f"[editorial filter]"
        )
        return filtered_types

    def _filter_by_peer_review(self, item, potential_types):
        """
        Reduces an item type list by its peer-review criteria
        :param item: the item
        :param potential_types: a list of potential types for the item
        :return: a list of filtered potential types
        """
        filtered_types = []

        for potential_type in potential_types:
            refereed = item.get("refereed")
            setting = self.config.peer_reviewed[potential_type]

            if setting == "ANY":
                # this type allows both peer-reviewed and non-peer-reviewed items
                filtered_types.append(potential_type)
            elif setting and refereed == "TRUE":
                # this type allows only peer-reviewed items
                filtered_types.append(potential_type)
            elif not setting and refereed == "FALSE":
                # this type allows only non-peer-reviewed items
                filtered_types.append(potential_type)

        self.logger.debug(
            f"Reduced types for {item['title']} to {filtered_types} "
            f"[peer review filter]"
        )
        return filtered_types

    def _get_potential_types(self, item):
        """
        Builds a list of potential sub-types for an item, which can then be
        matched against the section criteria
        :param item: the JSON item from eprints
        :return: a list of potential sub-types for the item
        """
        sub_types = [
            key for key, val in self.config.eprints_db.items() if val == item["type"]
        ]

        self.logger.debug(
            f"Potential sub-types for item {item['title']} are {sub_types}"
        )
        return sub_types

    def _parse_prechecks(self, check_types, load_json, types):
        """
        A set of pre-checks before we parse the JSON
        :param check_types: A shortcut to recheck types
        :param load_json: A shortcut to load the JSON
        :param types: A list of input types
        :return: True if checks OK, otherwise False
        """
        if load_json and not self._json_loaded:
            self.logger.debug("Loading JSON via shortcut")
            if not self._populate_json(self.refresh):
                return False
        elif not self._json_loaded:
            self.logger.error("JSON is not loaded")
            return False

        if check_types and not self._type_safe:
            self.logger.debug("Checking types via shortcut")
            if not self._check_types(types):
                return False
        elif not self._type_safe:
            self.logger.error("Types are not safe")
            return False

        self.logger.debug("Prechecks all passed")
        return True

    def _check_types(self, types):
        """
        Checks that the correct configuration details exist for all types
        :param types: A list of types to check
        :return: True if types are OK, otherwise False
        """
        self.logger.debug("Checking that all types are valid")
        errors = []

        requirements = [
            (self.config.storage, "storage entry"),
            (self.config.peer_reviewed, "peer review setting"),
            (self.config.editorial, "editorial setting"),
            (self.config.book_review, "book review setting"),
            (self.config.eprints_db, "eprints_db setting"),
        ]

        for input_type in types:
            for mapping, description in requirements:
                if input_type not in mapping:
                    errors.append(f"No {description} found for type {input_type}")

        if errors:
            for err in errors:
                self.logger.error(err)

            self._type_safe = False
            return False

        self._type_safe = True
        return True

    def fetch(self, types):
        """
        Fetches data from the repository and prepares the on-disk structure
        :param types: A list of types to parse from the repository
        :return: True if successful, otherwise False
        """
        if not self._check_types(types):
            return False

        if not self._populate_json(self.refresh):
            return False

        return self._parse_json(types)
