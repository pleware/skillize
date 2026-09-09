"""The store tree: policy file vs machine state.

Policy lives in `skillize.yaml` at the project root, beside `agentize.yaml`
and `ignite.toml`. It is committed. Runtime data lives in `.skillize/`,
which ignores itself. This kit does not write `.cursor/`.
"""

from __future__ import annotations

from pathlib import Path

CONFIG_NAME = "skillize.yaml"
DIR_NAME = ".skillize"
SCHEMA_NAME = "v1.json"


def config_path(project_root: Path) -> Path:
    return project_root / CONFIG_NAME


def data_dir(project_root: Path) -> Path:
    return project_root / DIR_NAME
