"""In-process citation rendering with citeproc-js on an embedded V8.

The CitationRenderer formats CSL-JSON items into bibliography entries by
running the vendored citeproc-js library inside an embedded V8 context
(via mini-racer), replacing the previous arrangement of one node
subprocess per uncached batch. Rendered entries are cached, so
formatting the same items for a second output rule costs nothing.

Each item is rendered as its own single-entry bibliography. That is
deliberate: rendering them together would make CSL substitute repeated
author names with em-dashes, which is wrong for a CV where every entry
should carry its authors.
"""

import json
import os

from py_mini_racer import MiniRacer

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CITEPROC_PATH = os.path.join(PROJECT_ROOT, "static", "js", "citeproc_commonjs.js")

_RENDER_FUNCTION = """
function __render(itemsJson) {
    var items = JSON.parse(itemsJson);
    var entries = [];

    for (var i = 0; i < items.length; i++) {
        __items[items[i].id] = items[i];
    }

    for (var i = 0; i < items.length; i++) {
        __engine.updateItems([items[i].id]);
        var bibliography = __engine.makeBibliography();
        entries.push(bibliography[1][0]);
    }

    return JSON.stringify(entries);
}
"""


class CiteprocEngine:
    """One citeproc-js engine, in an embedded V8 context, per style."""

    def __init__(self, style_path, locale_path):
        with open(style_path) as style_file:
            style = style_file.read()
        with open(locale_path) as locale_file:
            locale = locale_file.read()

        self._serial = 0
        self._context = MiniRacer()

        # citeproc-js ships as a CommonJS module, so give it a module
        # object to attach its exports to
        self._context.eval("var module = {exports: {}};")
        self._context.eval("var exports = module.exports;")
        with open(CITEPROC_PATH) as citeproc_file:
            self._context.eval(citeproc_file.read())
        self._context.eval("var CSL = module.exports;")

        self._context.eval(f"var __locale = {json.dumps(locale)};")
        self._context.eval("var __items = {};")
        self._context.eval(
            "var __engine = new CSL.Engine({"
            "retrieveLocale: function () { return __locale; },"
            "retrieveItem: function (id) { return __items[id]; }"
            f"}}, {json.dumps(style)});"
        )
        self._context.eval(_RENDER_FUNCTION)

    def render(self, items):
        """
        Format CSL-JSON items, each as a single-entry bibliography
        :param items: a list of CSL-JSON item dictionaries
        :return: a list of formatted HTML entries, one per item, in order
        """
        # callers reuse positional item ids across batches, so hand the
        # engine a unique id per rendered item; ids are bookkeeping and
        # never appear in the formatted entries
        prepared = []
        for item in items:
            self._serial += 1
            prepared.append({**item, "id": f"cv-item-{self._serial}"})

        rendered = self._context.call("__render", json.dumps(prepared))

        return json.loads(rendered)


class CitationRenderer:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self._cache = {}
        self._engines = {}

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
        """Render a batch of items with the engine for the given style."""
        self.logger.debug(f"Rendering {len(items)} citations with {style}")

        try:
            engine = self._engines.get(style)
            if engine is None:
                engine = CiteprocEngine(self.style_path(style), self.locale_path())
                self._engines[style] = engine

            return engine.render(items)
        except Exception as error:
            raise RuntimeError(f"Citation rendering failed: {error}") from error

    @staticmethod
    def _cache_key(item, style):
        # the id field is positional bookkeeping, not content: two identical
        # publications in different sections must share a cache entry
        content = {key: value for key, value in item.items() if key != "id"}
        return (style, json.dumps(content, sort_keys=True))
