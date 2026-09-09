"""skillize command line."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .errors import SkillizeError
from .policy import load_policy, load_policy_or_empty
from .sources import refresh_catalogue
from .store_tree import CONFIG_NAME, config_is_ignored, config_path, ensure_data_dir
from .tui import run_configure
from .wrapper import UNIX_NAME, write_wrappers


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
    subcommands.add_parser("refresh", help="list GitHub packs into the configure catalogue")
    subcommands.add_parser("init", help=f"plant launchers next to {CONFIG_NAME}")
    return parser


def cmd_check(root: Path) -> int:
    policy = load_policy(root)
    enabled = policy.enabled_names()
    print(f"skillize: {policy.path} (v{policy.version})")
    print(f"skillize: {len(enabled)} enabled / {len(policy.skills)} listed")
    for name in enabled:
        print(f"skillize: on  {name}")
    return 0


def cmd_init(root: Path) -> int:
    directory = ensure_data_dir(root)
    config = config_path(root)
    print(f"skillize: policy {config}")
    print(f"skillize: data   {directory}")

    for path in write_wrappers(root):
        print(f"skillize: launcher {path.name}")
    unix = root / UNIX_NAME
    if unix.is_dir():
        print(
            f"skillize: skip {UNIX_NAME} (a directory occupies that name)",
            file=sys.stderr,
        )

    if config_is_ignored(root):
        print(
            f"skillize: {CONFIG_NAME} is ignored by .gitignore, so it can never be\n"
            f"skillize: committed. Whitelist it with: !/{CONFIG_NAME}",
            file=sys.stderr,
        )
        return 1

    if not config.is_file():
        print(f"skillize: write {config} to continue")
    return 0


def cmd_refresh(root: Path) -> int:
    ensure_data_dir(root)
    policy = load_policy_or_empty(root)
    names, note = refresh_catalogue(root, policy)
    print(f"skillize: {note}")
    for name in names:
        print(f"skillize: {name}")
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
        if command == "init":
            return cmd_init(root)
        if command == "refresh":
            return cmd_refresh(root)
    except SkillizeError as exc:
        print(f"skillize: {exc}", file=sys.stderr)
        return 1
    parser.error(f"unknown command {command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
