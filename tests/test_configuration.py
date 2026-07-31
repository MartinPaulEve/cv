"""Behavioural tests for per-user configuration loading.

These pin down the contract of the config system: a config argument may
be a real path or a bare name resolved against the config directory; a
loaded config is a module exposing its variables; and plaintext user
names are converted to the eprints escaped person-identifier format so
that nobody has to write 'Eve=3AMartin_Paul=3A=3A' by hand again.
"""

import pytest

from cv.configuration import encode_eprints_user, load_config, resolve_config_path


@pytest.fixture
def config_dir(tmp_path):
    directory = tmp_path / "config"
    directory.mkdir()
    (directory / "jane_doe.py").write_text('user = "Jane Doe"\n')
    return directory


class TestPathResolution:
    def test_explicit_path_is_used_as_given(self, config_dir):
        explicit = str(config_dir / "jane_doe.py")
        assert resolve_config_path(explicit) == explicit

    def test_bare_name_resolves_into_config_directory(self, config_dir):
        assert resolve_config_path(
            "jane_doe", config_dir=str(config_dir)
        ) == str(config_dir / "jane_doe.py")

    def test_name_with_extension_resolves_into_config_directory(self, config_dir):
        assert resolve_config_path(
            "jane_doe.py", config_dir=str(config_dir)
        ) == str(config_dir / "jane_doe.py")

    def test_unresolvable_name_raises_a_clear_error(self, config_dir):
        with pytest.raises(FileNotFoundError, match="nonexistent"):
            resolve_config_path("nonexistent", config_dir=str(config_dir))


class TestLoading:
    def test_loaded_config_exposes_its_variables(self, config_dir):
        config = load_config(str(config_dir / "jane_doe.py"))
        assert config.user == "Jane Doe"

    def test_two_configs_do_not_collide(self, config_dir):
        (config_dir / "other.py").write_text('user = "Someone Else"\n')

        first = load_config(str(config_dir / "jane_doe.py"))
        second = load_config(str(config_dir / "other.py"))

        assert first.user == "Jane Doe"
        assert second.user == "Someone Else"


class TestEprintsUserEncoding:
    def test_two_part_name(self):
        assert encode_eprints_user("Jane Doe") == "Doe=3AJane=3A=3A"

    def test_three_part_name_keeps_given_names_together(self):
        assert encode_eprints_user("Martin Paul Eve") == "Eve=3AMartin_Paul=3A=3A"

    def test_single_name(self):
        assert encode_eprints_user("Cher") == "Cher=3A=3A=3A"

    def test_surrounding_whitespace_is_ignored(self):
        assert encode_eprints_user("  Jane Doe  ") == "Doe=3AJane=3A=3A"
