"""cv: build an academic CV, as HTML and PDF, from institutional repositories."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("cv")
except PackageNotFoundError:  # running from a bare checkout without installation
    __version__ = "0.0.0"
