# cv

This tool builds a PDF and an HTML CV from the metadata held about a scholar
in an institutional repository (at present, an eprints repository).

The project uses [uv](https://docs.astral.sh/uv/) for packaging and running.
There is no separate installation step: `uv run` resolves and installs
dependencies on first use.

# Usage

```
cv: build an academic CV, as HTML and PDF, from institutional repositories.

Usage:
  cv fetch [TYPES ...] [--debug] [--refresh]
  cv make OUTPUT_TYPES... [--debug]
  cv (-h | --help)
  cv --version

Options:
  -h --help     Show this screen.
  --version     Show version.
  --debug       Enable debug output.
  --refresh     Delete cached versions and do a hard refresh from the repository.
```

Valid options for "types" for the fetch operation, by default, are:

* all_books
* unedited_books
* edited_books
* all_peer_reviewed_articles
* peer_reviewed_articles
* other_articles
* reviews
* book_chapters
* conference_items

These can be extended using the configuration mapping system in `config.py`.

An example of default usage might be:

```
uv run cv fetch unedited_books edited_books peer_reviewed_articles --refresh --debug
uv run cv make pdf html
```

The tool includes two output options by default, "html" and "pdf".

The `fetch` mode pulls publication metadata from the remote repository (or the
on-disk cache in `data/`, unless `--refresh` is given); the `make` mode builds
the configured outputs from that cached data without touching the network.

This tool currently requires a working copy of
[citeproc-js-server](https://github.com/zotero/citeproc-js-server); point
`citeproc_js_server_directory` in `config.py` at your checkout.

# Development

Run the tests and the linter with:

```
uv run pytest
uv run ruff check cv tests
```
