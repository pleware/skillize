from __future__ import annotations

import sys
from pathlib import Path

from skillize.cli import main

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
