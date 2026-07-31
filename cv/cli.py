"""cv: build an academic CV, as HTML and PDF, from institutional repositories.

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

Info:

CONFIG selects the scholar to build a CV for. It may be a path to a
configuration file, or a bare name that is looked up in the config/
directory: "cv fetch martin_paul_eve" finds config/martin_paul_eve.py.
Copy config/config.py.example to create a new configuration.

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

The tool includes two output options by default, "html" and "pdf". The
fetch mode pulls metadata from the remote repository (or the on-disk
cache, unless --refresh is given); the make mode builds outputs purely
from local cached data.
"""

import logging

from docopt import docopt
from rich.logging import RichHandler

from cv import __version__
from cv.citeproc import CiteProc
from cv.configuration import load_config, resolve_config_path
from cv.repository import Repository

app = f"cv: the academic CV generator {__version__}"


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
    """Parse arguments, load the requested configuration, and dispatch."""
    args = docopt(__doc__, argv=argv, version=app)

    logger = _configure_logging(args["--debug"])
    logger.info(app)

    config = load_config(resolve_config_path(args["CONFIG"]))
    logger.info(f"Building for {config.user}")

    repo = Repository(config, logger, args["--refresh"])
    citeproc = CiteProc(repo, config, logger)

    if args["fetch"]:
        types = args["TYPES"] if args["TYPES"] else config.default_types
        repo.fetch(types)
    elif args["make"]:
        citeproc.build(args["OUTPUT_TYPES"])


def run():
    """Console entry point."""
    main()


if __name__ == "__main__":
    run()
