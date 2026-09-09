"""skillize command line."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .errors import SkillizeError
from .policy import load_policy
from .store_tree import CONFIG_NAME
from .tui import run_configure


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skillize",
        description="Enable agent skills and say when they fire.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "-C",
        "--directory",
        type=Path,
        default=None,
        metavar="PATH",
        help="project root (default: current directory)",
    )
    subcommands = parser.add_subparsers(dest="command")
    subcommands.add_parser("check", help=f"validate {CONFIG_NAME} against schema v1")
    subcommands.add_parser("configure", help=f"checkbox TUI for {CONFIG_NAME}")
    return parser


def cmd_check(root: Path) -> int:
    policy = load_policy(root)
    enabled = policy.enabled_names()
    print(f"skillize: {policy.path} (v{policy.version})")
    print(f"skillize: {len(enabled)} enabled / {len(policy.skills)} listed")
    for name in enabled:
        print(f"skillize: on  {name}")
    return 0


def cmd_configure(root: Path) -> int:
    if not sys.stdin.isatty():
        print("skillize: configure needs a terminal; use `skillize check`", file=sys.stderr)
        return 2
    return run_configure(root)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = (args.directory or Path.cwd()).resolve()
    command = args.command or "configure"
    try:
        if command == "check":
            return cmd_check(root)
        if command == "configure":
            return cmd_configure(root)
    except SkillizeError as exc:
        print(f"skillize: {exc}", file=sys.stderr)
        return 1
    parser.error(f"unknown command {command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
