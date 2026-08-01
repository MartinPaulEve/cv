# cv

This tool builds a PDF and an HTML CV from the metadata held about a scholar
in institutional repositories. It can pull from an eprints repository and
from any InvenioRDM repository (KC Works, Zenodo, and others), merging the
results and deduplicating records that were deposited in more than one
place (by DOI, with a title fallback for deposits that carry no DOI; the
eprints record is preferred and its gaps are filled from the other copy).

Both outputs are designed to support WCAG 2.2 AAA accessibility: semantic
list and landmark structure, AAA contrast, accessible link names, and a
tagged PDF with a document outline, produced fully headlessly. The axe-core
gate (`uv run cv-check-access`) checks the generated HTML documents for
automatically detectable issues and verifies that the PDF contains tagging,
language, and outline structures. Manual review remains necessary for WCAG
criteria that cannot be automated.

The project uses [uv](https://docs.astral.sh/uv/) for Python packaging and
running. PDF generation and the accessibility checks drive a headless
Chromium through Playwright, so install the dependencies and the browser
before the first build:

```
uv sync
uv run playwright install chromium
```

# Usage

```
cv: build an academic CV, as HTML and PDF, from institutional repositories.

Usage:
  cv fetch CONFIG [TYPES ...] [--debug] [--refresh]
  cv make CONFIG OUTPUT_TYPES... [--debug]
  cv (-h | --help)
  cv --version

Options:
  -h --help     Show this screen.
  --version     Show version.
  --debug       Enable debug output.
  --refresh     Delete cached versions and do a hard refresh from the repository.
```

CONFIG selects the scholar to build a CV for. It may be a path to a
configuration file, or a bare name that is looked up in the `config/`
directory: `cv fetch martin_paul_eve` finds `config/martin_paul_eve.py`.
To set up your own CV, copy `config/config.py.example` to
`config/<your_name>.py` and fill in the identity block at the top: your
name in plain text, your email addresses, and your ORCID. The eprints
person identifier is derived from your name automatically. The rest of
the file defines your CV's layout: sections, headings, templates, and
outputs are all per-user configuration.

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

These can be extended using the configuration mapping system in your
config file.

An example of default usage might be:

```
uv run cv fetch martin_paul_eve unedited_books edited_books peer_reviewed_articles --refresh --debug
uv run cv make martin_paul_eve pdf html
```

The tool includes two output options by default, "html" and "pdf".

The `fetch` mode pulls publication metadata from the remote repository (or the
on-disk cache in `data/`, unless `--refresh` is given); the `make` mode builds
the configured outputs from that cached data without touching the network.

Citations are formatted in-process with [citeproc-js](https://github.com/Juris-M/citeproc-js),
vendored in `static/js` and run on an embedded V8 engine (mini-racer); the
CSL style and locale are vendored in `static/csl`, so the build needs no
external services and no network access beyond the initial metadata fetch.
PDF generation is fully headless.

# Development

Run the tests and the linter with:

```
uv run pytest
uv run ruff check cv tests
```
