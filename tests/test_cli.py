"""Behavioural tests for the cv command line interface.

The CLI's job is to resolve the config argument, load that configuration,
and dispatch to the repository (fetch) or the builder (make) with the
right arguments. Repository and CiteProc are replaced by test doubles:
these tests exercise dispatch behaviour, not the classes themselves.
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
    resolved = {}

    def fake_resolve(name, config_dir="config"):
        resolved["name"] = name
        return f"/resolved/{name}"

    monkeypatch.setattr(cli, "Repository", MagicMock(return_value=repo_instance))
    monkeypatch.setattr(cli, "CiteProc", MagicMock(return_value=citeproc_instance))
    monkeypatch.setattr(cli, "resolve_config_path", fake_resolve)
    monkeypatch.setattr(cli, "load_config", lambda path: fake_config)

    return repo_instance, citeproc_instance, resolved


def test_package_exposes_a_version():
    assert isinstance(cv.__version__, str)
    assert cv.__version__.count(".") == 2


def test_config_argument_is_resolved(doubles):
    _, _, resolved = doubles
    cli.main(["fetch", "jane_doe"])
    assert resolved["name"] == "jane_doe"


def test_fetch_uses_default_types_when_none_given(doubles):
    repo, _, _ = doubles
    repo.fetch.return_value = True
    cli.main(["fetch", "jane_doe"])
    repo.fetch.assert_called_once_with(["books", "articles"])


def test_fetch_passes_explicit_types(doubles):
    repo, _, _ = doubles
    repo.fetch.return_value = True
    cli.main(["fetch", "jane_doe", "books"])
    repo.fetch.assert_called_once_with(["books"])


def test_make_builds_requested_outputs(doubles):
    _, citeproc, _ = doubles
    citeproc.build.return_value = True
    cli.main(["make", "jane_doe", "html", "pdf"])
    citeproc.build.assert_called_once_with(["html", "pdf"])


def test_failed_fetch_returns_nonzero_status(doubles):
    repo, _, _ = doubles
    repo.fetch.return_value = False

    assert cli.main(["fetch", "jane_doe"]) == 1


def test_failed_build_returns_nonzero_status(doubles):
    _, citeproc, _ = doubles
    citeproc.build.return_value = False

    assert cli.main(["make", "jane_doe", "html"]) == 1


def test_list_shaped_eprints_config_is_dispatchable(doubles, fake_config):
    """A config giving `eprints` as a list of repositories must still load
    and dispatch; the display name falls back to a pre-encoded user from
    any entry when no plaintext user is configured."""
    repo, _, _ = doubles
    repo.fetch.return_value = True
    del fake_config.user
    fake_config.eprints = [
        {"repo": "a.example.org"},
        {"repo": "b.example.org", "user": "Listed=3APerson=3A=3A"},
    ]

    assert cli.main(["fetch", "multi"]) == 0


def test_legacy_config_uses_pre_encoded_user_as_display_name(doubles, fake_config):
    repo, _, _ = doubles
    repo.fetch.return_value = True
    del fake_config.user
    fake_config.eprints["user"] = "Legacy=3APerson=3A=3A"

    assert cli.main(["fetch", "legacy"]) == 0
