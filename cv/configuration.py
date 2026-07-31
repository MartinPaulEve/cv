"""Per-user configuration loading.

A configuration is a plain Python module describing one scholar: who they
are (name, emails, ORCID), where their metadata lives, and how their CV
should be laid out. Configs live in the config/ directory by default, and
the CLI accepts either a path or a bare name that is resolved against
that directory.
"""

import importlib.util
import os


def resolve_config_path(name, config_dir="config"):
    """
    Resolve a config argument to a real file path. The argument may be an
    explicit path, or a bare name (with or without the .py extension) that
    is looked up in the config directory.
    :param name: the config argument as given on the command line
    :param config_dir: the directory in which bare names are looked up
    :return: the path of the config file
    """
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


def load_config(path):
    """
    Load a configuration module from a file path
    :param path: the path of the configuration file
    :return: the loaded module
    """
    module_name = f"cv_config_{os.path.splitext(os.path.basename(path))[0]}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
