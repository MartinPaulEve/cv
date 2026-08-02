"""Per-user configuration loading.

A configuration is a plain Python module describing one scholar: who they
are (name, emails, ORCID), where their metadata lives, and how their CV
should be laid out. Configs live in the config/ directory by default, and
the CLI accepts either a path or a bare name that is resolved against
that directory.
"""

import importlib.util
import os
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def resolve_config_path(name, config_dir=None):
    """
    Resolve a config argument to a real file path. The argument may be an
    explicit path, or a bare name (with or without the .py extension) that
    is looked up in the config directory.
    :param name: the config argument as given on the command line
    :param config_dir: the directory in which bare names are looked up
    :return: the path of the config file
    """
    config_dir = config_dir or str(PROJECT_ROOT / "config")
    candidates = [
        name,
        os.path.join(config_dir, name),
        os.path.join(config_dir, f"{name}.py"),
    ]

    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    raise FileNotFoundError(
        f"No configuration found for '{name}' (tried: {', '.join(candidates)})"
    )


def load_config(path, output_name=None):
    """
    Load a configuration module from a file path
    :param path: the path of the configuration file
    :param output_name: an optional base name for generated output files;
        when given it replaces the configured document name (so `123`
        yields 123.html, 123-PDF.html, 123.pdf) instead of the
        profile-prefixed defaults
    :return: the loaded module
    """
    path = os.path.abspath(path)
    profile = os.path.splitext(os.path.basename(path))[0]
    module_name = f"cv_config_{profile}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    module.profile = getattr(module, "profile", profile)
    module.project_root = str(PROJECT_ROOT)

    if hasattr(module, "storage"):
        module.storage = {
            key: str(_project_path(_profile_cache_path(value, module.profile)))
            for key, value in module.storage.items()
        }

    if hasattr(module, "output_rules"):
        output_rules = {}
        for rule, configured in module.output_rules.items():
            ruleset = list(configured)
            ruleset[0] = str(_project_path(ruleset[0]))
            if _is_filename_less(ruleset):
                stem = output_name or module.profile
                final = f"output/{stem}.{rule}"
                written = (
                    final
                    if len(ruleset) == 1
                    else f"output/{stem}-{rule.upper()}.html"
                )
                ruleset[1:] = [
                    command.replace("[[source]]", written).replace(
                        "[[output]]", final
                    )
                    for command in ruleset[1:]
                ]
                ruleset.insert(1, str(_project_path(written)))
            elif output_name:
                stem = _final_artifact_stem(ruleset)
                ruleset[1] = str(
                    _project_path(_renamed_path(ruleset[1], stem, output_name))
                )
                ruleset[2:] = [
                    _rename_command_outputs(command, stem, output_name)
                    for command in ruleset[2:]
                ]
            else:
                ruleset[1] = str(
                    _project_path(_profile_output_path(ruleset[1], module.profile))
                )
                ruleset[2:] = [
                    _namespace_command_outputs(command, module.profile)
                    for command in ruleset[2:]
                ]
            output_rules[rule] = ruleset
        module.output_rules = output_rules

    if hasattr(module, "csl_directory"):
        module.csl_directory = str(_project_path(module.csl_directory))

    return module


def _project_path(path):
    path = Path(path)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _profile_cache_path(path, profile):
    path = Path(path)
    if path.is_absolute() or profile in path.parts:
        return path
    return path.parent / profile / path.name


def _profile_output_path(path, profile):
    path = Path(path)
    if path.is_absolute() or path.name.startswith(f"{profile}-"):
        return path
    return path.with_name(f"{profile}-{path.name}")


_COMMAND_OUTPUT_PATTERN = re.compile(r"output/[^\s'\"]+")


def _is_filename_less(ruleset):
    """
    Whether an output rule omits its output filename. Such a rule is just
    a template, optionally followed by post-processing commands that
    refer to the derived paths as [[source]] and [[output]]; a command is
    recognisable because a bare output path never contains spaces or
    placeholders.
    :param ruleset: the rule list with its template already resolved
    :return: True for the filename-less form
    """
    if len(ruleset) == 1:
        return True
    return "[[" in ruleset[1] or " " in ruleset[1]


def _final_artifact_stem(ruleset):
    """
    The file stem of the rule's final artifact: the last output path
    named in its post-processing commands, or the output file itself for
    rules with no commands. Intermediate artifacts share this stem plus
    a suffix (CV-PDF.html against CV.pdf), so it is the part an output
    name replaces.
    :param ruleset: the [template, output_file, *commands] rule list
    :return: the stem of the rule's final artifact
    """
    paths = [ruleset[1]]
    for command in ruleset[2:]:
        paths += _COMMAND_OUTPUT_PATTERN.findall(command)
    return Path(paths[-1]).stem


def _renamed_path(path, stem, output_name):
    """Swap a path's leading document stem for the output name."""
    path = Path(path)
    if path.stem.startswith(stem):
        return path.with_name(output_name + path.stem[len(stem) :] + path.suffix)
    return path


def _rename_command_outputs(command, stem, output_name):
    def replace(match):
        return str(_renamed_path(match.group(0), stem, output_name))

    return _COMMAND_OUTPUT_PATTERN.sub(replace, command)


def _namespace_command_outputs(command, profile):
    def replace(match):
        return str(_profile_output_path(match.group(0), profile))

    return re.sub(r"output/[^\s'\"]+", replace, command)


def encode_eprints_user(name):
    """
    Convert a plaintext name to the eprints person-identifier format:
    'Martin Paul Eve' becomes 'Eve=3AMartin_Paul=3A=3A' (the URL-encoded
    form of 'Eve:Martin_Paul::', family name first).
    :param name: the user's name in plain text
    :return: the encoded eprints person identifier
    """
    parts = name.split()
    family = parts[-1]
    given = "_".join(parts[:-1])

    return f"{family}=3A{given}=3A=3A"
