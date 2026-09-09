"""The file you type is not the package. It is a trampoline into `uvx`.

A project commits three tiny launchers (`skillize`, `skillize.ps1`,
`skillize.cmd`). Each run asks `uv` for the current tree from GitHub, so a
clone that is a week old still starts today's skillize. The Python process
never replaces itself.

Inside this repository the same files notice `pyproject.toml` and call
`uv run` instead, so development does not bounce through GitHub.
"""

from __future__ import annotations

from pathlib import Path

from .store_tree import CONFIG_NAME

SOURCE = "git+https://github.com/pleware/skillize.git"
PACKAGE_NAME = "skillize"
NAME_LINE = f'name = "{PACKAGE_NAME}"'

UNIX_NAME = "skillize"
PS1_NAME = "skillize.ps1"
CMD_NAME = "skillize.cmd"

UNIX = f"""\
#!/bin/sh
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -f "$here/pyproject.toml" ] && grep -q '^name = "{PACKAGE_NAME}"' "$here/pyproject.toml"
then
  exec uv run --project "$here" {PACKAGE_NAME} "$@"
fi
if ! command -v uv >/dev/null 2>&1
then
  echo "skillize: uv is not on PATH" >&2
  exit 1
fi
if [ -n "${{SKILLIZE_OFFLINE-}}" ]
then
  exec uvx --offline --from {SOURCE} {PACKAGE_NAME} "$@"
fi
exec uvx --refresh --from {SOURCE} {PACKAGE_NAME} "$@"
"""

PS1 = f"""\
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$pyproject = Join-Path $here "pyproject.toml"
if ((Test-Path $pyproject) -and (
    Select-String -LiteralPath $pyproject -Pattern '^name = "{PACKAGE_NAME}"' -Quiet
)) {{
    & uv run --project $here {PACKAGE_NAME} @args
    exit $LASTEXITCODE
}}
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {{
    [Console]::Error.WriteLine("skillize: uv is not on PATH")
    exit 1
}}
$uvx = @()
if ($env:SKILLIZE_OFFLINE) {{
    $uvx += "--offline"
}} else {{
    $uvx += "--refresh"
}}
& uvx @uvx --from {SOURCE} {PACKAGE_NAME} @args
exit $LASTEXITCODE
"""

CMD = """\
@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0skillize.ps1" %*
exit /b %ERRORLEVEL%
"""

FILES = {
    UNIX_NAME: UNIX,
    PS1_NAME: PS1,
    CMD_NAME: CMD,
}


def is_self_checkout(directory: Path) -> bool:
    """True when this folder is the skillize source tree, not a consumer."""
    manifest = directory / "pyproject.toml"
    if not manifest.is_file():
        return False
    return NAME_LINE in manifest.read_text(encoding="utf-8")


def write_wrappers(project_root: Path) -> tuple[Path, ...]:
    """Plant the trampolines next to `skillize.yaml`. Idempotent.

    Skip a name that is already a directory — an umbrella that checks out
    this product at `./skillize/` cannot also hold the unix launcher.
    """
    written: list[Path] = []
    for name, text in FILES.items():
        path = project_root / name
        if path.is_dir():
            continue
        current = path.read_text(encoding="utf-8") if path.is_file() else None
        if current != text:
            path.write_text(text, encoding="utf-8", newline="\n")
        if name == UNIX_NAME:
            path.chmod(path.stat().st_mode | 0o111)
        written.append(path)
    return tuple(written)


def wrapper_ignore_hint() -> str:
    return (
        "a deny-by-default .gitignore must whitelist the launchers:\n"
        f"  !/{UNIX_NAME}\n"
        f"  !/{PS1_NAME}\n"
        f"  !/{CMD_NAME}\n"
        f"  !/{CONFIG_NAME}"
    )
