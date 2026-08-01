"""cv: build an academic CV, as HTML and PDF, from institutional repositories.

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

Info:

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

These can be extended using the configuration mapping system.

The tool includes two output options by default, "html" and "pdf".
"""

import logging
import os
import sys

from docopt import docopt
from rich.logging import RichHandler

from cv import __version__
from cv.citeproc import CiteProc
from cv.repository import Repository

app = f"cv: the academic CV generator {__version__}"


def load_config():
    """Import the config module from the current working directory.

    The configuration is deliberately a Python module so that users can
    express their CV layout and formatting rules directly. It lives in the
    project directory rather than the installed package, so the working
    directory is put on the path before importing it.
    """
    sys.path.insert(0, os.getcwd())
    import config

    return config


def _configure_logging(debug):
    logging.basicConfig(
        level="NOTSET",
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler()],
    )

    logger = logging.getLogger("rich")
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    return logger


def main(argv=None):
    """Parse arguments and dispatch to fetch or make."""
    args = docopt(__doc__, argv=argv, version=app)

    logger = _configure_logging(args["--debug"])
    logger.info(app)

    config = load_config()

    repo = Repository(config, logger, args["--refresh"])
    citeproc = CiteProc(repo, config, logger)

    try:
        if args["fetch"]:
            types = args["TYPES"] if args["TYPES"] else config.default_types
            repo.fetch(types)
        elif args["make"]:
            citeproc.start()
            citeproc.build(args["OUTPUT_TYPES"])
    finally:
        # always try to shut down the citeproc server
        citeproc.shutdown()


def run():
    """Console entry point."""
    main()


if __name__ == "__main__":
    run()
