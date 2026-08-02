"""Behavioural tests for per-user configuration loading.

These pin down the contract of the config system: a config argument may
be a real path or a bare name resolved against the config directory; a
loaded config is a module exposing its variables; and plaintext user
names are converted to the eprints escaped person-identifier format so
that nobody has to write 'Eve=3AMartin_Paul=3A=3A' by hand again.
"""

from pathlib import Path

import pytest

from cv.configuration import encode_eprints_user, load_config, resolve_config_path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


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

    def test_default_config_directory_is_independent_of_cwd(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        assert resolve_config_path("martin_paul_eve") == str(
            PROJECT_ROOT / "config" / "martin_paul_eve.py"
        )


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

    def test_profiles_receive_distinct_cache_and_output_paths(self, config_dir):
        common = (
            'storage = {"json": "data/eprints.json"}\n'
            'output_rules = {"html": ["templates/HTML", "output/CV.html"]}\n'
            'csl_directory = "static/csl"\n'
        )
        (config_dir / "jane_doe.py").write_text('user = "Jane Doe"\n' + common)
        (config_dir / "john_doe.py").write_text('user = "John Doe"\n' + common)

        jane = load_config(str(config_dir / "jane_doe.py"))
        john = load_config(str(config_dir / "john_doe.py"))

        assert jane.storage["json"] != john.storage["json"]
        assert jane.output_rules["html"][1] != john.output_rules["html"][1]
        assert "jane_doe" in jane.storage["json"]
        assert "john_doe" in john.output_rules["html"][1]

    def test_relative_project_paths_are_anchored(self, config_dir):
        config_file = config_dir / "jane_doe.py"
        config_file.write_text(
            'user = "Jane Doe"\n'
            'storage = {"json": "data/eprints.json"}\n'
            'output_rules = {"html": ["templates/HTML", "output/CV.html"]}\n'
            'csl_directory = "static/csl"\n'
        )

        config = load_config(str(config_file))

        assert Path(config.storage["json"]).is_absolute()
        assert Path(config.output_rules["html"][0]) == PROJECT_ROOT / "templates/HTML"
        assert Path(config.csl_directory) == PROJECT_ROOT / "static/csl"


class TestEprintsUserEncoding:
    def test_two_part_name(self):
        assert encode_eprints_user("Jane Doe") == "Doe=3AJane=3A=3A"

    def test_three_part_name_keeps_given_names_together(self):
        assert encode_eprints_user("Martin Paul Eve") == "Eve=3AMartin_Paul=3A=3A"

    def test_single_name(self):
        assert encode_eprints_user("Cher") == "Cher=3A=3A=3A"

    def test_surrounding_whitespace_is_ignored(self):
        assert encode_eprints_user("  Jane Doe  ") == "Doe=3AJane=3A=3A"


class TestOutputName:
    @pytest.fixture
    def config_file(self, config_dir):
        (config_dir / "jane_doe.py").write_text(
            'user = "Jane Doe"\n'
            "output_rules = {"
            '"html": ["templates/HTML", "output/CV.html"],'
            '"pdf": ["templates/PDF", "output/CV-PDF.html",'
            ' "uv run cv-print output/CV-PDF.html output/CV.pdf"]}\n'
        )
        return str(config_dir / "jane_doe.py")

    def test_output_name_becomes_the_final_artifact_basename(self, config_file):
        config = load_config(config_file, output_name="123")
        assert config.output_rules["html"][1].endswith("output/123.html")
        assert config.output_rules["pdf"][2].endswith("output/123.pdf")

    def test_intermediate_artifacts_keep_their_suffixes(self, config_file):
        config = load_config(config_file, output_name="123")
        assert config.output_rules["pdf"][1].endswith("output/123-PDF.html")
        assert "output/123-PDF.html" in config.output_rules["pdf"][2]

    def test_output_name_is_not_profile_prefixed(self, config_file):
        config = load_config(config_file, output_name="123")
        assert "jane_doe-" not in config.output_rules["html"][1]
        assert "jane_doe-" not in config.output_rules["pdf"][2]

    def test_templates_are_untouched_by_the_output_name(self, config_file):
        config = load_config(config_file, output_name="123")
        assert Path(config.output_rules["html"][0]) == PROJECT_ROOT / "templates/HTML"

    def test_without_an_output_name_profile_naming_is_unchanged(self, config_file):
        config = load_config(config_file)
        assert config.output_rules["html"][1].endswith("output/jane_doe-CV.html")


class TestFilenameLessOutputRules:
    @pytest.fixture
    def config_file(self, config_dir):
        (config_dir / "jane_doe.py").write_text(
            'user = "Jane Doe"\n'
            "output_rules = {"
            '"html": ["templates/HTML"],'
            '"pdf": ["templates/PDF", "uv run cv-print [[source]] [[output]]"]}\n'
        )
        return str(config_dir / "jane_doe.py")

    def test_rule_without_commands_derives_its_output_from_the_profile(
        self, config_file
    ):
        config = load_config(config_file)
        assert config.output_rules["html"][1].endswith("output/jane_doe.html")

    def test_rule_with_commands_writes_a_source_and_names_the_artifact(
        self, config_file
    ):
        config = load_config(config_file)
        assert config.output_rules["pdf"][1].endswith("output/jane_doe-PDF.html")
        command = config.output_rules["pdf"][2]
        assert "output/jane_doe-PDF.html" in command
        assert command.endswith("output/jane_doe.pdf")
        assert "[[" not in command

    def test_output_name_overrides_the_derived_stem(self, config_file):
        config = load_config(config_file, output_name="123")
        assert config.output_rules["html"][1].endswith("output/123.html")
        assert config.output_rules["pdf"][1].endswith("output/123-PDF.html")
        assert config.output_rules["pdf"][2].endswith("output/123.pdf")

    def test_templates_resolve_as_before(self, config_file):
        config = load_config(config_file)
        assert Path(config.output_rules["html"][0]) == PROJECT_ROOT / "templates/HTML"
