"""skillize command line."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .catalogue import skill_is_installed
from .errors import SkillizeError
from .install import install_skill, uninstall_skill
from .policy import load_policy, load_policy_or_empty
from .sources import refresh_catalogue, skill_slug
from .store_tree import CONFIG_NAME, config_is_ignored, config_path, ensure_data_dir
from .tui import run_configure
from .wrapper import UNIX_NAME, write_wrappers

AGENTIZE_CONFIG = "agentize.yaml"


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
    subcommands.add_parser("configure", help="Installed or Install New, then enable skills")
    subcommands.add_parser("refresh", help="list bundled and GitHub packs")
    install = subcommands.add_parser("install", help="copy a bundled or GitHub skill")
    install.add_argument("name", help="skill name or owner/repo/skill (as listed by refresh)")
    uninstall = subcommands.add_parser("uninstall", help="remove a bundled or GitHub skill")
    uninstall.add_argument("name", help="skill name (as listed by refresh)")
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
    entries, note = refresh_catalogue(root, policy)
    print(f"skillize: {note}")
    for entry in entries:
        print(f"skillize: {skill_slug(entry)}")
    return 0


def _parse_install_target(name: str) -> tuple[str | None, str]:
    """`owner/repo/skill` selects one pack; a plain `skill` matches by name."""
    parts = name.split("/")
    if len(parts) == 3 and all(parts):
        return f"{parts[0]}/{parts[1]}", parts[2]
    return None, name


def _agentize_hint(root: Path) -> None:
    if (root / AGENTIZE_CONFIG).is_file():
        print(
            "skillize: host copies refresh on the next `agentize mount` — "
            "run it to pick this up",
            file=sys.stderr,
        )


def cmd_install(root: Path, name: str) -> int:
    ensure_data_dir(root)
    policy = load_policy_or_empty(root)
    entries, note = refresh_catalogue(root, policy)
    print(f"skillize: {note}", file=sys.stderr)
    repo, skill_name = _parse_install_target(name)
    matches = [
        entry
        for entry in entries
        if entry.name == skill_name and (repo is None or entry.repo == repo)
    ]
    if not matches:
        print(f"skillize: no skill named {name} in the catalogue", file=sys.stderr)
        return 1
    from .builtin import is_bundled

    preferred = [entry for entry in matches if is_bundled(entry)]
    chosen = (preferred or matches)[0]
    if len(matches) > 1 and not preferred:
        print(
            f"skillize: {len(matches)} matches; using {chosen.repo}",
            file=sys.stderr,
        )
    dest = install_skill(root, chosen)
    print(f"skillize: installed {chosen.name} → {dest}")
    _agentize_hint(root)
    return 0


def cmd_uninstall(root: Path, name: str) -> int:
    if not skill_is_installed(root, name):
        print(f"skillize: {name} is not installed on this tree", file=sys.stderr)
        return 1
    uninstall_skill(root, name)
    print(f"skillize: uninstalled {name}")
    _agentize_hint(root)
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
        if command == "install":
            return cmd_install(root, args.name)
        if command == "uninstall":
            return cmd_uninstall(root, args.name)
    except SkillizeError as exc:
        print(f"skillize: {exc}", file=sys.stderr)
        return 1
    parser.error(f"unknown command {command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
