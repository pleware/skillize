"""The store tree: policy file vs machine state.

Policy lives in `skillize.yaml` at the project root, beside `agentize.yaml`
and `ignite.toml`. It is committed. Runtime data lives in `.skillize/`,
which ignores itself. This kit does not write `.cursor/`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

CONFIG_NAME = "skillize.yaml"
DIR_NAME = ".skillize"
SCHEMA_NAME = "v1.json"
GITIGNORE_NAME = ".gitignore"
CATALOGUE_NAME = "catalogue.json"

GITIGNORE = """\
# Managed by skillize. Runtime data only — nothing here belongs in git.
*
"""


def config_path(project_root: Path) -> Path:
    return project_root / CONFIG_NAME


def data_dir(project_root: Path) -> Path:
    return project_root / DIR_NAME


def ensure_data_dir(project_root: Path) -> Path:
    """Create `.skillize/` and make it ignore itself. Never touches the root .gitignore."""
    directory = data_dir(project_root)
    directory.mkdir(parents=True, exist_ok=True)
    ignore_file = directory / GITIGNORE_NAME
    if not ignore_file.is_file() or ignore_file.read_text(encoding="utf-8") != GITIGNORE:
        ignore_file.write_text(GITIGNORE, encoding="utf-8", newline="\n")
    return directory


def catalogue_path(project_root: Path) -> Path:
    return data_dir(project_root) / CATALOGUE_NAME


def config_is_ignored(project_root: Path) -> bool:
    """True when git would ignore `skillize.yaml`."""
    result = subprocess.run(
        ["git", "check-ignore", "-q", "--", CONFIG_NAME],
        cwd=project_root,
        capture_output=True,
    )
    return result.returncode == 0
