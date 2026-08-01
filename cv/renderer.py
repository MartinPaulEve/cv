"""In-process citation rendering via the citeproc npm package.

The CitationRenderer formats CSL-JSON items into bibliography entries by
invoking a small node script once per batch, replacing the previous
arrangement of twelve screen-managed citeproc-js-server processes and one
HTTP request per item. Rendered entries are cached, so formatting the
same items for a second output rule costs nothing.
"""

import json
import os
import subprocess

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RENDER_SCRIPT = os.path.join(PROJECT_ROOT, "scripts", "render-citations.js")


class CitationRenderer:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self._cache = {}

    def style_path(self, style):
        """The on-disk path of a named CSL style."""
        return os.path.join(self.config.csl_directory, f"{style}.csl")

    def locale_path(self):
        """The on-disk path of the configured CSL locale."""
        locale = self.config.citeproc_locale
        return os.path.join(self.config.csl_directory, f"locales-{locale}.xml")

    def render(self, items, style):
        """
        Format CSL-JSON items as bibliography entries
        :param items: a list of CSL-JSON item dictionaries
        :param style: the CSL style name to format with
        :return: a list of formatted HTML entries, one per item, in order
        """
        keys = [self._cache_key(item, style) for item in items]

        uncached = [
            item
            for item, key in zip(items, keys, strict=True)
            if key not in self._cache
        ]

        if uncached:
            rendered = self._render_batch(uncached, style)
            for item, entry in zip(uncached, rendered, strict=True):
                self._cache[self._cache_key(item, style)] = entry

        return [self._cache[key] for key in keys]

    def _render_batch(self, items, style):
        """Run the node renderer over a batch of items."""
        self.logger.debug(f"Rendering {len(items)} citations with {style}")

        result = subprocess.run(
            ["node", RENDER_SCRIPT, self.style_path(style), self.locale_path()],
            input=json.dumps(items),
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Citation rendering failed: {result.stderr}")

        return json.loads(result.stdout)

    @staticmethod
    def _cache_key(item, style):
        # the id field is positional bookkeeping, not content: two identical
        # publications in different sections must share a cache entry
        content = {key: value for key, value in item.items() if key != "id"}
        return (style, json.dumps(content, sort_keys=True))
