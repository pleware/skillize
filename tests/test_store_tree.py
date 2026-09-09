from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from skillize.cli import main
from skillize.store_tree import (
    CONFIG_NAME,
    GITIGNORE,
    config_is_ignored,
    config_path,
    data_dir,
    ensure_data_dir,
)


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return result.stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "--quiet")
    return tmp_path


def test_policy_lives_at_the_project_root(tmp_path: Path) -> None:
    assert config_path(tmp_path) == tmp_path / "skillize.yaml"
    assert CONFIG_NAME == "skillize.yaml"


def test_the_data_directory_ignores_itself(tmp_path: Path) -> None:
    directory = ensure_data_dir(tmp_path)
    assert (directory / ".gitignore").read_text(encoding="utf-8") == GITIGNORE


def test_a_deny_by_default_repo_hides_the_policy(repo: Path) -> None:
    (repo / ".gitignore").write_text("/*\n!/.gitignore\n", encoding="utf-8")
    assert config_is_ignored(repo)


def test_whitelisting_the_policy_clears_it(repo: Path) -> None:
    (repo / ".gitignore").write_text("/*\n!/.gitignore\n!/skillize.yaml\n", encoding="utf-8")
    assert not config_is_ignored(repo)


def test_init_fails_loudly_when_the_policy_would_be_ignored(repo: Path, capsys) -> None:
    (repo / ".gitignore").write_text("/*\n", encoding="utf-8")
    assert main(["-C", str(repo), "init"]) == 1
    stderr = capsys.readouterr().err
    assert "skillize.yaml is ignored" in stderr
    assert "!/skillize.yaml" in stderr


def test_init_succeeds_in_a_clean_repo(repo: Path) -> None:
    assert main(["-C", str(repo), "init"]) == 0
    assert (data_dir(repo) / ".gitignore").is_file()
