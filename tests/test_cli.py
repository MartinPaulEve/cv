"""Behavioural tests for the cv command line interface.

The CLI's job is to dispatch to the repository (fetch) or the builder
(make) with the right arguments. Repository and CiteProc are replaced by
test doubles: these tests exercise dispatch behaviour, not the classes
themselves.
"""

from unittest.mock import MagicMock

import pytest

import cv
from cv import cli


@pytest.fixture
def doubles(monkeypatch, fake_config):
    """Replace the CLI's collaborators with mocks and capture them."""
    repo_instance = MagicMock()
    citeproc_instance = MagicMock()

    monkeypatch.setattr(cli, "Repository", MagicMock(return_value=repo_instance))
    monkeypatch.setattr(cli, "CiteProc", MagicMock(return_value=citeproc_instance))
    monkeypatch.setattr(cli, "load_config", lambda: fake_config)

    return repo_instance, citeproc_instance


def test_package_exposes_a_version():
    assert isinstance(cv.__version__, str)
    assert cv.__version__.count(".") == 2


def test_fetch_uses_default_types_when_none_given(doubles):
    repo, _ = doubles
    cli.main(["fetch"])
    repo.fetch.assert_called_once_with(["books", "articles"])


def test_fetch_passes_explicit_types(doubles):
    repo, _ = doubles
    cli.main(["fetch", "books"])
    repo.fetch.assert_called_once_with(["books"])


def test_make_builds_requested_outputs(doubles):
    _, citeproc = doubles
    cli.main(["make", "html", "pdf"])
    citeproc.build.assert_called_once_with(["html", "pdf"])
