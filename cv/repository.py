"""Fetch and classify publication metadata from an eprints repository.

The Repository class downloads a scholar's publication list from an
eprints "exportview" JSON endpoint, caches it on disk, and splits it into
per-section files (books, articles, and so on) according to the rules in
the configuration: peer-review status, editorial status, and whether an
item is a book review.
"""

import json
import os
import tempfile

import requests

from cv.configuration import encode_eprints_user
from cv.dedupe import merge_records
from cv.invenio import InvenioSource


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
        Creates the eprints endpoint URL
        :return: an eprints endpoint URL string
        """
        repo = self.config.eprints["repo"]

        if not repo.startswith("htt"):
            repo = "https://" + repo

        if not repo.endswith("/"):
            repo += "/"

        # a pre-encoded eprints user in the config wins; otherwise the
        # identifier is derived from the plaintext user name
        if "user" in self.config.eprints:
            user = self.config.eprints["user"]
        else:
            user = encode_eprints_user(self.config.user)
        url = f"{repo}cgi/exportview/people/{user}/JSON/{user}.js"

        self.logger.debug(f"Built repository URL as: {url}")

        return url

    def _populate_json(self, refresh):
        """
        Updates the internal json object either from the on-disk file or from
        the remote repo
        :param refresh: whether to refresh from the remote repository even if
            there is an on-disk representation
        :return: boolean indicating whether the operation succeeded
        """
        if not os.path.isfile(self.config.storage["json"]) or refresh:
            self.logger.debug(f"Attempting to refresh {self.url}")

            try:
                response = requests.get(self.url, timeout=60)
                response.raise_for_status()
                records = json.loads(response.text)
            except (requests.RequestException, json.JSONDecodeError) as exc:
                self.logger.error(f"Error fetching eprints data: {exc}")
                self._json_loaded = False
                return False

            # merge in any configured InvenioRDM repository (e.g. KC Works),
            # deduplicating by DOI with the eprints record preferred
            if getattr(self.config, "invenio", None):
                try:
                    invenio_items = InvenioSource(
                        self.config, self.logger
                    ).fetch()
                except requests.RequestException as exc:
                    self.logger.error(f"Error fetching InvenioRDM data: {exc}")
                    self._json_loaded = False
                    return False
                self.logger.info(
                    f"Merging {len(invenio_items)} InvenioRDM items "
                    f"with {len(records)} eprints items"
                )
                records = merge_records(records, invenio_items)

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
