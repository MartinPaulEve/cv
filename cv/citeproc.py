"""Render publication metadata into formatted CV sections.

The CiteProc class converts eprints items into CSL-JSON, sends them to a
citeproc-js-server instance for bibliographic formatting, and assembles
the results — together with static section files and template documents —
into the final HTML outputs.
"""

import os
import re
import subprocess
import time
from contextlib import suppress
from datetime import datetime
from multiprocessing.pool import Pool

import requests

from cv.accessibility import strip_markup

# fallback open access colours, used when a configuration predates the
# oa_colors setting; both meet the WCAG AAA 7:1 contrast ratio on white
DEFAULT_OA_COLORS = {"gold": "#6B5300", "green": "#175117"}


class CiteProc:
    def __init__(self, repo, config, logger):
        self.config = config
        self.logger = logger
        self.repo = repo

        self.cached_italic_regexen = []

        # the commands used to start the citeproc-js server instances
        self.init_commands = [
            f'screen -S serve_npm{port} -d -m bash -c '
            f'"node lib/citeServer.js --port {port} > log.txt"'
            for port in config.citeproc_ports
        ]

    def start(self):
        """
        Start the NPM citeproc-js server
        :return: Nothing
        """
        for shell_script in self.init_commands:
            subprocess.call(
                shell_script,
                shell=True,
                cwd=self.config.citeproc_js_server_directory,
            )
        time.sleep(self.config.citeproc_delay)
        self.logger.info("Started citeproc-js-server(s)")

    def shutdown(self):
        """
        Shutdown the NPM citeproc-js server
        :return: Nothing
        """
        shutdown_commands = [
            f'screen -d -m bash -c "screen -S serve_npm{port} -X quit"'
            for port in self.config.citeproc_ports
        ]

        for shell_script in shutdown_commands:
            subprocess.call(shell_script, shell=True)

        self.logger.info("Shutdown citeproc-js-server")

    def build(self, rules):
        """
        Build the outputs for the given ruleset names (e.g. html, pdf)
        :param rules: a list of output rule names from the configuration
        :return: True if successful, otherwise False
        """
        for rule in rules:
            if rule not in self.config.output_rules:
                self.logger.error(f"Ruleset {rule} is not defined")
                return False

            self.logger.debug(f"Loading ruleset for {rule}")
            ruleset = self.config.output_rules[rule]

            template_file = ruleset[0]
            output_file = ruleset[1]

            template = self._load_template(template_file)

            if not template:
                return False

            template = self._substitute_template(template, rule)

            if not template:
                return False

            try:
                with open(output_file, "w") as out_file:
                    out_file.write(template)
            except OSError:
                self.logger.error(f"Cannot write output to {output_file}")
                with suppress(OSError):
                    os.remove(output_file)
                return False

            # run any post-processing shell commands in the ruleset
            for shell_script in ruleset[2:]:
                self.logger.debug(f"Calling shell script {shell_script}")
                subprocess.call(shell_script, shell=True)
        return True

    def _load_template(self, template):
        """
        Load a template file from disk
        :param template: the file to load
        :return: a string of the template or None if the operation fails
        """
        try:
            with open(template) as template_file:
                content = [line.rstrip("\n") for line in template_file]

            return "\n".join(content)
        except OSError:
            self.logger.error(f"Cannot load template from {template}")
            return None

    def _substitute_template(self, template, rule):
        """
        Substitute sections and eprint sections into a template document
        :param template: the template string
        :param rule: the output rule in play
        :return: a substituted template
        """
        matches = re.findall("{{(.+?)}}", template)
        for match in matches:
            self.logger.debug(f"Processing template section '{match}'")
            section = re.compile(r"{{" + match + "}}")
            if match in self.config.section_headings[rule]:
                substitute = self._eprint_substitute(match, rule)
            elif match.startswith("external:"):
                # run an external command that yields a section into a file
                # these should be in the format:
                # external:path_to_executable:working_directory:output_file
                split_line = match.split(":")

                subprocess.call(split_line[1], shell=True, cwd=split_line[2])

                with open(split_line[3]) as external_file:
                    substitute = external_file.read()
            else:
                try:
                    section_file = "sections/" + match
                    with open(section_file) as section_input:
                        content = [line.rstrip("\n") for line in section_input]
                        substitute = "\n".join(content)
                except OSError:
                    self.logger.error("Cannot load section.")
                    return False

            template = section.sub(str(substitute), template)

        return template

    @staticmethod
    def _build_date(item):
        """
        Builds a date for an item
        :param item: The item on which to work
        :return: a formatted date
        """
        try:
            the_date = datetime.strptime(item["date"][0:4], "%Y").year
        except (KeyError, TypeError, ValueError):
            the_date = "n.d."

        return the_date

    @staticmethod
    def _build_precise_date(item):
        """
        Builds a year/month/day date for an item, falling back to a year
        :param item: The item on which to work
        :return: a formatted date
        """
        try:
            parsed = datetime.strptime(item["date"], "%Y-%m-%d")
            the_date = [parsed.year, parsed.month, parsed.day]
        except (KeyError, TypeError, ValueError):
            the_date = CiteProc._build_date(item)

        return the_date

    def _italicize_titles(self, item, rule):
        """
        Italicizes titles
        :param item: The item on which to work
        :param rule: The current rule
        :return: nothing
        """
        if not self.config.italicize_titles[rule]:
            return

        # build a cached list of italic regexen if it doesn't exist
        if len(self.cached_italic_regexen) == 0:
            self.cached_italic_regexen = [
                re.compile(rf"(\W|^)({re.escape(italic)})(\W|$)")
                for italic in self.config.titles_to_italicize
            ]

        for italic in self.cached_italic_regexen:
            item["title"] = re.sub(italic, r"\1<i>\2</i>\3", item["title"])

    def _link_to_official_url_if_gold_oa(self, item, rule):
        """
        If setting is enabled, change the link to the official URL if the item
        is gold open access
        :param item: The item on which to work
        :param rule: The rule on which to operate
        :return: nothing
        """
        if (
            self.config.gold_oa_direct_link[rule]
            and item.get("oa_status") == "gold"
            and "official_url" in item
        ):
            item["uri"] = item["official_url"]

    def _build_oa_status(self, item, rule):
        """
        Builds an open access status for an item
        :param item: The item on which to work
        :param rule: The rule on which to operate
        :return: a string of the OA status of the item
        """
        oa_status = ""

        if rule in self.config.oa_status:
            oa_status = self.config.oa_status[rule]
            non_oa_status = self.config.non_oa_status[rule]

            # the accessible name must identify the link target as plain text
            # (WCAG 2.4.9) and state the route so that gold versus green is
            # not conveyed by colour alone (WCAG 1.4.1)
            oa_status = oa_status.replace("[[title]]", strip_markup(item["title"]))
            oa_status = oa_status.replace("[[oa_route]]", item.get("oa_status", ""))

            if "oa_status" in item:
                if item["oa_status"] == "green" or item["oa_status"] == "gold":
                    oa_colors = getattr(self.config, "oa_colors", DEFAULT_OA_COLORS)
                    oa_color = oa_colors[item["oa_status"]]
                    if "files" in item:
                        oa_status = (
                            oa_status.replace("[[oa_uri]]", item["files"][0]["url"])
                            .replace("[[oa_color]]", oa_color)
                            .replace("[[doc]]", "")
                        )
                    elif "documents" in item:
                        if len(item["documents"]) > 1:
                            for doc in item["documents"]:
                                doc_label = (
                                    " " + doc["formatdesc"]
                                    if "formatdesc" in doc
                                    else ""
                                )
                                oa_status = (
                                    oa_status.replace("[[oa_uri]]", doc["uri"])
                                    .replace("[[oa_color]]", oa_color)
                                    .replace("[[doc]]", doc_label)
                                )
                        else:
                            oa_status = (
                                oa_status.replace(
                                    "[[oa_uri]]", item["documents"][0]["uri"]
                                )
                                .replace("[[oa_color]]", oa_color)
                                .replace("[[doc]]", "")
                            )
                    else:
                        oa_status = non_oa_status.replace(
                            "[[email]]", self.config.email
                        ).replace("[[title]]", item["title"])
            else:
                oa_status = non_oa_status.replace(
                    "[[email]]", self.config.email
                ).replace("[[title]]", item["title"])

        return oa_status

    @staticmethod
    def _substitute_item_template(template, citeproc, the_date, item, oa_status):
        """
        Substitutes variables into an item template. This handles [[year]],
        [[oa_status]] and [[citeproc]].
        :param template: the template string
        :param citeproc: the formatted citeproc entry
        :param the_date: the date to use
        :param item: the eprints item
        :param oa_status: the formatted open access status string
        :return: a formatted output line
        """
        # citeproc returns a div; convert it to a link to the item
        citeproc = citeproc.replace("<div", '<a href="{}"'.format(item["uri"]))
        citeproc = citeproc.replace("</div", "</a")

        line = template.replace("[[citeproc]]", citeproc)
        line = line.replace("[[year]]", str(the_date))
        line = line.replace("[[oa_status]]", oa_status)

        return line

    @staticmethod
    def _get_citeproc_response(citeproc_server, citeproc_style, output, rule, port):
        # we have to do this _every_ time sadly because otherwise the CSL
        # substitutes repeated author names with "---"
        response = requests.post(
            f"{citeproc_server.format(port)}?bibliography=1&responseformat=json&style={citeproc_style[rule]}",
            json=output,
        )

        return response.json()

    def _eprint_substitute(self, section, rule):
        """
        Substitute in a section from the repository
        :param section: the section
        :param rule: the rule
        :return: the output for a section
        """
        # load up the templates for this section
        self.logger.debug(f"Loading sub-templates for {rule} {section}")
        section_template = self.config.section_template[rule]
        header_template = self.config.header_template[rule]
        item_templates = self.config.citeproc_item_templates[rule][section]
        item_templates_new_date = self.config.citeproc_item_templates_new_date[rule][
            section
        ]

        # get the items from the repo
        self.logger.debug(f"Fetching {section} from repo")
        section_items = self.repo.__getattr__(section)

        current_date = ""

        output = {}
        items = {}
        counter = 0

        output["items"] = items
        output_string = ""

        exclude_items = self.config.exclude_venues

        item_count = len(section_items)

        if rule in exclude_items and section in exclude_items[rule]:
            exclude_venues = exclude_items[rule][section].split(",")
        else:
            exclude_venues = []

        identifier_list = []
        starmap_args = []
        the_date_list = []
        item_list = []
        for port_var, item in enumerate(section_items):
            # spread requests across the available citeproc server ports
            port = self.config.citeproc_ports[
                port_var % len(self.config.citeproc_ports)
            ]
            if "publication" in item and item["publication"] in exclude_venues:
                item_count -= 1
            else:
                # format the date
                the_date = self._build_date(item)

                # italicize title
                self._italicize_titles(item, rule)

                # build the CSL-JSON for this item
                identifier = f"{counter}-{the_date}"
                items[identifier] = {}

                items[identifier]["id"] = identifier
                items[identifier]["title"] = item["title"]

                self._build_creators(identifier, item, items)
                self._build_editors(identifier, item, items)

                items[identifier]["type"] = self.config.citeproc_type_mapper[section]

                self._build_publisher(identifier, item, items)

                items[identifier]["issued"] = {"date-parts": [[the_date]]}

                self._build_container(identifier, item, items)
                self._build_volume(identifier, item, items)
                self._build_pages(identifier, item, items)
                self._build_identifier(identifier, item, items, rule)
                self._build_event(identifier, item, items)

                item_list.append(item)
                identifier_list.append(identifier)
                the_date_list.append(the_date)

                starmap_args.append(
                    (
                        self.config.citeproc_server,
                        self.config.citeproc_style,
                        output,
                        rule,
                        port,
                    )
                )

                output = {}
                items = {}
                output["items"] = items

                counter += 1

        # spawn requests to citeproc server(s) using multiprocessing
        with Pool() as pool:
            json_response = pool.starmap(self._get_citeproc_response, starmap_args)

        for loop_counter, item in enumerate(item_list):
            # build the oa_status
            oa_status = self._build_oa_status(item, rule)

            output_string, current_date = self._append_item(
                current_date,
                item,
                item_templates,
                item_templates_new_date,
                json_response[loop_counter],
                oa_status,
                output_string,
                the_date_list[loop_counter],
            )

        return self._finalize_section(
            header_template, item_count, output_string, rule, section, section_template
        )

    def _build_container(self, identifier, item, items):
        # if the type is 'book', don't add a container
        # this is because eprints seems sometimes to add book_title and title
        # to a book, which in turn causes citeproc problems
        if item["type"] != "book":
            if "publication" in item:
                items[identifier]["container-title"] = item["publication"]
            elif "book_title" in item:
                items[identifier]["container-title"] = item["book_title"]

    def _finalize_section(
        self,
        header_template,
        item_count,
        output_string,
        rule,
        section,
        section_template,
    ):
        if item_count > 0:
            header_output = header_template.format(
                self.config.section_headings[rule][section], item_count
            )

            # publication runs are wrapped in a real list element so that
            # assistive technology announces them as navigable lists
            list_templates = getattr(self.config, "list_template", {})
            if rule in list_templates:
                output_string = list_templates[rule].format(output_string)

            section_output = section_template.format(
                section, header_output + output_string
            )
        else:
            section_output = ""
        return section_output

    def _append_item(
        self,
        current_date,
        item,
        item_templates,
        item_templates_new_date,
        json_response,
        oa_status,
        output_string,
        the_date,
    ):
        if len(json_response["bibliography"][1]) > 0:
            if current_date != the_date:
                line = self._substitute_item_template(
                    item_templates_new_date,
                    json_response["bibliography"][1][0],
                    the_date,
                    item,
                    oa_status,
                )
                current_date = the_date
            else:
                line = self._substitute_item_template(
                    item_templates,
                    json_response["bibliography"][1][0],
                    the_date,
                    item,
                    oa_status,
                )

            output_string += line

        return output_string, current_date

    def _build_identifier(self, identifier, item, items, rule):
        if "doi" in item:
            items[identifier]["DOI"] = item["doi"]

        # setup official links for gold OA
        self._link_to_official_url_if_gold_oa(item, rule)

    def _build_publisher(self, identifier, item, items):
        if "publisher" in item:
            items[identifier]["publisher"] = item["publisher"]
        if "place_of_pub" in item:
            items[identifier]["publisher-place"] = item["place_of_pub"]

    def _build_event(self, identifier, item, items):
        if "event_title" in item:
            items[identifier]["event"] = item["event_title"]
        if "event_location" in item:
            items[identifier]["event-place"] = item["event_location"]
            items[identifier]["publisher-place"] = item["event_location"]

            # build a more precise date
            new_date = CiteProc._build_precise_date(item)

            if not isinstance(new_date, int) and len(new_date) > 1:
                items[identifier]["issued"] = {"date-parts": [new_date]}

    def _build_volume(self, identifier, item, items):
        if "volume" in item:
            try:
                items[identifier]["volume"] = int(item["volume"])
            except ValueError:
                items[identifier]["volume"] = item["volume"]

        if "number" in item:
            try:
                items[identifier]["issue"] = int(item["number"])
            except ValueError:
                items[identifier]["issue"] = item["number"]

    def _build_pages(self, identifier, item, items):
        if "pagerange" in item:
            items[identifier]["page"] = item["pagerange"]

    def _build_editors(self, identifier, item, items):
        # build the editors list
        if self.config.editors_item_name in item and (
            len(item[self.config.editors_item_name]) > 0
        ):
            items[identifier]["editor"] = []

            for editor in item[self.config.editors_item_name]:
                editor_dict = {
                    "family": editor[self.config.editor_field_top_level][
                        self.config.editor_field_last_name
                    ],
                    "given": editor[self.config.editor_field_top_level][
                        self.config.editor_field_given_name
                    ],
                }

                items[identifier]["editor"].append(editor_dict)

    def _build_creators(self, identifier, item, items):
        # build the authors list
        if self.config.creators_item_name in item and (
            len(item[self.config.creators_item_name]) > 0
        ):
            items[identifier]["author"] = []

            for creator in item[self.config.creators_item_name]:
                creator_dict = {
                    "family": creator[self.config.creator_field_top_level][
                        self.config.creator_field_last_name
                    ],
                    "given": creator[self.config.creator_field_top_level][
                        self.config.creator_field_given_name
                    ],
                }

                items[identifier]["author"].append(creator_dict)
