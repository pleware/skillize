"""Skills shipped inside the skillize wheel. Not fetched from GitHub."""

from __future__ import annotations

from collections.abc import Iterable
from importlib.resources import as_file, files
from pathlib import Path

import yaml

from .sources import SKILL_NAME, RemoteSkill

BUNDLED_REPO = "pleware/skillize"
BUNDLED_PACKAGE = "skillize.bundled"


def is_bundled(entry: RemoteSkill) -> bool:
    return entry.repo == BUNDLED_REPO


def _conflicts_from_frontmatter(path: Path) -> tuple[str, ...]:
    """The `conflicts:` list in a bundled SKILL.md frontmatter, if any."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ()
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ()
    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break
    if end is None:
        return ()
    try:
        data = yaml.safe_load("\n".join(lines[1:end]))
    except yaml.YAMLError:
        return ()
    if not isinstance(data, dict):
        return ()
    raw = data.get("conflicts")
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return ()
    return tuple(str(item) for item in raw if isinstance(item, str))


def bundled_entries() -> tuple[RemoteSkill, ...]:
    root = files(BUNDLED_PACKAGE)
    found: list[RemoteSkill] = []
    for child in root.iterdir():
        name = child.name
        if not SKILL_NAME.fullmatch(name):
            continue
        if not child.is_dir() or not (child / "SKILL.md").is_file():
            continue
        conflicts: tuple[str, ...] = ()
        with as_file(child / "SKILL.md") as skill_path:
            conflicts = _conflicts_from_frontmatter(skill_path)
        found.append(
            RemoteSkill(
                name=name,
                repo=BUNDLED_REPO,
                skill_path=f"bundled/{name}/SKILL.md",
                branch="",
                conflicts=conflicts,
            )
        )
    return tuple(sorted(found, key=lambda entry: entry.name))


def mutex_groups(entries: Iterable[RemoteSkill]) -> tuple[tuple[str, ...], ...]:
    """Mutually-exclusive skill sets, derived from each entry's `conflicts`."""
    seen: set[frozenset[str]] = set()
    groups: list[tuple[str, ...]] = []
    for entry in entries:
        if not entry.conflicts:
            continue
        group = frozenset((entry.name, *entry.conflicts))
        if group in seen:
            continue
        seen.add(group)
        groups.append(tuple(sorted(group)))
    return tuple(groups)
