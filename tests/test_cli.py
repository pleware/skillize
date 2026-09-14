from __future__ import annotations

import sys
from pathlib import Path

from skillize.cli import _parse_install_target, main

EXAMPLE_ROOT = Path(__file__).resolve().parents[1] / "examples"


def test_check_example(capsys) -> None:
    assert main(["-C", str(EXAMPLE_ROOT), "check"]) == 0
    out = capsys.readouterr().out
    assert "1 enabled / 2 listed" in out
    assert "api-and-interface-design" in out


def test_check_missing(tmp_path: Path, capsys) -> None:
    assert main(["-C", str(tmp_path), "check"]) == 1
    err = capsys.readouterr().err
    assert "no skillize.yaml" in err


def test_configure_requires_a_terminal(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    assert main(["-C", str(tmp_path), "configure"]) == 2
    err = capsys.readouterr().err
    assert "needs a terminal" in err


def test_install_missing_name(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("SKILLIZE_OFFLINE", "1")
    (tmp_path / "skillize.yaml").write_text(
        "version: 1\nsources:\n  - addyosmani/agent-skills\nskills: {}\n",
        encoding="utf-8",
    )
    assert main(["-C", str(tmp_path), "install", "no-such-skill"]) == 1
    err = capsys.readouterr().err
    assert "no skill named no-such-skill" in err


def test_install_php7_from_bundle(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("SKILLIZE_OFFLINE", "1")
    assert main(["-C", str(tmp_path), "install", "php7"]) == 0
    out = capsys.readouterr().out
    skill = tmp_path / ".agents" / "skills" / "php7" / "SKILL.md"
    assert skill.is_file()
    assert "installed php7" in out
    assert "name: php7" in skill.read_text(encoding="utf-8")


def test_parse_install_target_slug_and_name() -> None:
    assert _parse_install_target("anthropics/skills/frontend-design") == (
        "anthropics/skills",
        "frontend-design",
    )
    assert _parse_install_target("frontend-design") == (None, "frontend-design")
    assert _parse_install_target("owner/repo") == (None, "owner/repo")


def test_uninstall_removes_installed_skill(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("SKILLIZE_OFFLINE", "1")
    assert main(["-C", str(tmp_path), "install", "php7"]) == 0
    skill = tmp_path / ".agents" / "skills" / "php7" / "SKILL.md"
    assert skill.is_file()
    assert main(["-C", str(tmp_path), "uninstall", "php7"]) == 0
    assert not (tmp_path / ".agents" / "skills" / "php7").exists()
    assert "uninstalled php7" in capsys.readouterr().out


def test_uninstall_missing_reports_error(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("SKILLIZE_OFFLINE", "1")
    (tmp_path / "skillize.yaml").write_text("version: 1\nskills: {}\n", encoding="utf-8")
    assert main(["-C", str(tmp_path), "uninstall", "no-such"]) == 1
    assert "not installed" in capsys.readouterr().err


def test_install_hints_when_agentize_present(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("SKILLIZE_OFFLINE", "1")
    (tmp_path / "agentize.yaml").write_text("version: 1\n", encoding="utf-8")
    assert main(["-C", str(tmp_path), "install", "php7"]) == 0
    assert "agentize mount" in capsys.readouterr().err
